from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

import anthropic
from anthropic.types import (
    InputJSONDelta,
    MessageParam,
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawMessageDeltaEvent,
    TextBlockParam,
    TextDelta as ClaudeTextDelta,
    ToolParam,
    ToolResultBlockParam,
    ToolUseBlock,
    ToolUseBlockParam,
)
from pydantic import RootModel, ValidationError

from sarjy_gateway.llm import ChatModelError, ChatRateLimitedError, Finished, TextDelta, ToolCallDelta


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, AsyncIterator, Sequence

    from anthropic.lib.streaming import AsyncMessageStream

    from sarjy_gateway.llm import ChatEvent, ChatMessage, ToolCall, ToolSpec


type Effort = Literal["low", "medium", "high"]


# A tool call's arguments, which Claude takes as a JSON object rather than as text.
class ToolInput(RootModel[dict[str, object]]):
    pass


# A request in Claude's shape: the system text sits outside the messages.
@dataclass(frozen=True)
class ClaudeRequest:
    system: str
    messages: list[MessageParam]


# Claude through Anthropic's official SDK (D-63). The rest of the gateway speaks one
# message shape; this adapter translates it to Claude's and Claude's stream back.
class ClaudeChatModel:
    def __init__(self, client: anthropic.AsyncAnthropic, model: str, effort: Effort, max_tokens: int) -> None:
        self._client = client
        self._model = model
        self._effort: Effort = effort
        self._max_tokens = max_tokens

    @asynccontextmanager
    async def stream(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec]
    ) -> AsyncGenerator[AsyncIterator[ChatEvent]]:
        request = claude_request(messages)
        try:
            async with self._client.messages.stream(
                model=self._model,
                max_tokens=self._max_tokens,
                system=request.system or anthropic.omit,
                messages=request.messages,
                tools=[claude_tool(tool) for tool in tools] or anthropic.omit,
                # Thinking delays the first spoken word, and its blocks would have to go
                # back with every tool result; low effort also keeps spoken replies short.
                # Temperature is left out: Haiku 5.5 only takes its default.
                thinking={"type": "disabled"},
                output_config={"effort": self._effort},
            ) as stream:
                yield chat_events(stream)
        except anthropic.RateLimitError as error:
            message = "Claude rate limit reached"
            raise ChatRateLimitedError(message) from error
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as error:
            message = f"Claude request failed: {type(error).__name__}"
            raise ChatModelError(message) from error


# Claude's stream mapped to the gateway's events. A tool call's first block carries its
# id and name, and its JSON input follows in pieces, as with OpenAI-style streams.
async def chat_events(stream: AsyncMessageStream) -> AsyncIterator[ChatEvent]:
    async for event in stream:
        if isinstance(event, RawContentBlockStartEvent) and isinstance(event.content_block, ToolUseBlock):
            yield ToolCallDelta(event.index, event.content_block.id, event.content_block.name, "")
        elif isinstance(event, RawContentBlockDeltaEvent):
            if isinstance(event.delta, ClaudeTextDelta):
                yield TextDelta(event.delta.text)
            elif isinstance(event.delta, InputJSONDelta):
                yield ToolCallDelta(event.index, None, None, event.delta.partial_json)
        elif isinstance(event, RawMessageDeltaEvent) and event.delta.stop_reason is not None:
            yield Finished(event.delta.stop_reason)


def claude_request(messages: Sequence[ChatMessage]) -> ClaudeRequest:
    system: list[str] = []
    converted: list[MessageParam] = []
    # Claude wants every result of one round of tool calls in a single user message.
    results: list[ToolResultBlockParam] = []
    for message in messages:
        if message.role != "tool" and results:
            converted.append({"role": "user", "content": results})
            results = []
        match message.role:
            case "tool":
                results.append(tool_result(message))
            case "system":
                system.append(message.content)
            case "user":
                converted.append({"role": "user", "content": message.content})
            case "assistant":
                converted.append({"role": "assistant", "content": assistant_content(message)})
    if results:
        converted.append({"role": "user", "content": results})
    return ClaudeRequest(system="\n\n".join(system), messages=converted)


def assistant_content(message: ChatMessage) -> str | list[TextBlockParam | ToolUseBlockParam]:
    if not message.tool_calls:
        return message.content
    blocks: list[TextBlockParam | ToolUseBlockParam] = []
    if message.content.strip():
        blocks.append({"type": "text", "text": message.content})
    blocks += [tool_use(call) for call in message.tool_calls]
    return blocks


def tool_use(call: ToolCall) -> ToolUseBlockParam:
    return {"type": "tool_use", "id": call.call_id, "name": call.name, "input": tool_input(call.arguments)}


# A call whose arguments weren't valid JSON has already been answered with an error
# result; Claude only needs the call itself to be there.
def tool_input(arguments: str) -> dict[str, object]:
    try:
        return ToolInput.model_validate_json(arguments).root
    except ValidationError:
        return {}


def tool_result(message: ChatMessage) -> ToolResultBlockParam:
    return {"type": "tool_result", "tool_use_id": message.tool_call_id or "", "content": message.content}


def claude_tool(tool: ToolSpec) -> ToolParam:
    return {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}
