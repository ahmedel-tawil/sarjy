from collections.abc import Mapping
import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sarjy_gateway.messages import AudioFollows, Reply, ServerError, Transcript, TurnMarks
from sarjy_gateway.stt import SpeechToTextError
from sarjy_gateway.turn import TurnPipeline
from sarjy_gateway.voice import VoiceRouter

from gateway.tests.fakes import FakeChatModel, FakeSpeechToText, FakeTextToSpeech, SpeechRequest, TickingClock


TURN_END = '{"type": "turn_end"}'
TURN_ID = "0199c3a4b5d67e8f9a0b1c2d3e4f5a6b"


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
    stt: FakeSpeechToText | None = None, tts: FakeTextToSpeech | None = None, max_turn_audio_bytes: int = 1_000
) -> TestClient:
    tts = tts or FakeTextToSpeech()
    pipeline = TurnPipeline(stt or FakeSpeechToText(), FakeChatModel(), tts, TickingClock())
    app = FastAPI()
    app.include_router(VoiceRouter(pipeline, tts, max_turn_audio_bytes, max_history_turns=6).build())
    return TestClient(app)


def test_a_turn_sends_transcript_reply_audio_and_marks() -> None:
    with voice_client().websocket_connect("/ws") as socket:
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
    with voice_client(tts=tts).websocket_connect("/ws") as socket:
        socket.send_text('{"type": "set_voice", "voice": "am_adam"}')
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)
        for _ in range(3):
            socket.receive_text()
        socket.receive_bytes()
        socket.receive_text()

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
    with voice_client(max_turn_audio_bytes=10).websocket_connect("/ws") as socket:
        if before:
            socket.send_bytes(before)
        socket.send_text(control)

        assert ServerError.model_validate_json(socket.receive_text()).code == expected_code


def test_a_failed_turn_reports_its_code_and_keeps_the_socket_open() -> None:
    with voice_client(stt=FakeSpeechToText(error=SpeechToTextError("down"))).websocket_connect("/ws") as socket:
        socket.send_bytes(b"clip")
        socket.send_text(TURN_END)
        failure = ServerError.model_validate_json(socket.receive_text())
        socket.send_text(TURN_END)
        after = ServerError.model_validate_json(socket.receive_text())

    assert (failure.code, after.code) == ("stt_failed", "no_audio")
    assert failure.turn_id


def test_browser_marks_log_the_turns_ttfa_without_a_reply(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="sarjy_gateway.voice")
    with voice_client().websocket_connect("/ws") as socket:
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
    with voice_client().websocket_connect("/ws") as socket:
        socket.send_bytes(b"silence")
        socket.send_text('{"type": "turn_cancel"}')
        socket.send_text(TURN_END)

        assert ServerError.model_validate_json(socket.receive_text()).code == "no_audio"
