import asyncio
from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Protocol
import uuid

from sarjy_gateway.llm import (
    ChatMessage,
    ChatModelError,
    ChatRateLimitedError,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    assemble_tool_calls,
)
from sarjy_gateway.stt import RateLimitedError, SpeechToTextError
from sarjy_gateway.timeline import Timeline
from sarjy_gateway.tts import TextToSpeechError


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Sequence

    from sarjy_gateway.llm import ChatEvent, ChatModel, ToolSpec
    from sarjy_gateway.messages import ErrorCode
    from sarjy_gateway.stt import SpeechToText
    from sarjy_gateway.tools import Toolbox
    from sarjy_gateway.tts import TextToSpeech


logger = logging.getLogger(__name__)

# How many rounds of tool calls one turn may make. One more round follows that offers no
# tools, so the model has to answer with what it has (D-57).
MAX_TOOL_ROUNDS = 3


class TurnListener(Protocol):
    async def transcript(self, turn_id: str, text: str) -> None: ...

    async def reply(self, turn_id: str, text: str) -> None: ...

    async def audio(self, turn_id: str, wav: bytes) -> None: ...


class TurnError(Exception):
    def __init__(self, code: ErrorCode, turn_id: str) -> None:
        super().__init__(f"turn {turn_id} failed: {code}")
        self.code: ErrorCode = code
        self.turn_id = turn_id


# One WebSocket session: its recent turns and the voice the traveller chose.
@dataclass
class Conversation:
    max_turns: int
    voice: str | None = None
    history: list[ChatMessage] = field(default_factory=list[ChatMessage])

    def remember(self, user: str, assistant: str) -> None:
        self.history += [ChatMessage(role="user", content=user), ChatMessage(role="assistant", content=assistant)]
        # Only recent turns go to the LLM: older context costs tokens and latency (D-15).
        self.history = self.history[-2 * self.max_turns :]


@dataclass(frozen=True)
class CompletedTurn:
    turn_id: str
    transcript: str
    reply: str
    marks: dict[str, float]
    # What tools returned this turn, as the LLM saw it. Kept so a later check can test
    # spoken prices and temperatures against it (optional deep dive).
    tool_results: list[str]


# The model's spoken answer, and what its tools returned on the way.
@dataclass(frozen=True)
class Answer:
    reply: str
    tool_results: list[str]


# One request to the model: either text to speak, or tool calls to run first.
@dataclass(frozen=True)
class ModelRound:
    text: str
    tool_calls: list[ToolCall]
    # Clock reading at the first piece of text, which becomes `llm_first_token` if this
    # round is the spoken answer.
    first_text_at: float | None


