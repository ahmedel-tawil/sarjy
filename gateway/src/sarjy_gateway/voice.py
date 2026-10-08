from fastapi import APIRouter, WebSocket
from pydantic import ValidationError

from sarjy_gateway.messages import ServerError, TurnEnd
from sarjy_gateway.turn_audio import TurnAudio


class VoiceRouter:
    def __init__(self, max_turn_audio_bytes: int) -> None:
        self._max_turn_audio_bytes = max_turn_audio_bytes

    def build(self) -> APIRouter:
        router = APIRouter()

        @router.websocket("/ws")
        async def voice(websocket: WebSocket) -> None:
            await websocket.accept()
            turn = TurnAudio(self._max_turn_audio_bytes)
            while True:
                message = await websocket.receive()
                if message["type"] == "websocket.disconnect":
                    return
                chunk = message.get("bytes")
                if isinstance(chunk, bytes):
                    turn.add(chunk)
                    continue
                reply = end_turn(message.get("text"), turn)
                if isinstance(reply, ServerError):
                    await websocket.send_text(reply.model_dump_json())
                else:
                    await websocket.send_bytes(reply)

        return router


def end_turn(text: object, turn: TurnAudio) -> bytes | ServerError:
    if not isinstance(text, str):
        return ServerError(code="invalid_message")
    try:
        TurnEnd.model_validate_json(text)
    except ValidationError:
        return ServerError(code="invalid_message")
    too_long = turn.too_long
    audio = turn.take()
    if too_long:
        return ServerError(code="turn_too_long")
    if not audio:
        return ServerError(code="no_audio")
    return audio
