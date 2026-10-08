# Transcribes recorded clips with the real Groq API and reports how long each took.
# Run from the repository root, with SARJY_GROQ_API_KEY in .env or the environment:
#     uv run python gateway/scripts/transcribe.py clip.webm clip.mp4

import asyncio
import logging
from pathlib import Path
import sys
import time

import httpx2
from sarjy_gateway.settings import Settings
from sarjy_gateway.stt import GroqSpeechToText


logger = logging.getLogger("transcribe")


async def transcribe_all(paths: list[Path]) -> None:
    settings = Settings()
    if settings.groq_api_key is None:
        message = "set SARJY_GROQ_API_KEY in .env or the environment"
        raise SystemExit(message)
    async with httpx2.AsyncClient(timeout=30.0) as client:
        stt = GroqSpeechToText(client, settings.groq_api_key, settings.stt_model)
        for path in paths:
            started = time.perf_counter()
            text = await stt.transcribe(path.read_bytes())
            logger.info("%s (%.0f ms): %s", path.name, (time.perf_counter() - started) * 1000, text)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(transcribe_all([Path(argument) for argument in sys.argv[1:]]))


if __name__ == "__main__":
    main()
