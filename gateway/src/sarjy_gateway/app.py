from contextlib import asynccontextmanager
import logging
import time
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import httpx2

from sarjy_gateway.health import HealthRouter
from sarjy_gateway.tts import (
    REQUEST_TIMEOUT_SECONDS,
    HttpTextToSpeech,
    MetadataIdToken,
    MissingTextToSpeech,
    NoToken,
    TextToSpeech,
)
from sarjy_gateway.voice import VoiceRouter
from sarjy_gateway.voices import VoicesRouter


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sarjy_gateway.settings import Settings


logger = logging.getLogger(__name__)


def build_text_to_speech(settings: Settings) -> TextToSpeech:
    if settings.tts_url is None:
        return MissingTextToSpeech()
    client = httpx2.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS)
    tokens = MetadataIdToken(client, settings.tts_url, time.monotonic) if settings.tts_auth == "id_token" else NoToken()
    return HttpTextToSpeech(client, settings.tts_url, tokens)


def create_app(settings: Settings, tts: TextToSpeech) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        logger.info("gateway started")
        try:
            yield
        finally:
            await tts.aclose()
            logger.info("gateway stopped")

    app = FastAPI(title="Sarjy gateway", lifespan=lifespan)
    app.include_router(HealthRouter().build())
    app.include_router(VoicesRouter(tts).build())
    app.include_router(VoiceRouter(settings.max_turn_audio_bytes).build())
    # Mounted last so the API routes above take precedence over static files.
    if settings.frontend_dist is not None:
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    return app
