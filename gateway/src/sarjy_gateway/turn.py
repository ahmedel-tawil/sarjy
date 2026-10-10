import asyncio
from contextlib import suppress
from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING, Protocol
import uuid

from sarjy_gateway.activity import activity_of
from sarjy_gateway.conversation_store import SessionId
from sarjy_gateway.identity import UserId, new_user_id
from sarjy_gateway.links import tour_links
from sarjy_gateway.llm import (
    ChatMessage,
    ChatModelError,
    ChatRateLimitedError,
    TextDelta,
    ToolCall,
    ToolCallDelta,
    Usage,
    assemble_tool_calls,
)
from sarjy_gateway.sentences import SentenceChunker, speakable
from sarjy_gateway.stt import RateLimitedError, SpeechToTextError
from sarjy_gateway.timeline import Timeline
from sarjy_gateway.tools import Tool, failed
from sarjy_gateway.tts import TextToSpeechError


if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Awaitable, Callable, Mapping, Sequence

    from sarjy_gateway.llm import ChatEvent, ChatModel, ToolSpec
    from sarjy_gateway.messages import ErrorCode, TourLink
    from sarjy_gateway.prompts import Prompt
    from sarjy_gateway.stt import SpeechToText
    from sarjy_gateway.tools import Toolbox
    from sarjy_gateway.tts import TextToSpeech


logger = logging.getLogger(__name__)

# How many rounds of tool calls one turn may make. One more round follows that offers no
# tools, so the model has to answer with what it has (D-57).
MAX_TOOL_ROUNDS = 3

# Saving or forgetting a fact gives the model nothing it needs for its answer (D-95).
FACT_TOOLS = frozenset({"remember_fact", "forget_fact"})


class TurnListener(Protocol):
    async def transcript(self, turn_id: str, text: str) -> None: ...

    # What Sarjy is doing while a tool runs, such as "Looking for tours in Dubai" (D-94).
    async def activity(self, turn_id: str, text: str) -> None: ...

    # `links` are the pages of the tours the reply names (D-90).
    async def reply(self, turn_id: str, text: str, links: list[TourLink]) -> None: ...

    # `text` is what the audio says: the whole reply, or one sentence when streaming.
    async def audio(self, turn_id: str, text: str, wav: bytes) -> None: ...


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
    # The most recent turns, each its question, the tool calls it made and its reply.
    recent: list[list[ChatMessage]] = field(default_factory=list[list[ChatMessage]])
    # Set once the visit is stored; None when the database is unavailable, and then turns
    # are spoken but not saved.
    session_id: SessionId | None = None
    # The browser's id; the voice socket sets it, and tests and scripts get a throwaway one.
    user_id: UserId = field(default_factory=new_user_id)
    # What Sarjy knows about this user, loaded when the visit starts and kept current by the
    # memory tools, so each turn's prompt has it without reading the database (D-67).
    facts: dict[str, str] = field(default_factory=dict[str, str])
    # Tools that belong to this visit, on top of the shared ones: the user's memory tools.
    tools: list[Tool] = field(default_factory=list[Tool])
    # Where the visit comes from and how many turns it has taken, for the limits (D-72).
    client_ip: str = "unknown"
    turns_taken: int = 0

    @property
    def history(self) -> list[ChatMessage]:
        return [message for turn in self.recent for message in turn]

    # Tool calls and their results stay in the history: without them, a later turn saw
    # prices it had said with nothing behind them and took them back as made up, even with
    # the calls kept and a stand-in for each result (D-100).
    def remember(self, user: str, assistant: str, tool_calls: Sequence[ToolCall], tool_results: Sequence[str]) -> None:
        turn = [ChatMessage(role="user", content=user)]
        if tool_calls:
            turn.append(ChatMessage(role="assistant", content="", tool_calls=list(tool_calls)))
            turn += [
                ChatMessage(role="tool", content=result, tool_call_id=call.call_id)
                for call, result in zip(tool_calls, tool_results, strict=True)
            ]
        turn.append(ChatMessage(role="assistant", content=assistant))
        # Only recent turns go to the LLM: older context costs tokens and latency (D-15).
        # Whole turns are dropped, so a tool call never loses its result.
        self.recent = [*self.recent, turn][-self.max_turns :]


