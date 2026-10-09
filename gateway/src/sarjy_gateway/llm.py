from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Literal, NotRequired, Protocol, TypedDict

import httpx2
from pydantic import BaseModel, Field, ValidationError


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Sequence
    from contextlib import AbstractAsyncContextManager

    from pydantic import SecretStr


class ToolCall(BaseModel):
    call_id: str
    name: str
    # The JSON arguments exactly as the model wrote them; the tool validates them.
    arguments: str


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    # Set on an assistant message that asks for tools, and on the tool message that answers
    # one of those calls.
    tool_calls: list[ToolCall] = Field(default_factory=list[ToolCall])
    tool_call_id: str | None = None
    # Set on the last message that is the same from request to request: a provider that
    # caches prompts may cache everything up to and including it (D-93).
    cache_point: bool = False


# What the model is told about one tool: its name, when to use it, and the JSON schema of
# its arguments.
@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, object]


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


# What one request cost, by the provider's own count: experiment 5 compares input tokens
# (M3.9). With prompt caching, `input_tokens` is only the part read fresh; the cached part
# is counted apart, as read from the cache or written to it (D-93).
@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    output_tokens: int


type ChatEvent = TextDelta | ToolCallDelta | Finished | Usage


class ChatModelError(RuntimeError):
    pass


class ChatRateLimitedError(ChatModelError):
    pass


# Used as `async with model.stream(messages, tools) as events:`; the HTTP response stays
# open exactly as long as the block, even if the caller stops reading early.
class ChatModel(Protocol):
    def stream(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> AbstractAsyncContextManager[AsyncIterator[ChatEvent]]: ...


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


class ChunkUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


# Groq reports usage on the last chunk under its own key; others under `usage`.
class GroqExtras(BaseModel):
    usage: ChunkUsage | None = None


class StreamChunk(BaseModel):
    choices: list[Choice]
    usage: ChunkUsage | None = None
    x_groq: GroqExtras | None = None


# Some failures arrive inside the stream instead of as an HTTP error, such as Groq
# rejecting a tool call that doesn't match the tool's schema (`tool_use_failed`).
class StreamFailure(BaseModel):
    message: str


class StreamError(BaseModel):
    error: StreamFailure


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
    async def stream(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> AsyncGenerator[AsyncIterator[ChatEvent]]:
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        body = self._body(messages, tools)
        # Network errors while the caller reads the events also surface here.
        try:
            async with self._client.stream("POST", self._url, json=body, headers=headers) as response:
                raise_for_provider_status(response)
                yield events_from(response)
        except httpx2.HTTPError as error:
            message = f"chat model request failed: {type(error).__name__}"
            raise ChatModelError(message) from error

    def _body(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]) -> dict[str, object]:
        body: dict[str, object] = {
            "model": self._options.model,
            "messages": [wire_message(message) for message in messages],
            "stream": True,
            "temperature": self._options.temperature,
            "max_tokens": self._options.max_tokens,
        }
        # No tools at all means a plain answer, so the key is left out rather than empty.
        if tools:
            body["tools"] = [wire_tool(tool) for tool in tools]
        if self._options.reasoning_effort is not None:
            body["reasoning_effort"] = self._options.reasoning_effort
        return body


logger = logging.getLogger(__name__)


# Asks the first model and, if it fails before saying anything (a rate limit, a refused or
# deactivated key, a server or network error, no key at all), sends the same request to
# the second. Once words have arrived the answer can't be swapped, so later failures are
# the turn's (D-63).
class FallbackChatModel:
    def __init__(self, first: ChatModel, second: ChatModel, first_name: str, second_name: str) -> None:
        self._first = first
        self._second = second
        self._first_name = first_name
        self._second_name = second_name

    @asynccontextmanager
    async def stream(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> AsyncGenerator[AsyncIterator[ChatEvent]]:
        # The stack closes whichever stream opened, once the caller's block ends.
        async with AsyncExitStack() as stack:
            try:
                events = await stack.enter_async_context(self._first.stream(messages, tools))
                answered_by = self._first_name
            except ChatModelError as error:
                logger.warning(
                    "%(first)s failed before answering, asking %(second)s",
                    {"first": self._first_name, "second": self._second_name, "error": str(error)},
                )
                events = await stack.enter_async_context(self._second.stream(messages, tools))
                answered_by = self._second_name
            logger.info("chat answered by %(model)s", {"model": answered_by})
            yield events


class MissingChatModel:
    def stream(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> AbstractAsyncContextManager[AsyncIterator[ChatEvent]]:
        message = f"SARJY_LLM_API_KEY is not set; cannot answer {len(messages)} messages with {len(tools)} tools"
        raise ChatModelError(message)


# The request shapes of the OpenAI-compatible API, as sent on the wire.
class WireFunctionCall(TypedDict):
    name: str
    arguments: str


class WireToolCall(TypedDict):
    id: str
    type: Literal["function"]
    function: WireFunctionCall


class WireMessage(TypedDict):
    role: str
    content: str
    tool_calls: NotRequired[list[WireToolCall]]
    tool_call_id: NotRequired[str]


class WireFunction(TypedDict):
    name: str
    description: str
    parameters: dict[str, object]


class WireTool(TypedDict):
    type: Literal["function"]
    function: WireFunction


def wire_message(message: ChatMessage) -> WireMessage:
    wire = WireMessage(role=message.role, content=message.content)
    if message.tool_calls:
        wire["tool_calls"] = [
            WireToolCall(
                id=call.call_id, type="function", function=WireFunctionCall(name=call.name, arguments=call.arguments)
            )
            for call in message.tool_calls
        ]
    if message.tool_call_id is not None:
        wire["tool_call_id"] = message.tool_call_id
    return wire


def wire_tool(tool: ToolSpec) -> WireTool:
    return WireTool(
        type="function",
        function=WireFunction(name=tool.name, description=tool.description, parameters=tool.parameters),
    )


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
        raise ChatModelError(chunk_problem(payload)) from error


def chunk_problem(payload: str) -> str:
    try:
        failure = StreamError.model_validate_json(payload).error
    except ValidationError:
        return "chat model sent a chunk that is not a completion delta"
    return f"chat model failed mid-stream: {failure.message}"


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
    usage = chunk.usage or (chunk.x_groq.usage if chunk.x_groq is not None else None)
    if usage is not None:
        # Only Claude's prompt is cached on purpose (D-93); Groq's cache counts aren't read.
        events.append(
            Usage(
                input_tokens=usage.prompt_tokens,
                cache_read_tokens=0,
                cache_write_tokens=0,
                output_tokens=usage.completion_tokens,
            )
        )
    return events


# Rebuilds whole tool calls from their streamed pieces: the first piece of each call
# carries its id and name, and the arguments arrive as JSON text split across pieces.
def assemble_tool_calls(deltas: Sequence[ToolCallDelta]) -> list[ToolCall]:
    ids: dict[int, str] = {}
    names: dict[int, str] = {}
    arguments: dict[int, str] = {}
    for delta in deltas:
        if delta.call_id:
            ids[delta.index] = delta.call_id
        if delta.name:
            names[delta.index] = delta.name
        arguments[delta.index] = arguments.get(delta.index, "") + delta.arguments
    calls: list[ToolCall] = []
    for index in sorted(arguments):
        if index not in ids or index not in names:
            message = f"chat model sent tool call {index} without an id or a name"
            raise ChatModelError(message)
        # A tool without arguments may stream none; "{}" still validates as an empty object.
        calls.append(ToolCall(call_id=ids[index], name=names[index], arguments=arguments[index] or "{}"))
    return calls
