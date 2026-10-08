from contextlib import asynccontextmanager
import logging
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sarjy_gateway.health import HealthRouter
from sarjy_gateway.voice import VoiceRouter


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sarjy_gateway.settings import Settings


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    logger.info("gateway started")
    try:
        yield
    finally:
        logger.info("gateway stopped")


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="Sarjy gateway", lifespan=lifespan)
    app.include_router(HealthRouter().build())
    app.include_router(VoiceRouter().build())
    # Mounted last so the API routes above take precedence over static files.
    if settings.frontend_dist is not None:
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    return app
