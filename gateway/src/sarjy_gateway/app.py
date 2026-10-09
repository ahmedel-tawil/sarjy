from contextlib import asynccontextmanager
from datetime import datetime
import logging
import time
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sarjy_gateway.catalogue import SayTechCatalogue
from sarjy_gateway.health import HealthRouter
from sarjy_gateway.identity import identity_cookie
from sarjy_gateway.limits import MAX_KEYS, SlidingWindow, TurnLimits
from sarjy_gateway.migrate import MIGRATIONS_FOLDER, MigrationError, MigrationRunner, Migrations
from sarjy_gateway.prompts import SystemPrompt
from sarjy_gateway.tools import TOOL_TIMEOUT_SECONDS, Toolbox
from sarjy_gateway.tour_tools import GetTourTool, RawGetTourTool, RawSearchToursTool, SearchToursTool
from sarjy_gateway.turn import TurnPipeline
from sarjy_gateway.voice import VoiceRouter
from sarjy_gateway.voices import VoicesRouter
from sarjy_gateway.weather import UAE_TIME
from sarjy_gateway.weather_tool import GetWeatherTool


if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sarjy_gateway.services import Services
    from sarjy_gateway.settings import Settings
    from sarjy_gateway.tools import Tool


logger = logging.getLogger(__name__)


def create_app(settings: Settings, services: Services) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        if services.database_pool is not None:
            await services.database_pool.open()
            # A failure leaves memory unavailable, not the whole gateway: voice still works.
            migrations: Migrations = MigrationRunner(services.database_pool, MIGRATIONS_FOLDER)
            try:
                await migrations.apply_pending()
            except MigrationError:
                logger.exception("starting without an up-to-date database")
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

    # Shared by every visit; each visit adds its user's memory tools (D-67).
    tools = [
        *tour_tools(settings, services),
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
        sentence_streaming=settings.pipeline_mode == "sentence",
    )
    app = FastAPI(title="Sarjy gateway", lifespan=lifespan)
    app.include_router(HealthRouter(services.database).build())
    app.include_router(VoicesRouter(services.tts).build())
    app.middleware("http")(identity_cookie(secure=settings.cookie_secure))
    app.include_router(
        VoiceRouter(
            pipeline,
            services.tts,
            services.conversations,
            services.facts,
            TurnLimits(
                per_user=SlidingWindow(
                    settings.turns_per_user, settings.turn_window_seconds, time.monotonic, max_keys=MAX_KEYS
                ),
                per_ip=SlidingWindow(
                    settings.turns_per_ip, settings.turn_window_seconds, time.monotonic, max_keys=MAX_KEYS
                ),
            ),
            max_turn_audio_bytes=settings.max_turn_audio_bytes,
            max_history_turns=settings.max_history_turns,
            max_turns_per_visit=settings.max_turns_per_visit,
        ).build()
    )
    # Mounted last so the API routes above take precedence over static files.
    if settings.frontend_dist is not None:
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    return app


# Experiment 5 (M3.9): raw payloads come straight from SayTech, uncached, so only what the
# model reads differs from the lean tools. Without an HTTP client (tests) they stay lean.
def tour_tools(settings: Settings, services: Services) -> list[Tool]:
    if settings.tool_payload == "raw" and services.http_client is not None:
        saytech = SayTechCatalogue(services.http_client, settings.saytech_base_url, settings.saytech_timeout_seconds)
        return [RawSearchToursTool(saytech), RawGetTourTool(saytech)]
    return [SearchToursTool(services.catalogue), GetTourTool(services.catalogue)]
