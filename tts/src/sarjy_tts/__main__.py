import logging
import time

import uvicorn

from sarjy_tts.app import create_app
from sarjy_tts.loading import load_synthesizer
from sarjy_tts.logs import configure_logging
from sarjy_tts.settings import Settings


logger = logging.getLogger(__name__)


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)

    started = time.perf_counter()
    synthesizer = load_synthesizer(settings.models_dir, settings.model_file, settings.threads)
    if settings.default_voice not in synthesizer.voice_names:
        message = f"default voice {settings.default_voice} is not among {synthesizer.voice_names}"
        raise ValueError(message)
    # An onnxruntime session's first run is slower than the rest; pay that cost before
    # Cloud Run sends real traffic.
    synthesizer.synthesize("Hello.", settings.default_voice)
    logger.info("loaded and warmed up %s in %.1f s", settings.model_file, time.perf_counter() - started)

    # log_config=None keeps uvicorn's logs in our JSON format; Cloud Run logs requests.
    uvicorn.run(
        create_app(synthesizer, settings),
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    main()
