# Streams real replies from the configured chat model and reports the time to the first
# word, which feeds straight into time-to-first-audio.
# Run from the repository root, with SARJY_LLM_API_KEY in .env or the environment:
#     uv run python gateway/scripts/chat.py "Is tomorrow good for a desert safari?"

import asyncio
from dataclasses import dataclass
import logging
import statistics
import sys
import time

import httpx2
from sarjy_gateway.llm import (
    ChatMessage,
    ChatModel,
    Finished,
    GenerationOptions,
    OpenAiCompatibleChatModel,
    TextDelta,
)
from sarjy_gateway.prompts import SYSTEM_PROMPT
from sarjy_gateway.settings import Settings


DEFAULT_QUESTION = "I'm in Dubai this weekend with two kids. What could we do?"
RUNS = 3

logger = logging.getLogger("chat")


@dataclass(frozen=True)
class TimedReply:
    first_word_seconds: float | None
    total_seconds: float
    finish: str
    text: str


async def time_one_reply(model: ChatModel, messages: list[ChatMessage]) -> TimedReply:
    started = time.perf_counter()
    first_word: float | None = None
    parts: list[str] = []
    finish = "none"
    async with model.stream(messages, []) as events:
        async for event in events:
            if isinstance(event, TextDelta):
                first_word = first_word if first_word is not None else time.perf_counter() - started
                parts.append(event.text)
            elif isinstance(event, Finished):
                finish = event.reason
    return TimedReply(first_word, time.perf_counter() - started, finish, "".join(parts))


async def chat(question: str) -> None:
    settings = Settings()
    if settings.llm_api_key is None:
        message = "set SARJY_LLM_API_KEY in .env or the environment"
        raise SystemExit(message)
    options = GenerationOptions(
        settings.llm_model, settings.llm_temperature, settings.llm_max_tokens, settings.llm_reasoning_effort
    )
    messages = [ChatMessage(role="system", content=SYSTEM_PROMPT), ChatMessage(role="user", content=question)]
    logger.info("model %s, reasoning %s", settings.llm_model, settings.llm_reasoning_effort)
    replies: list[TimedReply] = []
    async with httpx2.AsyncClient(timeout=30.0) as client:
        model = OpenAiCompatibleChatModel(client, settings.llm_base_url, settings.llm_api_key, options)
        for run in range(1, RUNS + 1):
            reply = await time_one_reply(model, messages)
            replies.append(reply)
            logger.info(
                "run %d: first word %.0f ms, whole reply %.0f ms, finish %s",
                run,
                (reply.first_word_seconds or 0) * 1000,
                reply.total_seconds * 1000,
                reply.finish,
            )
            logger.info("  %s", reply.text.replace("\n", " "))
    first_words = [reply.first_word_seconds for reply in replies if reply.first_word_seconds is not None]
    if first_words:
        logger.info("median first word: %.0f ms", statistics.median(first_words) * 1000)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    asyncio.run(chat(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_QUESTION))


if __name__ == "__main__":
    main()
