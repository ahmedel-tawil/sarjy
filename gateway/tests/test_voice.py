from collections.abc import Mapping
from contextlib import contextmanager
import json
import logging
from typing import TYPE_CHECKING, Protocol
import uuid

from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient
from pydantic import BaseModel
import pytest
from sarjy_gateway.conversation_store import TurnId
from sarjy_gateway.database import DatabaseUnavailableError
from sarjy_gateway.identity import COOKIE_NAME, UserId, new_user_id
from sarjy_gateway.limits import MAX_KEYS, SlidingWindow, TurnLimits
from sarjy_gateway.llm import TextDelta, ToolCallDelta
from sarjy_gateway.messages import (
    Activity,
    AudioFollows,
    History,
    Memory,
    RememberedFact,
    Reply,
    ServerError,
    Transcript,
    TurnMarks,
)
from sarjy_gateway.stt import SpeechToTextError
from sarjy_gateway.tools import TOOL_TIMEOUT_SECONDS, Toolbox
from sarjy_gateway.tts import TextToSpeechError
from sarjy_gateway.turn import TurnPipeline
from sarjy_gateway.voice import VoiceRouter

from gateway.tests.fakes import (
    FakeChatModel,
    FakeConversationStore,
    FakeFactStore,
    FakePrompt,
    FakeSpeechToText,
    FakeTextToSpeech,
    ManualClock,
    SpeechRequest,
    TickingClock,
)


if TYPE_CHECKING:
    from collections.abc import Generator


TURN_END = '{"type": "turn_end"}'
FORGET_ME = '{"type": "forget_me"}'
TURN_ID = "0199c3a4b5d67e8f9a0b1c2d3e4f5a6b"
USER_ID = UserId(uuid.UUID("0199c3a4-0000-7000-8000-00000000abcd"))


def browser_marks(speech_end: float, playback_start: float, turn_id: str = TURN_ID) -> str:
    return json.dumps(
        {
            "type": "browser_marks",
            "turn_id": turn_id,
            "speech_end": speech_end,
            "playback_start": playback_start,
        }
    )


def voice_client(
    *,
    stt: FakeSpeechToText | None = None,
    tts: FakeTextToSpeech | None = None,
    max_turn_audio_bytes: int = 1_000,
    store: FakeConversationStore | None = None,
    cookie: str | None = str(USER_ID),
    facts: FakeFactStore | None = None,
    llm: FakeChatModel | None = None,
    prompt: FakePrompt | None = None,
    limits: TurnLimits | None = None,
    max_turns_per_visit: int = 100,
) -> TestClient:
    tts = tts or FakeTextToSpeech()
    toolbox = Toolbox([], TickingClock(), TOOL_TIMEOUT_SECONDS)
    pipeline = TurnPipeline(
        stt or FakeSpeechToText(),
        llm or FakeChatModel(),
        tts,
        toolbox,
        system_prompt=(prompt or FakePrompt()).build,
        clock=TickingClock(),
        sentence_streaming=False,
    )
    app = FastAPI()
    router = VoiceRouter(
        pipeline,
        tts,
        store or FakeConversationStore(),
        facts or FakeFactStore(),
        limits or roomy_limits(),
        max_turn_audio_bytes=max_turn_audio_bytes,
        max_history_turns=6,
        max_turns_per_visit=max_turns_per_visit,
    )
    app.include_router(router.build())
    return TestClient(app, cookies=None if cookie is None else {COOKIE_NAME: cookie})


def roomy_limits(*, per_user: int = 1_000, per_ip: int = 1_000) -> TurnLimits:
    clock = ManualClock()
    return TurnLimits(
        per_user=SlidingWindow(per_user, 600, clock, max_keys=MAX_KEYS),
        per_ip=SlidingWindow(per_ip, 600, clock, max_keys=MAX_KEYS),
    )


# Reads only the type of whatever the gateway sent.
class AnyMessage(BaseModel):
    type: str


# The parts of the test client's socket these tests use.
class Socket(Protocol):
    def send_text(self, data: str, /) -> None: ...

    def send_bytes(self, data: bytes, /) -> None: ...

    def receive_text(self) -> str: ...

    def receive_bytes(self) -> bytes: ...


