import asyncio

import pytest
from sarjy_gateway.llm import (
    ChatMessage,
    ChatModelError,
    ChatRateLimitedError,
    TextDelta,
    ToolCall,
    ToolCallDelta,
)
from sarjy_gateway.stt import RateLimitedError, SpeechToTextError
from sarjy_gateway.tools import TOOL_TIMEOUT_SECONDS, Toolbox, ToolFailure
from sarjy_gateway.tts import TextToSpeechError
from sarjy_gateway.turn import MAX_TOOL_ROUNDS, CompletedTurn, Conversation, TurnError, TurnPipeline

from gateway.tests.fakes import (
    FIXED_PROMPT,
    FakeChatModel,
    FakePrompt,
    FakeSpeechToText,
    FakeTextToSpeech,
    FakeWeatherTool,
    RecordingListener,
    SpeechRequest,
    TickingClock,
    WeatherArguments,
)


DUBAI_CALL = ToolCallDelta(0, "call-1", "get_weather", '{"city": "Dubai", "date": "2026-10-09"}')


def pipeline_with(
    llm: FakeChatModel,
    tool: FakeWeatherTool | None = None,
    tts: FakeTextToSpeech | None = None,
    *,
    sentence_streaming: bool = False,
) -> TurnPipeline:
    # The toolbox's own clock only times tools for the logs, so it is kept apart from the
    # pipeline's, whose readings the mark tests count.
    toolbox = Toolbox([] if tool is None else [tool], TickingClock(), TOOL_TIMEOUT_SECONDS)
    return TurnPipeline(
        FakeSpeechToText(),
        llm,
        tts or FakeTextToSpeech(),
        toolbox,
        system_prompt=FakePrompt().build,
        clock=TickingClock(),
        sentence_streaming=sentence_streaming,
    )


def run(pipeline: TurnPipeline) -> CompletedTurn:
    return asyncio.run(pipeline.run(b"clip", Conversation(max_turns=6), RecordingListener()))


def test_a_turn_transcribes_answers_and_speaks_in_order() -> None:
    tts = FakeTextToSpeech()
    pipeline = pipeline_with(FakeChatModel(), tts=tts)
    listener = RecordingListener()

    turn = asyncio.run(pipeline.run(b"clip", Conversation(max_turns=6, voice="am_adam"), listener))

    assert listener.events == [
        "transcript What can we do in Abu Dhabi?",
        "reply Try the Louvre.",
        f"audio {len(b'RIFFTry the Louvre.')} bytes: Try the Louvre.",
    ]
    assert tts.requests == [SpeechRequest("Try the Louvre.", "am_adam")]
    assert (turn.transcript, turn.reply, turn.tool_results) == ("What can we do in Abu Dhabi?", "Try the Louvre.", [])


def test_marks_follow_the_turn_in_order_from_audio_received() -> None:
    turn = run(pipeline_with(FakeChatModel()))

    assert list(turn.marks) == ["audio_received", "stt_done", "llm_first_token", "first_sentence_ready", "tts_first_byte"]
    assert turn.marks["audio_received"] == 0
    assert list(turn.marks.values()) == sorted(turn.marks.values())


