import asyncio
from typing import TYPE_CHECKING, Annotated, Protocol

from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from sarjy_tts.synthesizer import to_wav


if TYPE_CHECKING:
    import numpy as np
    from numpy.typing import NDArray


class Synthesizer(Protocol):
    @property
    def voice_names(self) -> list[str]: ...

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> NDArray[np.float32]: ...


class SynthesisRequest(BaseModel):
    text: str = Field(min_length=1)
    voice: str | None = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class VoicesResponse(BaseModel):
    voices: list[str]
    default: str


class SynthesisRouter:
    def __init__(self, synthesizer: Synthesizer, default_voice: str, max_text_chars: int) -> None:
        self._synthesizer = synthesizer
        self._default_voice = default_voice
        self._max_text_chars = max_text_chars

    def build(self) -> APIRouter:
        router = APIRouter()

        @router.get("/voices", status_code=200, response_model=VoicesResponse)
        async def voices() -> VoicesResponse:
            return VoicesResponse(voices=self._synthesizer.voice_names, default=self._default_voice)

        # The reply is WAV audio, not JSON. StreamingResponse marks it as binary, and leaves
        # room to stream long text chunk by chunk later.
        @router.post(
            "/synthesize",
            status_code=200,
            response_class=StreamingResponse,
            responses={
                200: {"content": {"audio/wav": {}}, "description": "16-bit mono WAV at 24 kHz"},
                422: {"description": "Empty or too-long text, an unknown voice or a speed out of range"},
            },
        )
        async def synthesize(request: Annotated[SynthesisRequest, Body()]) -> StreamingResponse:
            if len(request.text) > self._max_text_chars:
                raise HTTPException(status_code=422, detail=f"text is longer than {self._max_text_chars} characters")
            voice = request.voice or self._default_voice
            if voice not in self._synthesizer.voice_names:
                raise HTTPException(status_code=422, detail=f"unknown voice: {voice}")
            # Synthesis is CPU-bound; a worker thread keeps the event loop free for /health.
            audio = await asyncio.to_thread(self._synthesizer.synthesize, request.text, voice, request.speed)
            return StreamingResponse(iter([to_wav(audio)]), media_type="audio/wav")

        return router