# Opens the socket and reads the memory list and the history every visit starts with.
@contextmanager
def visit(client: TestClient) -> Generator[Socket]:
    with client.websocket_connect("/ws") as socket:
        Memory.model_validate_json(socket.receive_text())
        History.model_validate_json(socket.receive_text())
        yield socket


# Sends one clip and reads the whole answer: transcript, reply, audio and marks.
def answered_turn(socket: Socket) -> Reply:
    socket.send_bytes(b"clip")
    socket.send_text(TURN_END)
    Transcript.model_validate_json(socket.receive_text())
    reply = Reply.model_validate_json(socket.receive_text())
    AudioFollows.model_validate_json(socket.receive_text())
    socket.receive_bytes()
    TurnMarks.model_validate_json(socket.receive_text())
    return reply


def refused_turn(socket: Socket) -> str:
    socket.send_bytes(b"clip")
    socket.send_text(TURN_END)
    return ServerError.model_validate_json(socket.receive_text()).code


def test_a_turn_sends_transcript_reply_audio_and_marks() -> None:
    with visit(voice_client()) as socket:
        socket.send_bytes(b"first ")
        socket.send_bytes(b"second")
        socket.send_text(TURN_END)

        transcript = Transcript.model_validate_json(socket.receive_text())
        reply = Reply.model_validate_json(socket.receive_text())
        audio_follows = AudioFollows.model_validate_json(socket.receive_text())
        audio = socket.receive_bytes()
        marks = TurnMarks.model_validate_json(socket.receive_text())

    assert transcript.text == "What can we do in Abu Dhabi?"
    assert reply.text == "Try the Louvre."
    assert audio == b"RIFFTry the Louvre."
    assert transcript.turn_id == reply.turn_id == audio_follows.turn_id == marks.turn_id
    assert "tts_first_byte" in marks.marks


def test_set_voice_changes_the_voice_of_later_turns() -> None:
    tts = FakeTextToSpeech()
    with visit(voice_client(tts=tts)) as socket:
        socket.send_text('{"type": "set_voice", "voice": "am_adam"}')
        Memory.model_validate_json(socket.receive_text())
        answered_turn(socket)

    assert tts.requests == [SpeechRequest("Try the Louvre.", "am_adam")]


@pytest.mark.parametrize(
    ("before", "control", "expected_code"),
    [
        (b"", '{"type": "set_voice", "voice": "nobody"}', "unknown_voice"),
        (b"", '{"type": "dance"}', "invalid_message"),
        (b"", TURN_END, "no_audio"),
        (b"x" * 11, TURN_END, "turn_too_long"),
        (b"", browser_marks(speech_end=900, playback_start=100), "invalid_message"),
        (b"", browser_marks(speech_end=100, playback_start=900, turn_id="../../etc"), "invalid_message"),
    ],
    ids=[
        "unknown voice",
        "unknown control message",
        "turn end without audio",
        "audio over the limit",
        "playback before speech end",
        "turn id that the gateway never makes",
    ],
)
def test_problems_before_the_pipeline_are_reported(before: bytes, control: str, expected_code: str) -> None:
    with visit(voice_client(max_turn_audio_bytes=10)) as socket:
        if before:
            socket.send_bytes(before)
        socket.send_text(control)

        assert ServerError.model_validate_json(socket.receive_text()).code == expected_code


def test_a_failed_turn_reports_its_code_and_keeps_the_socket_open() -> None:
    with visit(voice_client(stt=FakeSpeechToText(error=SpeechToTextError("down")))) as socket:
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)
        failure = ServerError.model_validate_json(socket.receive_text())
        socket.send_text(TURN_END)
        after = ServerError.model_validate_json(socket.receive_text())

    assert (failure.code, after.code) == ("stt_failed", "no_audio")
    assert failure.turn_id


def test_browser_marks_log_the_turns_ttfa_without_a_reply(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="sarjy_gateway.voice")
    with visit(voice_client()) as socket:
        socket.send_text(browser_marks(speech_end=1000.0, playback_start=4212.34))
        # The next message answers the turn end, so the marks themselves got no reply.
        socket.send_text(TURN_END)
        reply = ServerError.model_validate_json(socket.receive_text())

    played = [record.args for record in caplog.records if record.msg == "turn %(turn_id)s played"]
    assert reply.code == "no_audio"
    assert len(played) == 1
    assert isinstance(played[0], Mapping)
    assert played[0] == {"turn_id": TURN_ID, "ttfa_ms": 3212.3}


