from contextlib import asynccontextmanager
import logging
import time
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sarjy_gateway.health import HealthRouter
from sarjy_gateway.turn import TurnPipeline
from sarjy_gateway.voice import VoiceRouter
from sarjy_gateway.voices import VoicesRouter


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sarjy_gateway.services import Services
    from sarjy_gateway.settings import Settings


logger = logging.getLogger(__name__)


def create_app(settings: Settings, services: Services) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        logger.info("gateway started")
        try:
            yield
        finally:
            if services.http_client is not None:
                await services.http_client.aclose()
            logger.info("gateway stopped")

    pipeline = TurnPipeline(services.stt, services.llm, services.tts, time.monotonic)
    app = FastAPI(title="Sarjy gateway", lifespan=lifespan)
    app.include_router(HealthRouter().build())
    app.include_router(VoicesRouter(services.tts).build())
    app.include_router(
        VoiceRouter(pipeline, services.tts, settings.max_turn_audio_bytes, settings.max_history_turns).build()
    )
    # Mounted last so the API routes above take precedence over static files.
    if settings.frontend_dist is not None:
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    return app
