from fastapi import APIRouter, WebSocket


class VoiceRouter:
    def build(self) -> APIRouter:
        router = APIRouter()

        @router.websocket("/ws")
        async def voice(websocket: WebSocket) -> None:
            await websocket.accept()
            async for frame in websocket.iter_bytes():
                await websocket.send_bytes(frame)

        return router