def test_a_cancelled_turn_drops_its_audio() -> None:
    with visit(voice_client()) as socket:
        socket.send_bytes(b"silence")
        socket.send_text('{"type": "turn_cancel"}')
        socket.send_text(TURN_END)

        assert ServerError.model_validate_json(socket.receive_text()).code == "no_audio"


def test_a_browser_that_leaves_mid_turn_ends_the_session_quietly(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="sarjy_gateway.voice")
    # A send to a closed socket raises this mid-turn; the fake STT raises it at that point.
    stt = FakeSpeechToText(error=WebSocketDisconnect(code=1006))
    with visit(voice_client(stt=stt)) as socket:
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)

    assert "browser left mid-turn" in caplog.messages


@pytest.mark.parametrize("cookie", [None, "not-a-user-id"], ids=["no cookie", "garbled cookie"])
def test_a_socket_without_a_valid_identity_cookie_is_refused(cookie: str | None) -> None:
    client = voice_client(cookie=cookie)

    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect("/ws") as socket:
        socket.receive_text()

    assert refused.value.code == 1008


def test_a_visit_starts_a_session_and_each_turn_is_saved_to_it() -> None:
    store = FakeConversationStore()
    with visit(voice_client(store=store)) as socket:
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)
        for _ in range(3):
            socket.receive_text()
        socket.receive_bytes()
        marks = TurnMarks.model_validate_json(socket.receive_text())

    ((user_id, session_id),) = store.sessions
    (turn,) = store.saved[session_id]
    assert user_id == USER_ID
    assert turn.id == uuid.UUID(hex=marks.turn_id)
    assert (turn.transcript, turn.reply) == ("What can we do in Abu Dhabi?", "Try the Louvre.")


def test_without_the_database_the_turn_is_still_answered(caplog: pytest.LogCaptureFixture) -> None:
    store = FakeConversationStore(error=DatabaseUnavailableError("database unreachable: PoolTimeout"))
    caplog.set_level(logging.WARNING, logger="sarjy_gateway.voice")
    with visit(voice_client(store=store)) as socket:
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)
        reply = [Transcript.model_validate_json(socket.receive_text()), Reply.model_validate_json(socket.receive_text())]

    assert reply[1].text == "Try the Louvre."
    assert caplog.messages == [
        "session not stored: database unreachable: PoolTimeout",
        "earlier visits not loaded: database unreachable: PoolTimeout",
    ]


def test_a_visit_starts_knowing_the_users_facts_and_with_memory_tools() -> None:
    facts = FakeFactStore({USER_ID: {"favourite_colour": "green"}})
    llm = FakeChatModel()
    prompt = FakePrompt()
    with visit(voice_client(facts=facts, llm=llm, prompt=prompt)) as socket:
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)
        Transcript.model_validate_json(socket.receive_text())
        Reply.model_validate_json(socket.receive_text())

    assert prompt.facts_seen == [{"favourite_colour": "green"}]
    assert llm.offered_tools[0] == ["remember_fact", "forget_fact"]


def test_a_visit_opens_with_the_users_facts_for_the_memory_panel() -> None:
    facts = FakeFactStore({USER_ID: {"travelling_with": "two children", "favourite_colour": "green"}})
    with voice_client(facts=facts).websocket_connect("/ws") as socket:
        memory = Memory.model_validate_json(socket.receive_text())

    assert memory.facts == [
        RememberedFact(key="favourite_colour", value="green"),
        RememberedFact(key="travelling_with", value="two children"),
    ]


def test_a_fact_saved_mid_turn_is_announced_and_reaches_the_page_before_the_reply() -> None:
    save = ToolCallDelta(0, "call-1", "remember_fact", '{"key": "favourite_colour", "value": "green"}')
    llm = FakeChatModel(rounds=[[save], [TextDelta("Noted, green.")]])
    with visit(voice_client(llm=llm)) as socket:
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)
        Transcript.model_validate_json(socket.receive_text())
        activity = Activity.model_validate_json(socket.receive_text())
        memory = Memory.model_validate_json(socket.receive_text())
        reply = Reply.model_validate_json(socket.receive_text())

    assert activity.text == "Noting that down"
    assert memory.facts == [RememberedFact(key="favourite_colour", value="green")]
    assert reply.text == "Noted, green."


