import asyncio
from pathlib import Path

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
    ToolCallDelta,
    sse_data,
)


FIXTURES = Path(__file__).parent / "fixtures"
API_KEY = "test-llm-key"
OPTIONS = GenerationOptions(model="qwen/qwen3.8-27b", temperature=0.5, max_tokens=300, reasoning_effort="none")
MESSAGES = [ChatMessage(role="system", content="Be brief."), ChatMessage(role="user", content="Hello?")]


class RequestBody(BaseModel):
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


async def collect(model: OpenAiCompatibleChatModel) -> list[ChatEvent]:
    async with model.stream(MESSAGES) as events:
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
