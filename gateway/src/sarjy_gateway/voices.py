from fastapi import APIRouter, HTTPException

from sarjy_gateway.tts import TextToSpeech, TextToSpeechError, Voices


class VoicesRouter:
    def __init__(self, tts: TextToSpeech) -> None:
        self._tts = tts

    def build(self) -> APIRouter:
        router = APIRouter()

        @router.get(
            "/voices",
            status_code=200,
            response_model=Voices,
            responses={503: {"description": "The TTS service could not be reached"}},
        )
        async def voices() -> Voices:
            try:
                return await self._tts.voices()
            except TextToSpeechError as error:
                raise HTTPException(status_code=503, detail="voices are unavailable right now") from error

        return router