def test_forget_me_deletes_the_facts_and_empties_the_panel_and_the_next_prompt() -> None:
    facts = FakeFactStore({USER_ID: {"favourite_colour": "green"}})
    prompt = FakePrompt()
    with visit(voice_client(facts=facts, prompt=prompt)) as socket:
        socket.send_text(FORGET_ME)
        memory = Memory.model_validate_json(socket.receive_text())
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)
        Transcript.model_validate_json(socket.receive_text())
        Reply.model_validate_json(socket.receive_text())

    assert memory.facts == []
    assert USER_ID not in facts.saved
    assert prompt.facts_seen == [{}]


def test_forget_me_without_the_database_tells_the_page(caplog: pytest.LogCaptureFixture) -> None:
    facts = FakeFactStore(error=DatabaseUnavailableError("database unreachable: PoolTimeout"))
    caplog.set_level(logging.WARNING, logger="sarjy_gateway.voice")
    with visit(voice_client(facts=facts)) as socket:
        socket.send_text(FORGET_ME)
        error = ServerError.model_validate_json(socket.receive_text())

    assert error.code == "forget_failed"
    assert "facts not forgotten: database unreachable: PoolTimeout" in caplog.messages


def test_a_user_over_their_limit_hears_to_slow_down(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sarjy_gateway.voice")
    with visit(voice_client(limits=roomy_limits(per_user=1))) as socket:
        reply = answered_turn(socket)
        refused = refused_turn(socket)

    assert reply.text == "Try the Louvre."
    assert refused == "too_many_turns"
    assert caplog.messages == ["turn refused: too many turns from this user or ip"]


def test_new_cookies_from_one_address_share_its_limit_however_the_header_is_forged() -> None:
    limits = roomy_limits(per_ip=1)
    answers: list[str] = []
    for forged in ("6.6.6.6", "7.7.7.7"):
        client = voice_client(limits=limits, cookie=str(new_user_id()))
        headers = {"x-forwarded-for": f"{forged}, 203.0.113.7"}
        with client.websocket_connect("/ws", headers=headers) as socket:
            Memory.model_validate_json(socket.receive_text())
            History.model_validate_json(socket.receive_text())
            socket.send_bytes(b"clip")
            socket.send_text(TURN_END)
            answers.append(AnyMessage.model_validate_json(socket.receive_text()).type)

    assert answers == ["transcript", "error"]


def test_a_visit_stops_at_its_turn_limit() -> None:
    with visit(voice_client(max_turns_per_visit=1)) as socket:
        answered_turn(socket)
        refused = refused_turn(socket)

    assert refused == "visit_limit"


def test_a_turns_marks_are_stored_with_the_browsers_once_it_plays() -> None:
    store = FakeConversationStore()
    with visit(voice_client(store=store)) as socket:
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)
        for _ in range(3):
            socket.receive_text()
        socket.receive_bytes()
        marks = TurnMarks.model_validate_json(socket.receive_text())
        socket.send_text(browser_marks(speech_end=1000.0, playback_start=4212.34, turn_id=marks.turn_id))
        # Anything after the marks proves they were handled.
        socket.send_text(TURN_END)
        ServerError.model_validate_json(socket.receive_text())

    stored = store.stored_marks[TurnId(uuid.UUID(hex=marks.turn_id))]
    assert set(stored) == {*marks.marks, "speech_end", "playback_start"}
    assert len(stored) == 7
    assert (stored["speech_end"], stored["playback_start"]) == (1000.0, 4212.34)


def test_browser_marks_for_a_turn_of_another_visit_are_not_stored() -> None:
    store = FakeConversationStore()
    with visit(voice_client(store=store)) as socket:
        socket.send_text(browser_marks(speech_end=1000.0, playback_start=4212.34))
        socket.send_text(TURN_END)
        ServerError.model_validate_json(socket.receive_text())

    assert store.stored_marks == {}


