from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Protocol
import uuid

from sarjy_gateway.llm import ChatMessage, ChatModelError, ChatRateLimitedError, TextDelta
from sarjy_gateway.prompts import SYSTEM_PROMPT
from sarjy_gateway.stt import RateLimitedError, SpeechToTextError
from sarjy_gateway.timeline import Timeline
from sarjy_gateway.tts import TextToSpeechError


if TYPE_CHECKING:
    from collections.abc import Callable

    from sarjy_gateway.llm import ChatModel
    from sarjy_gateway.messages import ErrorCode
    from sarjy_gateway.stt import SpeechToText
    from sarjy_gateway.tts import TextToSpeech


logger = logging.getLogger(__name__)


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
    # What tools returned this turn, as the LLM saw it; empty until M2.5. Kept so a later
    # check can test spoken prices and temperatures against it (optional deep dive).
    tool_results: list[str]


# Experiment 1's baseline: the whole reply is collected before any of it is spoken.
class TurnPipeline:
    def __init__(self, stt: SpeechToText, llm: ChatModel, tts: TextToSpeech, clock: Callable[[], float]) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._clock = clock

    async def run(self, audio: bytes, conversation: Conversation, listener: TurnListener) -> CompletedTurn:
        turn_id = uuid.uuid7().hex
        timeline = Timeline(self._clock)
        timeline.mark("audio_received")
        transcript = await self._transcribe(audio, turn_id)
        timeline.mark("stt_done")
        await listener.transcript(turn_id, transcript)
        reply = await self._answer(transcript, conversation, timeline, turn_id)
        timeline.mark("first_sentence_ready")
        await listener.reply(turn_id, reply)
        wav = await self._speak(reply, conversation.voice, turn_id)
        timeline.mark("tts_first_byte")
        await listener.audio(turn_id, wav)
        conversation.remember(transcript, reply)
        turn = CompletedTurn(turn_id, transcript, reply, timeline.marks, [])
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

    async def _answer(self, transcript: str, conversation: Conversation, timeline: Timeline, turn_id: str) -> str:
        messages = [
            ChatMessage(role="system", content=SYSTEM_PROMPT),
            *conversation.history,
            ChatMessage(role="user", content=transcript),
        ]
        parts: list[str] = []
        try:
            async with self._llm.stream(messages) as events:
                async for event in events:
                    if isinstance(event, TextDelta):
                        if not parts:
                            timeline.mark("llm_first_token")
                        parts.append(event.text)
        except ChatRateLimitedError as error:
            raise TurnError(code="rate_limited", turn_id=turn_id) from error
        except ChatModelError as error:
            raise TurnError(code="llm_failed", turn_id=turn_id) from error
        reply = "".join(parts).strip()
        if not reply:
            raise TurnError(code="llm_failed", turn_id=turn_id)
        return reply

    async def _speak(self, reply: str, voice: str | None, turn_id: str) -> bytes:
        try:
            return await self._tts.synthesize(reply, voice)
        except TextToSpeechError as error:
            raise TurnError(code="tts_failed", turn_id=turn_id) from error
