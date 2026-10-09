import asyncio
from pathlib import Path

import anthropic
import httpx2
from pydantic import BaseModel
import pytest
from sarjy_gateway.claude import ClaudeChatModel, claude_request
from sarjy_gateway.llm import (
    ChatEvent,
    ChatMessage,
    ChatModelError,
    ChatRateLimitedError,
    Finished,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    ToolSpec,
    Usage,
    assemble_tool_calls,
)


FIXTURES = Path(__file__).parent / "fixtures"
MESSAGES = [ChatMessage(role="system", content="Be brief."), ChatMessage(role="user", content="Hello?")]
WEATHER = ToolSpec("get_weather", "The forecast for a UAE city on a date.", {"type": "object", "properties": {}})


class SentRequest(BaseModel, extra="allow"):
    model: str
    max_tokens: int
    system: list[dict[str, object]]
    thinking: dict[str, str]
    output_config: dict[str, str]
    stream: bool


def claude_answering(answer: httpx2.Response, seen: list[httpx2.Request]) -> ClaudeChatModel:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return answer

    transport = httpx2.MockTransport(handler)
    client = anthropic.AsyncAnthropic(
        api_key="test-claude-key", max_retries=0, http_client=anthropic.DefaultAsyncHttpxClient(transport=transport)
    )
    return ClaudeChatModel(client, "claude-haiku-5-5", "low", max_tokens=300, cache_prompt=True)


def recorded(name: str) -> httpx2.Response:
    return httpx2.Response(
        200, content=(FIXTURES / name).read_bytes(), headers={"content-type": "text/event-stream"}
    )


async def collect(model: ClaudeChatModel, tools: list[ToolSpec] | None = None) -> list[ChatEvent]:
    async with model.stream(MESSAGES, tools or []) as events:
        return [event async for event in events]


def test_streams_the_text_of_a_recorded_claude_reply() -> None:
    events = asyncio.run(collect(claude_answering(recorded("claude_text.sse"), [])))

    assert "".join(event.text for event in events if isinstance(event, TextDelta)) == "Hello! How can I help you today?"
    # The input count comes from the message's start, the output count with its end.
    usage = Usage(input_tokens=17, cache_read_tokens=0, cache_write_tokens=0, output_tokens=13)
    assert events[-2:] == [usage, Finished("end_turn")]


# Recorded on 9 Oct 2026: the second of two requests with the same 911-token shared prompt.
def test_a_cached_prompt_is_counted_apart_from_the_fresh_input() -> None:
    events = asyncio.run(collect(claude_answering(recorded("claude_cached_text.sse"), [])))

    usage = Usage(input_tokens=60, cache_read_tokens=911, cache_write_tokens=0, output_tokens=51)
    assert events[-2:] == [usage, Finished("end_turn")]


def test_streams_the_tool_call_of_a_recorded_claude_reply() -> None:
    events = asyncio.run(collect(claude_answering(recorded("claude_tool_call.sse"), []), [WEATHER]))

    (call,) = assemble_tool_calls([event for event in events if isinstance(event, ToolCallDelta)])
    assert (call.name, call.arguments) == ("get_weather", '{"city": "Abu Dhabi", "date": "2026-10-10"}')
    assert events[-1] == Finished("tool_use")


def test_sends_the_model_with_thinking_off_low_effort_and_no_temperature() -> None:
    seen: list[httpx2.Request] = []

    asyncio.run(collect(claude_answering(recorded("claude_text.sse"), seen), [WEATHER]))

    (request,) = seen
    assert request.url.path == "/v1/messages"
    assert request.headers["x-api-key"] == "test-claude-key"
    body = SentRequest.model_validate_json(request.content)
    assert (body.model, body.max_tokens) == ("claude-haiku-5-5", 300)
    assert body.system == [{"type": "text", "text": "Be brief."}]
    assert body.thinking == {"type": "disabled"}
    assert body.output_config == {"effort": "low"}
    assert body.model_extra is not None
    assert "temperature" not in body.model_extra
    assert body.model_extra["tools"] == [
        {"name": "get_weather", "description": "The forecast for a UAE city on a date.", "input_schema": WEATHER.parameters}
    ]


def test_a_tool_round_becomes_tool_use_blocks_and_one_message_of_results() -> None:
    calls = [
        ToolCall(call_id="call-1", name="get_weather", arguments='{"city": "Dubai"}'),
        ToolCall(call_id="call-2", name="get_weather", arguments='{"city": '),
    ]
    messages = [
        *MESSAGES,
        ChatMessage(role="assistant", content="Let me check.", tool_calls=calls),
        ChatMessage(role="tool", content='{"temperature_c": 35}', tool_call_id="call-1"),
        ChatMessage(role="tool", content='{"error": "Invalid arguments"}', tool_call_id="call-2"),
    ]

    request = claude_request(messages, cache_prompt=True)

    assert request.system == [{"type": "text", "text": "Be brief."}]
    assert request.messages[1:] == [
        {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Let me check."},
                {"type": "tool_use", "id": "call-1", "name": "get_weather", "input": {"city": "Dubai"}},
                # Broken arguments were already answered with an error; the call still has to be there.
                {"type": "tool_use", "id": "call-2", "name": "get_weather", "input": {}},
            ],
        },
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "call-1", "content": '{"temperature_c": 35}'},
                {"type": "tool_result", "tool_use_id": "call-2", "content": '{"error": "Invalid arguments"}'},
            ],
        },
    ]


def test_the_cache_point_ends_the_cached_part_of_the_system_text() -> None:
    messages = [
        ChatMessage(role="system", content="The rules.", cache_point=True),
        ChatMessage(role="system", content="Today is Friday."),
        ChatMessage(role="user", content="Hello?"),
    ]

    request = claude_request(messages, cache_prompt=True)

    assert request.system == [
        {"type": "text", "text": "The rules.", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "Today is Friday."},
    ]


def test_without_prompt_caching_no_block_is_marked() -> None:
    messages = [ChatMessage(role="system", content="The rules.", cache_point=True)]

    request = claude_request(messages, cache_prompt=False)

    assert request.system == [{"type": "text", "text": "The rules."}]


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        (httpx2.Response(429, json={"type": "error", "error": {"type": "rate_limit_error", "message": "slow"}}), ChatRateLimitedError),
        (httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": "bad key"}}), ChatModelError),
        (httpx2.Response(529, json={"type": "error", "error": {"type": "overloaded_error", "message": "busy"}}), ChatModelError),
    ],
    ids=["rate limited", "key refused", "overloaded"],
)
def test_claude_failures_become_the_gateways_errors(answer: httpx2.Response, error: type[ChatModelError]) -> None:
    with pytest.raises(error) as raised:
        asyncio.run(collect(claude_answering(answer, [])))

    assert "test-claude-key" not in str(raised.value)
