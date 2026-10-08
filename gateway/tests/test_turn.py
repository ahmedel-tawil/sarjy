import asyncio

import pytest
from sarjy_gateway.llm import ChatMessage, ChatModelError, ChatRateLimitedError
from sarjy_gateway.prompts import SYSTEM_PROMPT
from sarjy_gateway.stt import RateLimitedError, SpeechToTextError
from sarjy_gateway.tts import TextToSpeechError
from sarjy_gateway.turn import Conversation, TurnError, TurnPipeline

from gateway.tests.fakes import (
    FakeChatModel,
    FakeSpeechToText,
    FakeTextToSpeech,
    RecordingListener,
    SpeechRequest,
    TickingClock,
)


def test_a_turn_transcribes_answers_and_speaks_in_order() -> None:
    tts = FakeTextToSpeech()
    pipeline = TurnPipeline(FakeSpeechToText(), FakeChatModel(), tts, TickingClock())
    listener = RecordingListener()

    turn = asyncio.run(pipeline.run(b"clip", Conversation(max_turns=6, voice="am_adam"), listener))

    assert listener.events == [
        "transcript What can we do in Abu Dhabi?",
        "reply Try the Louvre.",
        f"audio {len(b'RIFFTry the Louvre.')} bytes",
    ]
    assert tts.requests == [SpeechRequest("Try the Louvre.", "am_adam")]
    assert (turn.transcript, turn.reply, turn.tool_results) == ("What can we do in Abu Dhabi?", "Try the Louvre.", [])


def test_marks_follow_the_turn_in_order_from_audio_received() -> None:
    pipeline = TurnPipeline(FakeSpeechToText(), FakeChatModel(), FakeTextToSpeech(), TickingClock())

    turn = asyncio.run(pipeline.run(b"clip", Conversation(max_turns=6), RecordingListener()))

    assert list(turn.marks) == ["audio_received", "stt_done", "llm_first_token", "first_sentence_ready", "tts_first_byte"]
    assert turn.marks["audio_received"] == 0
    assert list(turn.marks.values()) == sorted(turn.marks.values())


def test_the_llm_sees_the_system_prompt_recent_turns_and_the_new_question() -> None:
    llm = FakeChatModel()
    pipeline = TurnPipeline(FakeSpeechToText(), llm, FakeTextToSpeech(), TickingClock())
    conversation = Conversation(max_turns=6)

    asyncio.run(pipeline.run(b"first", conversation, RecordingListener()))
    asyncio.run(pipeline.run(b"second", conversation, RecordingListener()))

    assert llm.requests[1] == [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content="What can we do in Abu Dhabi?"),
        ChatMessage(role="assistant", content="Try the Louvre."),
        ChatMessage(role="user", content="What can we do in Abu Dhabi?"),
    ]


def test_only_the_most_recent_turns_are_kept() -> None:
    conversation = Conversation(max_turns=2)

    for number in range(5):
        conversation.remember(f"question {number}", f"answer {number}")

    assert [message.content for message in conversation.history] == [
        "question 3",
        "answer 3",
        "question 4",
        "answer 4",
    ]


@pytest.mark.parametrize(
    ("stt", "llm", "tts", "code"),
    [
        (FakeSpeechToText(error=SpeechToTextError("down")), FakeChatModel(), FakeTextToSpeech(), "stt_failed"),
        (FakeSpeechToText(error=RateLimitedError("slow")), FakeChatModel(), FakeTextToSpeech(), "rate_limited"),
        (FakeSpeechToText(transcript=""), FakeChatModel(), FakeTextToSpeech(), "no_speech"),
        (FakeSpeechToText(), FakeChatModel(error=ChatModelError("down")), FakeTextToSpeech(), "llm_failed"),
        (FakeSpeechToText(), FakeChatModel(error=ChatRateLimitedError("slow")), FakeTextToSpeech(), "rate_limited"),
        (FakeSpeechToText(), FakeChatModel(deltas=()), FakeTextToSpeech(), "llm_failed"),
        (FakeSpeechToText(), FakeChatModel(), FakeTextToSpeech(error=TextToSpeechError("down")), "tts_failed"),
    ],
    ids=[
        "stt fails",
        "stt rate limited",
        "nothing was said",
        "llm fails",
        "llm rate limited",
        "llm says nothing",
        "tts fails",
    ],
)
def test_a_failing_stage_raises_one_clear_code_and_leaves_history_alone(
    stt: FakeSpeechToText, llm: FakeChatModel, tts: FakeTextToSpeech, code: str
) -> None:
    pipeline = TurnPipeline(stt, llm, tts, TickingClock())
    conversation = Conversation(max_turns=6)

    with pytest.raises(TurnError) as raised:
        asyncio.run(pipeline.run(b"clip", conversation, RecordingListener()))

    assert raised.value.code == code
    assert raised.value.turn_id
    assert conversation.history == []
