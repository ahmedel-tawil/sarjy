import logging
from typing import TYPE_CHECKING
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from sarjy_gateway.conversation_store import StoredTurn
from sarjy_gateway.database import DatabaseUnavailableError
from sarjy_gateway.identity import COOKIE_NAME, user_id_from
from sarjy_gateway.memory import ForgetFactTool, RememberFactTool
from sarjy_gateway.messages import (
    AudioFollows,
    BrowserMarks,
    ClientMessage,
    ErrorCode,
    Reply,
    ServerError,
    SetVoice,
    Transcript,
    TurnCancel,
    TurnEnd,
    TurnMarks,
)
from sarjy_gateway.tts import TextToSpeechError
from sarjy_gateway.turn import Conversation, TurnError
from sarjy_gateway.turn_audio import TurnAudio


if TYPE_CHECKING:
    from sarjy_gateway.conversation_store import ConversationStore, SessionId
    from sarjy_gateway.identity import UserId
    from sarjy_gateway.memory import FactStore
    from sarjy_gateway.tts import TextToSpeech
    from sarjy_gateway.turn import CompletedTurn, TurnPipeline


logger = logging.getLogger(__name__)


# Sends each part of a turn to the browser as soon as the pipeline has it.
class SocketListener:
    def __init__(self, websocket: WebSocket) -> None:
        self._websocket = websocket

    async def transcript(self, turn_id: str, text: str) -> None:
        await self._websocket.send_text(Transcript(turn_id=turn_id, text=text).model_dump_json())

    async def reply(self, turn_id: str, text: str) -> None:
        await self._websocket.send_text(Reply(turn_id=turn_id, text=text).model_dump_json())

    async def audio(self, turn_id: str, wav: bytes) -> None:
        # A binary frame cannot carry the turn id, so a small JSON message announces it.
        await self._websocket.send_text(AudioFollows(turn_id=turn_id).model_dump_json())
        await self._websocket.send_bytes(wav)

    async def marks(self, turn_id: str, marks: dict[str, float]) -> None:
        await self._websocket.send_text(TurnMarks(turn_id=turn_id, marks=marks).model_dump_json())

    async def error(self, code: ErrorCode, turn_id: str | None = None) -> None:
        await self._websocket.send_text(ServerError(code=code, turn_id=turn_id).model_dump_json())


class VoiceRouter:
    def __init__(
        self,
        pipeline: TurnPipeline,
        tts: TextToSpeech,
        store: ConversationStore,
        facts: FactStore,
        *,
        max_turn_audio_bytes: int,
        max_history_turns: int,
    ) -> None:
        self._pipeline = pipeline
        self._tts = tts
        self._store = store
        self._facts = facts
        self._max_turn_audio_bytes = max_turn_audio_bytes
        self._max_history_turns = max_history_turns

    def build(self) -> APIRouter:
        router = APIRouter()

        @router.websocket("/ws")
        async def voice(websocket: WebSocket) -> None:
            # Only a browser that loaded the page, and so has its identity cookie, may talk.
            user_id = user_id_from(websocket.cookies.get(COOKIE_NAME))
            if user_id is None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            await websocket.accept()
            try:
                await self._serve(websocket, user_id)
            except WebSocketDisconnect:
                # The page was closed or reloaded while its turn was running, so the next
                # send found the socket gone. Nothing is left to answer.
                logger.info("browser left mid-turn")

        return router

    async def _serve(self, websocket: WebSocket, user_id: UserId) -> None:
        audio = TurnAudio(self._max_turn_audio_bytes)
        conversation = Conversation(max_turns=self._max_history_turns, user_id=user_id)
        conversation.session_id = await self._start_session(user_id)
        conversation.facts = await self._load_facts(user_id)
        conversation.tools = [
            RememberFactTool(self._facts, conversation),
            ForgetFactTool(self._facts, conversation),
        ]
        listener = SocketListener(websocket)
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            chunk = message.get("bytes")
            if isinstance(chunk, bytes):
                audio.add(chunk)
            else:
                await self._control(message.get("text"), audio, conversation, listener)

    async def _control(
        self, text: object, audio: TurnAudio, conversation: Conversation, listener: SocketListener
    ) -> None:
        if not isinstance(text, str):
            await listener.error("invalid_message")
            return
        try:
            control = ClientMessage.model_validate_json(text).root
        except ValidationError:
            await listener.error("invalid_message")
            return
        match control:
            case SetVoice(voice=voice):
                await self._set_voice(voice, conversation, listener)
            case TurnEnd():
                await self._end_turn(audio, conversation, listener)
            case TurnCancel():
                audio.take()
            case BrowserMarks():
                # Joined to the server's "completed" line by turn_id; M3.1 stores both.
                logger.info("turn %(turn_id)s played", {"turn_id": control.turn_id, "ttfa_ms": control.ttfa_ms})

    # Without the database the visit goes ahead unrecorded: voice matters more than history.
    async def _start_session(self, user_id: UserId) -> SessionId | None:
        try:
            return await self._store.start_session(user_id)
        except DatabaseUnavailableError as error:
            logger.warning("session not stored: %(reason)s", {"reason": str(error)})
            return None

    # Saved facts go into every prompt of the visit; without the database Sarjy starts the
    # visit knowing nothing.
    async def _load_facts(self, user_id: UserId) -> dict[str, str]:
        try:
            return {fact.key: fact.value for fact in await self._facts.facts(user_id)}
        except DatabaseUnavailableError as error:
            logger.warning("facts not loaded: %(reason)s", {"reason": str(error)})
            return {}

    async def _set_voice(self, voice: str, conversation: Conversation, listener: SocketListener) -> None:
        try:
            available = await self._tts.voices()
        except TextToSpeechError:
            await listener.error("tts_failed")
            return
        if voice not in available.voices:
            await listener.error("unknown_voice")
            return
        conversation.voice = voice

    async def _end_turn(self, audio: TurnAudio, conversation: Conversation, listener: SocketListener) -> None:
        too_long = audio.too_long
        clip = audio.take()
        if too_long:
            await listener.error("turn_too_long")
            return
        if not clip:
            await listener.error("no_audio")
            return
        try:
            turn = await self._pipeline.run(clip, conversation, listener)
        except TurnError as error:
            logger.warning(
                "turn %(turn_id)s failed: %(code)s", {"turn_id": error.turn_id, "code": error.code}, exc_info=error
            )
            await listener.error(error.code, error.turn_id)
            return
        await listener.marks(turn.turn_id, turn.marks)
        # Saved after the reply has been spoken and its marks sent, so it never delays them.
        if conversation.session_id is not None:
            await self._save(turn, conversation.session_id)

    async def _save(self, turn: CompletedTurn, session_id: SessionId) -> None:
        stored = StoredTurn(
            id=uuid.UUID(hex=turn.turn_id), transcript=turn.transcript, reply=turn.reply, tool_results=turn.tool_results
        )
        try:
            await self._store.save_turn(session_id, stored)
        except DatabaseUnavailableError as error:
            logger.warning("turn %(turn_id)s not stored: %(reason)s", {"turn_id": turn.turn_id, "reason": str(error)})
