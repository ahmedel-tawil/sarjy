# Sends typed questions through the real turn pipeline (the configured LLM and SayTech,
# no speech in or out) and shows each tool call, the reply Sarjy would speak, and the
# marks. The questions share one conversation, so later ones can refer to earlier ones.
# Run from the repository root, with SARJY_LLM_API_KEY in .env or the environment:
#     uv run python gateway/scripts/ask.py "How much is the buggy dune bashing tour?"

import asyncio
import logging
import sys
import time
from typing import TYPE_CHECKING

from pydantic import ValidationError
from sarjy_gateway.services import build_services
from sarjy_gateway.settings import Settings
from sarjy_gateway.tools import TOOL_TIMEOUT_SECONDS, Toolbox, ToolError
from sarjy_gateway.tour_tools import GetTourTool, SearchToursTool
from sarjy_gateway.tts import Voices
from sarjy_gateway.turn import Conversation, TurnPipeline


if TYPE_CHECKING:
    from sarjy_gateway.llm import ToolSpec
    from sarjy_gateway.tools import Tool


logger = logging.getLogger("ask")


# Stands in for speech to text: the "transcript" is the typed question.
class TypedQuestion:
    def __init__(self) -> None:
        self.text = ""

    async def transcribe(self, audio: bytes) -> str:
        return self.text if audio else ""


class NoSpeech:
    async def voices(self) -> Voices:
        return Voices(voices=[], default="")

    async def synthesize(self, text: str, voice: str | None) -> bytes:
        return f"[{voice or 'default voice'}] {text}".encode()


class NoListener:
    async def transcript(self, turn_id: str, text: str) -> None:
        pass

    async def reply(self, turn_id: str, text: str) -> None:
        pass

    async def audio(self, turn_id: str, wav: bytes) -> None:
        pass


# Wraps a tool to print what the model asked it and how much it sent back.
class ShownTool:
    def __init__(self, tool: Tool) -> None:
        self._tool = tool

    @property
    def spec(self) -> ToolSpec:
        return self._tool.spec

    async def run(self, arguments: str) -> str:
        try:
            result = await self._tool.run(arguments)
        except (ValidationError, ToolError) as error:
            logger.info("  tool %s %s -> error: %s", self.spec.name, arguments, error)
            raise
        logger.info("  tool %s %s -> %d bytes", self.spec.name, arguments, len(result))
        return result


async def ask(questions: list[str]) -> None:
    settings = Settings()
    if settings.llm_api_key is None:
        message = "set SARJY_LLM_API_KEY in .env or the environment"
        raise SystemExit(message)
    services = build_services(settings)
    tools: list[Tool] = [
        ShownTool(SearchToursTool(services.catalogue)),
        ShownTool(GetTourTool(services.catalogue)),
    ]
    stt = TypedQuestion()
    toolbox = Toolbox(tools, time.monotonic, TOOL_TIMEOUT_SECONDS)
    pipeline = TurnPipeline(stt, services.llm, NoSpeech(), toolbox, time.monotonic)
    conversation = Conversation(max_turns=settings.max_history_turns)
    try:
        for question in questions:
            stt.text = question
            logger.info("you: %s", question)
            turn = await pipeline.run(b"typed", conversation, NoListener())
            logger.info("sarjy: %s", turn.reply)
            first_word_ms = turn.marks["llm_first_token"]
            logger.info("  first word of the answer after %.0f ms\n", first_word_ms)
    finally:
        if services.http_client is not None:
            await services.http_client.aclose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("sarjy_gateway").setLevel(logging.WARNING)
    asyncio.run(ask(sys.argv[1:]))


if __name__ == "__main__":
    main()