@dataclass(frozen=True)
class CompletedTurn:
    turn_id: str
    transcript: str
    reply: str
    marks: dict[str, float]
    # What tools returned this turn, as the LLM saw it. Kept so a later check can test
    # spoken prices and temperatures against it (optional deep dive).
    tool_results: list[str]


# The model's spoken answer, the tools it called on the way and what they returned.
@dataclass(frozen=True)
class Answer:
    reply: str
    tool_calls: list[ToolCall]
    tool_results: list[str]


# One request to the model: either text to speak, or tool calls to run first.
@dataclass(frozen=True)
class ModelRound:
    text: str
    tool_calls: list[ToolCall]
    # Clock reading at the first piece of text, which becomes `llm_first_token` if this
    # round is the spoken answer.
    first_text_at: float | None
    # The provider's token count for the round, when it gave one (M3.9).
    usage: Usage | None = None


# The round that answered in words, and what tools returned on the way.
@dataclass(frozen=True)
class Conversed:
    final: ModelRound
    tool_calls: list[ToolCall]
    tool_results: list[str]


@dataclass(frozen=True)
class SpokenTurn:
    turn_id: str
    voice: str | None
    timeline: Timeline


# Speaks a turn's sentences in order while the model is still writing: each complete
# sentence goes to TTS at once, and its audio is sent as soon as it is ready (D-76). One
# sentence at a time keeps the order, and Kokoro synthesises faster than it speaks.
class SentenceSpeaker:
    def __init__(self, tts: TextToSpeech, listener: TurnListener, turn: SpokenTurn) -> None:
        self._tts = tts
        self._listener = listener
        self._turn = turn
        self._chunker = SentenceChunker()
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._sentences: list[str] = []
        self._task = asyncio.ensure_future(self._speak_in_order())

    # A piece of the model's text, as it streams in.
    def heard(self, piece: str) -> None:
        if not self._turn.timeline.has("llm_first_token"):
            self._turn.timeline.mark("llm_first_token")
        self._say(self._chunker.add(piece))

    # Text left without a final full stop is spoken when the model's round ends, before
    # any tools run.
    def round_ended(self) -> None:
        self._say(self._chunker.flush())

    # Waits for the last sentence to be sent and returns everything spoken.
    async def finish(self) -> list[str]:
        self._queue.put_nowait(None)
        await self._task
        return list(self._sentences)

    # After a failure elsewhere in the turn, stops speaking.
    async def stop(self) -> None:
        self._task.cancel()
        with suppress(asyncio.CancelledError, TurnError):
            await self._task

    def _say(self, sentences: list[str]) -> None:
        for sentence in sentences:
            text = speakable(sentence)
            if not text:
                continue
            if not self._sentences:
                self._turn.timeline.mark("first_sentence_ready")
            self._sentences.append(text)
            self._queue.put_nowait(text)

    async def _speak_in_order(self) -> None:
        while (sentence := await self._queue.get()) is not None:
            try:
                wav = await self._tts.synthesize(sentence, self._turn.voice)
            except TextToSpeechError as error:
                raise TurnError(code="tts_failed", turn_id=self._turn.turn_id) from error
            if not self._turn.timeline.has("tts_first_byte"):
                self._turn.timeline.mark("tts_first_byte")
            await self._listener.audio(self._turn.turn_id, sentence, wav)


