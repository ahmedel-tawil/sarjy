import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

import httpx2
from pydantic import BaseModel, SecretStr
import pytest
from sarjy_gateway.llm import (
    ChatEvent,
    ChatMessage,
    ChatModelError,
    ChatRateLimitedError,
    Finished,
    GenerationOptions,
    OpenAiCompatibleChatModel,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    ToolSpec,
    assemble_tool_calls,
    sse_data,
)


if TYPE_CHECKING:
    from collections.abc import Sequence


FIXTURES = Path(__file__).parent / "fixtures"
API_KEY = "test-llm-key"
OPTIONS = GenerationOptions(model="qwen/qwen3.8-27b", temperature=0.5, max_tokens=300, reasoning_effort="none")
MESSAGES = [ChatMessage(role="system", content="Be brief."), ChatMessage(role="user", content="Hello?")]


class ToolRequestBody(BaseModel):
    messages: list[dict[str, object]]
    tools: list[dict[str, object]]


class RequestBody(BaseModel, extra="allow"):
    model: str
    messages: list[ChatMessage]
    stream: bool
    temperature: float
    max_tokens: int
    reasoning_effort: str | None = None


def model_answering(answer: httpx2.Response, seen: list[httpx2.Request]) -> OpenAiCompatibleChatModel:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return answer

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return OpenAiCompatibleChatModel(client, "https://api.groq.com/openai/v1", SecretStr(API_KEY), OPTIONS)


async def collect(
    model: OpenAiCompatibleChatModel,
    messages: Sequence[ChatMessage] = MESSAGES,
    tools: Sequence[ToolSpec] = (),
) -> list[ChatEvent]:
    async with model.stream(messages, tools) as events:
        return [event async for event in events]


def recorded(name: str) -> httpx2.Response:
    return httpx2.Response(200, content=(FIXTURES / name).read_bytes())


def test_streams_the_text_of_a_recorded_groq_reply() -> None:
    events = asyncio.run(collect(model_answering(recorded("groq_text.sse"), [])))

    text = "".join(event.text for event in events if isinstance(event, TextDelta))
    assert text == "Hello, and welcome to Dubai!"
    assert events[-1] == Finished("stop")


def test_streams_the_tool_call_of_a_recorded_groq_reply() -> None:
    events = asyncio.run(collect(model_answering(recorded("groq_tool_call.sse"), [])))

    assert events == [
        ToolCallDelta(0, "5nd4axs1q", "get_weather", '{"city":"Abu Dhabi","date":"2026-10-09"}'),
        Finished("tool_calls"),
    ]


def test_sends_model_messages_options_and_key() -> None:
    seen: list[httpx2.Request] = []

    asyncio.run(collect(model_answering(recorded("groq_text.sse"), seen)))

    (request,) = seen
    assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
    assert request.headers["Authorization"] == f"Bearer {API_KEY}"
    assert RequestBody.model_validate_json(request.content) == RequestBody(
        model="qwen/qwen3.8-27b",
        messages=MESSAGES,
        stream=True,
        temperature=0.5,
        max_tokens=300,
        reasoning_effort="none",
    )
    # Nothing beyond the fields above was sent: in particular, no empty "tools" list.
    assert RequestBody.model_validate_json(request.content).model_extra == {}


def test_sends_tools_and_tool_messages_in_the_openai_format() -> None:
    seen: list[httpx2.Request] = []
    call = ToolCall(call_id="call-1", name="get_weather", arguments='{"city": "Dubai"}')
    messages = [
        *MESSAGES,
        ChatMessage(role="assistant", content="", tool_calls=[call]),
        ChatMessage(role="tool", content='{"temperature_c": 31}', tool_call_id="call-1"),
    ]
    weather = ToolSpec("get_weather", "The forecast for a UAE city.", {"type": "object", "properties": {}})

    asyncio.run(collect(model_answering(recorded("groq_text.sse"), seen), messages, [weather]))

    body = ToolRequestBody.model_validate_json(seen[0].content)
    assert body.messages[2:] == [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"id": "call-1", "type": "function", "function": {"name": "get_weather", "arguments": '{"city": "Dubai"}'}}
            ],
        },
        {"role": "tool", "content": '{"temperature_c": 31}', "tool_call_id": "call-1"},
    ]
    assert body.tools == [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "The forecast for a UAE city.",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]


def test_tool_calls_are_assembled_from_their_streamed_pieces() -> None:
    pieces = [
        ToolCallDelta(0, "call-a", "search_tours", '{"city": "Ab'),
        ToolCallDelta(1, "call-b", "get_weather", ""),
        ToolCallDelta(0, None, None, 'u Dhabi"}'),
        ToolCallDelta(1, None, None, '{"city": "Dubai"}'),
        ToolCallDelta(2, "call-c", "forget_me", ""),
    ]

    assert assemble_tool_calls(pieces) == [
        ToolCall(call_id="call-a", name="search_tours", arguments='{"city": "Abu Dhabi"}'),
        ToolCall(call_id="call-b", name="get_weather", arguments='{"city": "Dubai"}'),
        ToolCall(call_id="call-c", name="forget_me", arguments="{}"),
    ]


def test_a_tool_call_without_a_name_is_a_model_error() -> None:
    with pytest.raises(ChatModelError):
        assemble_tool_calls([ToolCallDelta(0, "call-a", None, "{}")])


def test_rate_limits_are_reported_as_their_own_error() -> None:
    with pytest.raises(ChatRateLimitedError):
        asyncio.run(collect(model_answering(httpx2.Response(429, text="slow down"), [])))


@pytest.mark.parametrize(
    "answer",
    [httpx2.Response(500, text="overloaded"), httpx2.Response(200, content=b'data: {"not": "a chunk"}\n\n')],
    ids=["server error", "malformed chunk"],
)
def test_failures_raise_chat_model_errors_without_the_key(answer: httpx2.Response) -> None:
    with pytest.raises(ChatModelError) as raised:
        asyncio.run(collect(model_answering(answer, [])))

    assert API_KEY not in str(raised.value)
    assert not isinstance(raised.value, ChatRateLimitedError)


@pytest.mark.parametrize(
    ("line", "expected"),
    [("data: {}", "{}"), ("data: [DONE]", "[DONE]"), ("", None), (": keep-alive", None)],
    ids=["event", "end of stream", "blank line between events", "comment"],
)
def test_sse_data_reads_only_data_lines(line: str, expected: str | None) -> None:
    assert sse_data(line) == expected