def test_the_llm_sees_the_system_prompt_recent_turns_and_the_new_question() -> None:
    llm = FakeChatModel()
    pipeline = pipeline_with(llm)
    conversation = Conversation(max_turns=6)

    asyncio.run(pipeline.run(b"first", conversation, RecordingListener()))
    asyncio.run(pipeline.run(b"second", conversation, RecordingListener()))

    assert llm.requests[1] == [
        ChatMessage(role="system", content=FIXED_PROMPT),
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
    toolbox = Toolbox([], TickingClock(), TOOL_TIMEOUT_SECONDS)
    pipeline = TurnPipeline(
        stt, llm, tts, toolbox, system_prompt=FakePrompt().build, clock=TickingClock(), sentence_streaming=False
    )
    conversation = Conversation(max_turns=6)

    with pytest.raises(TurnError) as raised:
        asyncio.run(pipeline.run(b"clip", conversation, RecordingListener()))

    assert raised.value.code == code
    assert raised.value.turn_id
    assert conversation.history == []


def test_a_tool_call_runs_and_its_result_goes_back_to_the_model() -> None:
    llm = FakeChatModel(rounds=[[DUBAI_CALL], [TextDelta("It will be 31 degrees.")]])
    tool = FakeWeatherTool()

    turn = run(pipeline_with(llm, tool))

    assert turn.reply == "It will be 31 degrees."
    assert tool.calls == [WeatherArguments(city="Dubai", date="2026-10-09")]
    assert turn.tool_results == ['{"temperature_c": 31}']
    assert llm.offered_tools == [["get_weather"], ["get_weather"]]
    assert llm.requests[1][-2:] == [
        ChatMessage(
            role="assistant",
            content="",
            tool_calls=[ToolCall(call_id="call-1", name="get_weather", arguments=DUBAI_CALL.arguments)],
        ),
        ChatMessage(role="tool", content='{"temperature_c": 31}', tool_call_id="call-1"),
    ]


def test_two_calls_in_one_round_both_run_and_answer_in_call_order() -> None:
    abu_dhabi_call = ToolCallDelta(1, "call-2", "get_weather", '{"city": "Abu Dhabi", "date": "2026-10-09"}')
    llm = FakeChatModel(rounds=[[DUBAI_CALL, abu_dhabi_call], [TextDelta("Both are hot.")]])
    tool = FakeWeatherTool()

    turn = run(pipeline_with(llm, tool))

    assert sorted(call.city for call in tool.calls) == ["Abu Dhabi", "Dubai"]
    assert [message.tool_call_id for message in llm.requests[1][-2:]] == ["call-1", "call-2"]
    assert turn.reply == "Both are hot."


def test_a_bad_tool_call_goes_back_to_the_model_instead_of_failing_the_turn() -> None:
    missing_date = ToolCallDelta(0, "call-1", "get_weather", '{"city": "Dubai"}')
    llm = FakeChatModel(rounds=[[missing_date], [TextDelta("Which day?")]])
    tool = FakeWeatherTool()

    turn = run(pipeline_with(llm, tool))

    assert tool.calls == []
    assert ToolFailure.model_validate_json(turn.tool_results[0]).error == "Invalid arguments: date: Field required"
    assert turn.reply == "Which day?"


def test_the_round_after_the_last_tool_round_offers_no_tools() -> None:
    llm = FakeChatModel(rounds=[*[[DUBAI_CALL]] * MAX_TOOL_ROUNDS, [TextDelta("It's sunny.")]])
    tool = FakeWeatherTool()

    turn = run(pipeline_with(llm, tool))

    assert llm.offered_tools == [*[["get_weather"]] * MAX_TOOL_ROUNDS, []]
    assert len(tool.calls) == MAX_TOOL_ROUNDS
    assert turn.reply == "It's sunny."


def test_a_model_that_never_stops_calling_tools_fails_the_turn() -> None:
    llm = FakeChatModel(rounds=[[DUBAI_CALL]])

    with pytest.raises(TurnError) as raised:
        run(pipeline_with(llm, FakeWeatherTool()))

    assert raised.value.code == "llm_failed"
    assert len(llm.requests) == MAX_TOOL_ROUNDS + 1


def test_only_the_answer_after_the_tools_is_spoken_and_marks_llm_first_token() -> None:
    llm = FakeChatModel(rounds=[[TextDelta("Let me check. "), DUBAI_CALL], [TextDelta("It will be 31 degrees.")]])
    tts = FakeTextToSpeech()

    turn = run(pipeline_with(llm, FakeWeatherTool(), tts))

    assert tts.requests == [SpeechRequest("It will be 31 degrees.", None)]
    # The pipeline's clock is read 10 ms apart at: audio_received, stt_done, the first word
    # of round one, the first word of round two. The mark is round two's, 30 ms in.
    assert turn.marks["llm_first_token"] == pytest.approx(30.0)


def test_streaming_speaks_each_sentence_as_it_is_written_and_sends_the_reply_last() -> None:
    llm = FakeChatModel(deltas=("Try the Louvre", " Abu Dhabi. It opens at ", "10.30 today", "!"))
    tts = FakeTextToSpeech()
    listener = RecordingListener()

    turn = asyncio.run(
        pipeline_with(llm, tts=tts, sentence_streaming=True).run(b"clip", Conversation(max_turns=6), listener)
    )

    assert [request.text for request in tts.requests] == ["Try the Louvre Abu Dhabi.", "It opens at 10.30 today!"]
    assert listener.events == [
        "transcript What can we do in Abu Dhabi?",
        f"audio {len(b'RIFFTry the Louvre Abu Dhabi.')} bytes: Try the Louvre Abu Dhabi.",
        f"audio {len(b'RIFFIt opens at 10.30 today!')} bytes: It opens at 10.30 today!",
        "reply Try the Louvre Abu Dhabi. It opens at 10.30 today!",
    ]
    assert turn.reply == "Try the Louvre Abu Dhabi. It opens at 10.30 today!"


def test_streaming_marks_the_first_sentence_and_its_audio() -> None:
    llm = FakeChatModel(deltas=("Try the Louvre Abu Dhabi.", " It opens at ten."))

    marks = run(pipeline_with(llm, sentence_streaming=True)).marks

    assert list(marks) == ["audio_received", "stt_done", "llm_first_token", "first_sentence_ready", "tts_first_byte"]
    assert marks["llm_first_token"] < marks["first_sentence_ready"] < marks["tts_first_byte"]


def test_streaming_speaks_what_the_model_says_before_a_tool_while_it_runs() -> None:
    llm = FakeChatModel(
        rounds=[
            [TextDelta("Let me check the forecast"), DUBAI_CALL],
            [TextDelta("It will be sunny and 34 degrees.")],
        ]
    )
    tts = FakeTextToSpeech()

    turn = asyncio.run(
        pipeline_with(llm, FakeWeatherTool(), tts, sentence_streaming=True).run(
            b"clip", Conversation(max_turns=6), RecordingListener()
        )
    )

    assert [request.text for request in tts.requests] == [
        "Let me check the forecast",
        "It will be sunny and 34 degrees.",
    ]
    assert turn.reply == "Let me check the forecast It will be sunny and 34 degrees."


def test_streaming_reports_a_tts_failure() -> None:
    tts = FakeTextToSpeech(error=TextToSpeechError("down"))

    with pytest.raises(TurnError) as failure:
        run(pipeline_with(FakeChatModel(), tts=tts, sentence_streaming=True))

    assert failure.value.code == "tts_failed"


def test_streaming_without_any_words_is_a_failed_answer() -> None:
    with pytest.raises(TurnError) as failure:
        run(pipeline_with(FakeChatModel(deltas=("  ",)), sentence_streaming=True))

    assert failure.value.code == "llm_failed"


def test_a_reply_carries_the_links_of_the_tours_it_names() -> None:
    found = (
        '{"tours": [{"name": "Louvre Abu Dhabi Ticket", "type": "ticket", "slug": "louvre", '
        '"price": "from AED 70", "accessible": false, "link": "https://me.example/louvre"}], "total": 1}'
    )
    tool = FakeWeatherTool(result=found)
    llm = FakeChatModel(rounds=[[DUBAI_CALL], [TextDelta("Visit the Louvre, from 70 dirhams.")]])
    listener = RecordingListener()

    asyncio.run(pipeline_with(llm, tool, sentence_streaming=True).run(b"clip", Conversation(max_turns=6), listener))

    assert [(link.name, link.url) for link in listener.links] == [("Louvre Abu Dhabi Ticket", "https://me.example/louvre")]
