from typing import TYPE_CHECKING

from fastapi import FastAPI

from sarjy_tts.api import SynthesisRouter
from sarjy_tts.health import HealthRouter


if TYPE_CHECKING:
    from sarjy_tts.api import Synthesizer
    from sarjy_tts.settings import Settings


def create_app(synthesizer: Synthesizer, settings: Settings) -> FastAPI:
    app = FastAPI(title="Sarjy TTS")
    app.include_router(HealthRouter().build())
    app.include_router(SynthesisRouter(synthesizer, settings.default_voice, settings.max_text_chars).build())
    return app
