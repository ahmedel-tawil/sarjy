from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Protocol

import httpx2
from pydantic import BaseModel, ValidationError


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Sequence
    from contextlib import AbstractAsyncContextManager

    from pydantic import SecretStr


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class TextDelta:
    text: str


# Tool calls arrive in pieces: the first piece names the function, later pieces add to
# its JSON arguments. `index` says which call a piece belongs to (M2.5 assembles them).
@dataclass(frozen=True)
class ToolCallDelta:
    index: int
    call_id: str | None
    name: str | None
    arguments: str


@dataclass(frozen=True)
class Finished:
    reason: str


type ChatEvent = TextDelta | ToolCallDelta | Finished


class ChatModelError(RuntimeError):
    pass


class ChatRateLimitedError(ChatModelError):
    pass


# Used as `async with model.stream(messages) as events:`; the HTTP response stays open
# exactly as long as the block, even if the caller stops reading early.
class ChatModel(Protocol):
    def stream(self, messages: Sequence[ChatMessage]) -> AbstractAsyncContextManager[AsyncIterator[ChatEvent]]: ...


# The OpenAI-compatible streaming chunk, reduced to the fields Sarjy reads. Providers add
# others (usage, reasoning); Pydantic ignores them.
class FunctionDelta(BaseModel):
    name: str | None = None
    arguments: str | None = None


class ToolCallChunk(BaseModel):
    index: int
    id: str | None = None
    function: FunctionDelta | None = None


class Delta(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCallChunk] | None = None


class Choice(BaseModel):
    delta: Delta
    finish_reason: str | None = None


class StreamChunk(BaseModel):
    choices: list[Choice]


@dataclass(frozen=True)
class GenerationOptions:
    model: str
    temperature: float
    max_tokens: int
    reasoning_effort: str | None


# One adapter for every OpenAI-compatible API: Groq, Cerebras and Gemini differ only in
# base URL, key and model (experiment 4), which also leaves room for a fallback provider.
class OpenAiCompatibleChatModel:
    def __init__(self, client: httpx2.AsyncClient, base_url: str, api_key: SecretStr, options: GenerationOptions) -> None:
        self._client = client
        self._url = f"{base_url.rstrip('/')}/chat/completions"
        self._api_key = api_key
        self._options = options

    @asynccontextmanager
    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncGenerator[AsyncIterator[ChatEvent]]:
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        # Network errors while the caller reads the events also surface here.
        try:
            async with self._client.stream("POST", self._url, json=self._body(messages), headers=headers) as response:
                raise_for_provider_status(response)
                yield events_from(response)
        except httpx2.HTTPError as error:
            message = f"chat model request failed: {type(error).__name__}"
            raise ChatModelError(message) from error

    def _body(self, messages: Sequence[ChatMessage]) -> dict[str, object]:
        body: dict[str, object] = {
            "model": self._options.model,
            "messages": [{"role": message.role, "content": message.content} for message in messages],
            "stream": True,
            "temperature": self._options.temperature,
            "max_tokens": self._options.max_tokens,
        }
        if self._options.reasoning_effort is not None:
            body["reasoning_effort"] = self._options.reasoning_effort
        return body


def raise_for_provider_status(response: httpx2.Response) -> None:
    if response.status_code == httpx2.codes.TOO_MANY_REQUESTS:
        message = "chat model rate limit reached"
        raise ChatRateLimitedError(message)
    if response.is_error:
        message = f"chat model request failed with HTTP {response.status_code}"
        raise ChatModelError(message)


async def events_from(response: httpx2.Response) -> AsyncIterator[ChatEvent]:
    async for line in response.aiter_lines():
        payload = sse_data(line)
        if payload == "[DONE]":
            return
        if payload is not None:
            for event in events_in(parse_chunk(payload)):
                yield event


# Server-sent events: each event is a "data: ..." line; anything else is a keep-alive,
# a comment or the blank line between events.
def sse_data(line: str) -> str | None:
    if not line.startswith("data:"):
        return None
    return line.removeprefix("data:").strip()


def parse_chunk(payload: str) -> StreamChunk:
    try:
        return StreamChunk.model_validate_json(payload)
    except ValidationError as error:
        message = "chat model sent a chunk that is not a completion delta"
        raise ChatModelError(message) from error


def events_in(chunk: StreamChunk) -> list[ChatEvent]:
    events: list[ChatEvent] = []
    for choice in chunk.choices:
        if choice.delta.content:
            events.append(TextDelta(choice.delta.content))
        for call in choice.delta.tool_calls or []:
            function = call.function or FunctionDelta()
            events.append(ToolCallDelta(call.index, call.id, function.name, function.arguments or ""))
        if choice.finish_reason is not None:
            events.append(Finished(choice.finish_reason))
    return events
