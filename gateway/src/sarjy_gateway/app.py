from contextlib import asynccontextmanager
from datetime import datetime
import logging
import time
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sarjy_gateway.health import HealthRouter
from sarjy_gateway.prompts import SystemPrompt
from sarjy_gateway.tools import TOOL_TIMEOUT_SECONDS, Toolbox
from sarjy_gateway.tour_tools import GetTourTool, SearchToursTool
from sarjy_gateway.turn import TurnPipeline
from sarjy_gateway.voice import VoiceRouter
from sarjy_gateway.voices import VoicesRouter
from sarjy_gateway.weather import UAE_TIME
from sarjy_gateway.weather_tool import GetWeatherTool


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sarjy_gateway.services import Services
    from sarjy_gateway.settings import Settings


logger = logging.getLogger(__name__)


def create_app(settings: Settings, services: Services) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        if services.database_pool is not None:
            await services.database_pool.open()
        logger.info("gateway started")
        try:
            yield
        finally:
            if services.database_pool is not None:
                await services.database_pool.close()
            if services.http_client is not None:
                await services.http_client.aclose()
            if services.anthropic_client is not None:
                await services.anthropic_client.close()
            logger.info("gateway stopped")

    # Memory tools join in M2.6.
    tools = [
        SearchToursTool(services.catalogue),
        GetTourTool(services.catalogue),
        # The wall clock, not a monotonic one: the tool needs today's date.
        GetWeatherTool(services.weather, time.time),
    ]
    toolbox = Toolbox(tools=tools, clock=time.monotonic, timeout_seconds=TOOL_TIMEOUT_SECONDS)
    pipeline = TurnPipeline(
        services.stt,
        services.llm,
        services.tts,
        toolbox,
        system_prompt=SystemPrompt(services.catalogue, lambda: datetime.now(UAE_TIME)).build,
        clock=time.monotonic,
    )
    app = FastAPI(title="Sarjy gateway", lifespan=lifespan)
    app.include_router(HealthRouter(services.database).build())
    app.include_router(VoicesRouter(services.tts).build())
    app.include_router(
        VoiceRouter(pipeline, services.tts, settings.max_turn_audio_bytes, settings.max_history_turns).build()
    )
    # Mounted last so the API routes above take precedence over static files.
    if settings.frontend_dist is not None:
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    return app