# One spoken turn. In the baseline the whole reply is collected before any of it is
# spoken; with `sentence_streaming` each sentence is spoken as soon as it is written.
class TurnPipeline:
    # `system_prompt` is awaited for every turn, so its date and catalogue are current.
    def __init__(
        self,
        stt: SpeechToText,
        llm: ChatModel,
        tts: TextToSpeech,
        toolbox: Toolbox,
        *,
        system_prompt: Callable[[Mapping[str, str]], Awaitable[Prompt]],
        clock: Callable[[], float],
        sentence_streaming: bool,
    ) -> None:
        self._stt = stt
        self._llm = llm
        self._tts = tts
        self._toolbox = toolbox
        self._system_prompt = system_prompt
        self._clock = clock
        self._sentence_streaming = sentence_streaming

    async def run(self, audio: bytes, conversation: Conversation, listener: TurnListener) -> CompletedTurn:
        turn_id = uuid.uuid7().hex
        timeline = Timeline(self._clock)
        timeline.mark("audio_received")
        # The prompt is built while the speech is transcribed, so fetching SayTech's
        # context on a cache miss adds nothing to the wait.
        prompt = asyncio.ensure_future(self._system_prompt(conversation.facts))
        try:
            transcript = await self._transcribe(audio, turn_id)
            timeline.mark("stt_done")
            await listener.transcript(turn_id, transcript)
            system = await prompt
        finally:
            # Only matters when the turn ends early; a finished task ignores it.
            prompt.cancel()
        if self._sentence_streaming:
            answer = await self._answer_aloud(system, transcript, conversation, SpokenTurn(turn_id, conversation.voice, timeline), listener)
        else:
            answer = await self._answer(system, transcript, conversation, timeline, turn_id, listener=listener)
            timeline.mark("first_sentence_ready")
            await listener.reply(turn_id, answer.reply, tour_links(answer.reply, answer.tool_results))
            wav = await self._speak(answer.reply, conversation.voice, turn_id)
            timeline.mark("tts_first_byte")
            await listener.audio(turn_id, answer.reply, wav)
        conversation.remember(transcript, answer.reply, answer.tool_calls, answer.tool_results)
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

    # The baseline: the answer's words are spoken only once the model has finished.
    async def _answer(
        self,
        system: Prompt,
        transcript: str,
        conversation: Conversation,
        timeline: Timeline,
        turn_id: str,
        *,
        listener: TurnListener,
    ) -> Answer:
        conversed = await self._converse(system, transcript, conversation, turn_id, listener=listener, speaker=None)
        return self._spoken(conversed, timeline, turn_id)

    # Experiment 2: every sentence is spoken as soon as it is written, including any the
    # model writes before calling a tool, which plays while the tool runs (D-76). The
    # reply is everything spoken, sent once the last sentence's audio has gone.
    async def _answer_aloud(
        self, system: Prompt, transcript: str, conversation: Conversation, turn: SpokenTurn, listener: TurnListener
    ) -> Answer:
        speaker = SentenceSpeaker(self._tts, listener, turn)
        try:
            conversed = await self._converse(
                system, transcript, conversation, turn.turn_id, listener=listener, speaker=speaker
            )
            sentences = await speaker.finish()
        finally:
            await speaker.stop()
        if not sentences:
            raise TurnError(code="llm_failed", turn_id=turn.turn_id)
        reply = " ".join(sentences)
        await listener.reply(turn.turn_id, reply, tour_links(reply, conversed.tool_results))
        return Answer(reply, conversed.tool_calls, conversed.tool_results)

    # Asks the model, runs any tools it calls and asks again with their results, until it
    # answers in words. Only this turn's tool messages are sent; history keeps the replies.
    # The listener hears what each tool call is about to do; a speaker, when there is one,
    # hears the text of every round as it streams.
    async def _converse(
        self,
        system: Prompt,
        transcript: str,
        conversation: Conversation,
        turn_id: str,
        *,
        listener: TurnListener,
        speaker: SentenceSpeaker | None,
    ) -> Conversed:
        messages = [
            ChatMessage(role="system", content=system.shared, cache_point=True),
            ChatMessage(role="system", content=system.this_turn),
            *conversation.history,
            ChatMessage(role="user", content=transcript),
        ]
        toolbox = self._toolbox.including(conversation.tools)
        tool_calls: list[ToolCall] = []
        tool_results: list[str] = []
        for round_number in range(MAX_TOOL_ROUNDS + 1):
            tools = toolbox.specs if round_number < MAX_TOOL_ROUNDS else []
            model_round = await self._ask(messages, tools, turn_id, speaker)
            log_round(model_round, turn_id, round_number)
            if speaker is not None:
                speaker.round_ended()
            if not model_round.tool_calls:
                return Conversed(model_round, tool_calls, tool_results)
            for call in model_round.tool_calls:
                activity = activity_of(call, system.today, tool_results)
                if activity is not None:
                    await listener.activity(turn_id, activity)
            results = await toolbox.run_all(model_round.tool_calls, turn_id)
            tool_calls += model_round.tool_calls
            tool_results += results
            if answered_while_saving(model_round, results):
                logger.info("turn %(turn_id)s answered while saving facts, so it ends", {"turn_id": turn_id})
                return Conversed(model_round, tool_calls, tool_results)
            messages.append(ChatMessage(role="assistant", content=model_round.text, tool_calls=model_round.tool_calls))
            for call, result in zip(model_round.tool_calls, results, strict=True):
                messages.append(ChatMessage(role="tool", content=result, tool_call_id=call.call_id))
            if speaker is not None and model_round.text.strip():
                messages.append(already_heard(model_round.text))
        # Still calling tools in the round that offered none.
        raise TurnError(code="llm_failed", turn_id=turn_id)

    async def _ask(
        self, messages: Sequence[ChatMessage], tools: Sequence[ToolSpec], turn_id: str, speaker: SentenceSpeaker | None
    ) -> ModelRound:
        try:
            async with self._llm.stream(messages, tools) as events:
                return await self._read(events, speaker)
        except ChatRateLimitedError as error:
            raise TurnError(code="rate_limited", turn_id=turn_id) from error
        except ChatModelError as error:
            raise TurnError(code="llm_failed", turn_id=turn_id) from error

    async def _read(self, events: AsyncIterator[ChatEvent], speaker: SentenceSpeaker | None) -> ModelRound:
        parts: list[str] = []
        call_pieces: list[ToolCallDelta] = []
        first_text_at: float | None = None
        usage: Usage | None = None
        async for event in events:
            if isinstance(event, Usage):
                usage = event
            elif isinstance(event, TextDelta):
                first_text_at = first_text_at if first_text_at is not None else self._clock()
                parts.append(event.text)
                if speaker is not None:
                    speaker.heard(event.text)
            elif isinstance(event, ToolCallDelta):
                call_pieces.append(event)
        return ModelRound("".join(parts), assemble_tool_calls(call_pieces), first_text_at, usage)

    @staticmethod
    def _spoken(conversed: Conversed, timeline: Timeline, turn_id: str) -> Answer:
        model_round = conversed.final
        reply = model_round.text.strip()
        if not reply or model_round.first_text_at is None:
            raise TurnError(code="llm_failed", turn_id=turn_id)
        # The first word of the answer that is spoken, after any tool rounds (D-57).
        timeline.mark("llm_first_token", at=model_round.first_text_at)
        return Answer(reply, conversed.tool_calls, conversed.tool_results)

    async def _speak(self, reply: str, voice: str | None, turn_id: str) -> bytes:
        try:
            return await self._tts.synthesize(reply, voice)
        except TextToSpeechError as error:
            raise TurnError(code="tts_failed", turn_id=turn_id) from error