# Experiment 1's baseline: the whole reply is collected before any of it is spoken.
class TurnPipeline:
    # `system_prompt` is awaited for every turn, so its date and catalogue are current.
    def __init__(
        self,
        stt: SpeechToText,
        llm: ChatModel,
        tts: TextToSpeech,
        toolbox: Toolbox,
        *,
        system_prompt: Callable[[], Awaitable[str]],
        clock: Callable[[], float],
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._toolbox = toolbox
        self._system_prompt = system_prompt
        self._clock = clock

    async def run(self, audio: bytes, conversation: Conversation, listener: TurnListener) -> CompletedTurn:
        turn_id = uuid.uuid7().hex
        timeline = Timeline(self._clock)
        timeline.mark("audio_received")
        # The prompt is built while the speech is transcribed, so fetching SayTech's
        # context on a cache miss adds nothing to the wait.
        prompt = asyncio.ensure_future(self._system_prompt())
        try:
            transcript = await self._transcribe(audio, turn_id)
            timeline.mark("stt_done")
            await listener.transcript(turn_id, transcript)
            system = await prompt
        finally:
            # Only matters when the turn ends early; a finished task ignores it.
            prompt.cancel()
        answer = await self._answer(system, transcript, conversation, timeline, turn_id)
        timeline.mark("first_sentence_ready")
        await listener.reply(turn_id, answer.reply)
        wav = await self._speak(answer.reply, conversation.voice, turn_id)
        timeline.mark("tts_first_byte")
        await listener.audio(turn_id, wav)
        conversation.remember(transcript, answer.reply)
        turn = CompletedTurn(turn_id, transcript, answer.reply, timeline.marks, answer.tool_results)
        logger.info("turn %(turn_id)s completed", {"turn_id": turn_id, "marks": turn.marks})
        return turn

    async def _transcribe(self, audio: bytes, turn_id: str) -> str:
        try:
            transcript = await self._stt.transcribe(audio)
        except RateLimitedError as error:
            raise TurnError(code="rate_limited", turn_id=turn_id) from error
        except SpeechToTextError as error:
            raise TurnError(code="stt_failed", turn_id=turn_id) from error
        if not transcript:
            raise TurnError(code="no_speech", turn_id=turn_id)
        return transcript

    # Asks the model, runs any tools it calls and asks again with their results, until it
    # answers in words. Only this turn's tool messages are sent; history keeps the replies.
    async def _answer(
        self, system: str, transcript: str, conversation: Conversation, timeline: Timeline, turn_id: str
    ) -> Answer:
        messages = [
            ChatMessage(role="system", content=system),
            *conversation.history,
            ChatMessage(role="user", content=transcript),
        ]
        tool_results: list[str] = []
        for round_number in range(MAX_TOOL_ROUNDS + 1):
            tools = self._toolbox.specs if round_number < MAX_TOOL_ROUNDS else []
            model_round = await self._ask(messages, tools, turn_id)
            if not model_round.tool_calls:
                return self._spoken(model_round, tool_results, timeline, turn_id)
            results = await self._toolbox.run_all(model_round.tool_calls, turn_id)
            messages.append(ChatMessage(role="assistant", content=model_round.text, tool_calls=model_round.tool_calls))
            for call, result in zip(model_round.tool_calls, results, strict=True):
                messages.append(ChatMessage(role="tool", content=result, tool_call_id=call.call_id))
            tool_results += results
        # Still calling tools in the round that offered none.
        raise TurnError(code="llm_failed", turn_id=turn_id)

    async def _ask(self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec], turn_id: str) -> ModelRound:
        try:
            async with self._llm.stream(messages, tools) as events:
                return await self._read(events)
        except ChatRateLimitedError as error:
            raise TurnError(code="rate_limited", turn_id=turn_id) from error
        except ChatModelError as error:
            raise TurnError(code="llm_failed", turn_id=turn_id) from error

    async def _read(self, events: AsyncIterator[ChatEvent]) -> ModelRound:
        parts: list[str] = []
        call_pieces: list[ToolCallDelta] = []
        first_text_at: float | None = None
        async for event in events:
            if isinstance(event, TextDelta):
                first_text_at = first_text_at if first_text_at is not None else self._clock()
                parts.append(event.text)
            elif isinstance(event, ToolCallDelta):
                call_pieces.append(event)
        return ModelRound("".join(parts), assemble_tool_calls(call_pieces), first_text_at)

    @staticmethod
    def _spoken(model_round: ModelRound, tool_results: list[str], timeline: Timeline, turn_id: str) -> Answer:
        reply = model_round.text.strip()
        if not reply or model_round.first_text_at is None:
            raise TurnError(code="llm_failed", turn_id=turn_id)
        # The first word of the answer that is spoken, after any tool rounds (D-57).
        timeline.mark("llm_first_token", at=model_round.first_text_at)
        return Answer(reply, tool_results)

    async def _speak(self, reply: str, voice: str | None, turn_id: str) -> bytes:
        try:
            return await self._tts.synthesize(reply, voice)
        except TextToSpeechError as error:
            raise TurnError(code="tts_failed", turn_id=turn_id) from error