def test_opening_a_visit_wakes_tts_before_the_first_question() -> None:
    tts = FakeTextToSpeech()
    with visit(voice_client(tts=tts)) as socket:
        # Anything answered proves the visit's start, and its wake-up, has run.
        socket.send_text(TURN_END)
        ServerError.model_validate_json(socket.receive_text())

    assert tts.voice_lists == 1
    assert tts.requests == []


def test_a_failed_wake_up_does_not_stop_the_visit(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="sarjy_gateway.voice")
    tts = FakeTextToSpeech(error=TextToSpeechError("tts unreachable"))
    with visit(voice_client(tts=tts)) as socket:
        socket.send_text(TURN_END)
        refused = ServerError.model_validate_json(socket.receive_text())

    assert refused.code == "no_audio"
    assert "tts wake-up failed: tts unreachable" in caplog.messages


def test_a_picked_voice_is_remembered_and_shown_in_the_memory_panel() -> None:
    facts = FakeFactStore()
    with visit(voice_client(facts=facts)) as socket:
        socket.send_text('{"type": "set_voice", "voice": "am_adam"}')
        memory = Memory.model_validate_json(socket.receive_text())

    assert facts.saved[USER_ID] == {"voice": "am_adam"}
    assert memory.facts == [RememberedFact(key="voice", value="am_adam")]


def test_a_returning_visitor_hears_the_voice_they_picked() -> None:
    tts = FakeTextToSpeech()
    facts = FakeFactStore({USER_ID: {"voice": "am_adam"}})
    with visit(voice_client(tts=tts, facts=facts)) as socket:
        answered_turn(socket)

    assert tts.requests == [SpeechRequest("Try the Louvre.", "am_adam")]


def test_a_visit_opens_with_the_users_earlier_visits_newest_first() -> None:
    store = FakeConversationStore()
    with visit(voice_client(store=store)) as socket:
        answered_turn(socket)
    with visit(voice_client(store=store)) as socket:
        socket.send_text(TURN_END)
        ServerError.model_validate_json(socket.receive_text())
    with voice_client(store=store).websocket_connect("/ws") as socket:
        Memory.model_validate_json(socket.receive_text())
        history = History.model_validate_json(socket.receive_text())

    # The second visit asked nothing, so only the first is shown.
    ((earlier,),) = [history.visits]
    ((turn,),) = [earlier.turns]
    assert (turn.transcript, turn.reply) == ("What can we do in Abu Dhabi?", "Try the Louvre.")


def test_a_replay_speaks_an_earlier_reply_again_in_the_visits_voice() -> None:
    store = FakeConversationStore()
    tts = FakeTextToSpeech()
    with visit(voice_client(store=store)) as socket:
        reply = answered_turn(socket)
    tts.requests.clear()
    facts = FakeFactStore({USER_ID: {"voice": "am_adam"}})
    with visit(voice_client(store=store, tts=tts, facts=facts)) as socket:
        socket.send_text(json.dumps({"type": "replay", "turn_id": reply.turn_id}))
        follows = AudioFollows.model_validate_json(socket.receive_text())
        audio = socket.receive_bytes()
        done = AnyMessage.model_validate_json(socket.receive_text())

    assert (follows.turn_id, follows.text, audio) == (reply.turn_id, "Try the Louvre.", b"RIFFTry the Louvre.")
    assert done.type == "replay_done"
    assert tts.requests == [SpeechRequest("Try the Louvre.", "am_adam")]


def test_a_page_cannot_replay_another_users_turn() -> None:
    store = FakeConversationStore()
    with visit(voice_client(store=store, cookie=str(new_user_id()))) as socket:
        theirs = answered_turn(socket)
    with visit(voice_client(store=store)) as socket:
        socket.send_text(json.dumps({"type": "replay", "turn_id": theirs.turn_id}))
        refused = ServerError.model_validate_json(socket.receive_text())

    assert (refused.code, refused.turn_id) == ("replay_failed", theirs.turn_id)


def test_replays_count_against_the_turn_limits() -> None:
    store = FakeConversationStore()
    limits = roomy_limits(per_user=1)
    with visit(voice_client(store=store, limits=limits)) as socket:
        reply = answered_turn(socket)
        socket.send_text(json.dumps({"type": "replay", "turn_id": reply.turn_id}))
        refused = ServerError.model_validate_json(socket.receive_text())

    assert refused.code == "too_many_turns"