# A round that answered in words and only saved or forgot facts is the whole answer:
# asked again with the results, the model says it all a second time (D-95). A failed save
# still goes back to the model, so it can say so.
def answered_while_saving(model_round: ModelRound, results: Sequence[str]) -> bool:
    return (
        bool(model_round.text.strip())
        and all(call.name in FACT_TOOLS for call in model_round.tool_calls)
        and not any(failed(result) for result in results)
    )


# With sentence streaming, words written before a tool call are spoken at once. Told what
# the traveller heard, the model carries on from it instead of saying it again (D-95).
def already_heard(text: str) -> ChatMessage:
    return ChatMessage(
        role="system",
        content=(
            f'The traveller has already heard you say: "{text.strip()}" Carry on from there with what '
            "the tool results add, without repeating it, greeting or thanking them again."
        ),
    )


# How much each request read and wrote, so experiment 5 can compare tool payloads.
def log_round(model_round: ModelRound, turn_id: str, round_number: int) -> None:
    if model_round.usage is None:
        return
    logger.info(
        "turn %(turn_id)s round %(round)s used %(input_tokens)s input tokens,"
        " read %(cache_read_tokens)s from the cache and wrote %(cache_write_tokens)s to it",
        {
            "turn_id": turn_id,
            "round": round_number,
            "input_tokens": model_round.usage.input_tokens,
            "cache_read_tokens": model_round.usage.cache_read_tokens,
            "cache_write_tokens": model_round.usage.cache_write_tokens,
            "output_tokens": model_round.usage.output_tokens,
            "tool_calls": len(model_round.tool_calls),
        },
    )
