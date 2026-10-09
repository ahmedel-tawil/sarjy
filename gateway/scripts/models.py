# Experiment 4 (M3.8): the script's ten questions, typed, through the real pipeline and
# tools for one model at a time, with no fallback. It times the first word of each answer
# and checks that each turn did what its question needs. Every pass is a fresh visit with
# an empty memory. Run from the repository root, with the provider's key in .env or the
# environment (SARJY_ANTHROPIC_API_KEY for claude, SARJY_LLM_API_KEY for groq):
#     uv run python gateway/scripts/models.py claude:claude-haiku-5-5 claude-haiku 2
#     uv run python gateway/scripts/models.py groq:openai/gpt-oss-20b groq-gpt-oss-20b 2
# Each run writes docs/latency/models/LABEL.jsonl, one turn per line.

import asyncio
from dataclasses import dataclass
import datetime
import itertools
import logging
from pathlib import Path
import re
import sys
import time
from typing import TYPE_CHECKING

from pydantic import BaseModel, RootModel, ValidationError
from sarjy_gateway.latency import percentile
from sarjy_gateway.memory import Fact, ForgetFactTool, RememberFactTool
from sarjy_gateway.prompts import SystemPrompt
from sarjy_gateway.services import build_services
from sarjy_gateway.settings import Settings
from sarjy_gateway.tools import TOOL_TIMEOUT_SECONDS, Toolbox
from sarjy_gateway.tour_tools import GetTourTool, SearchToursArguments, SearchToursTool
from sarjy_gateway.tts import Voices
from sarjy_gateway.turn import CompletedTurn, Conversation, TurnError, TurnPipeline
from sarjy_gateway.weather import UAE_TIME
from sarjy_gateway.weather_tool import GetWeatherArguments, GetWeatherTool


if TYPE_CHECKING:
    from collections.abc import Mapping

    from sarjy_gateway.identity import UserId
    from sarjy_gateway.llm import ToolSpec
    from sarjy_gateway.messages import TourLink
    from sarjy_gateway.services import Services
    from sarjy_gateway.tools import Tool


logger = logging.getLogger("models")

SCRIPT = Path("docs/latency/script/script.json")
MODELS_FOLDER = Path("docs/latency/models")
# Groq's free tier allows 8,000 tokens a minute per model, about one tool turn, so its
# turns are paced a minute apart and a rate-limited turn waits and runs again.
GROQ_PAUSE_SECONDS = 60
RATE_LIMIT_WAIT_SECONDS = 60
MAX_WAITS_PER_TURN = 5
SCRIPT_PRICE_LIMIT_AED = 400
SATURDAY = 5


class Line(BaseModel):
    clip: str
    says: str


class Script(RootModel[list[Line]]):
    pass


# One turn of a run, as written to the run's file.
class ModelTurn(BaseModel):
    model: str
    run: int
    clip: str
    says: str
    first_word_ms: float | None
    tool_calls: list[str]
    passed: bool
    reply: str
    rate_limit_waits: int


@dataclass(frozen=True)
class Called:
    name: str
    arguments: str


# Stands in for speech to text: the "transcript" is the script's line as typed.
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


# Hears the turn and the memory updates and keeps none of them; the checks read the
# conversation instead.
class Quiet:
    async def transcript(self, turn_id: str, text: str) -> None:
        pass

    async def activity(self, turn_id: str, text: str) -> None:
        pass

    async def reply(self, turn_id: str, text: str, links: list[TourLink]) -> None:
        pass

    async def audio(self, turn_id: str, text: str, wav: bytes) -> None:
        pass

    async def memory(self, facts: Mapping[str, str]) -> None:
        pass


# The run's memory, so the visit's facts never reach the database.
class DictFactStore:
    def __init__(self) -> None:
        self._facts: dict[UserId, dict[str, str]] = {}

    async def facts(self, user_id: UserId) -> list[Fact]:
        return list(itertools.starmap(Fact, self._facts.get(user_id, {}).items()))

    async def remember(self, user_id: UserId, fact: Fact) -> None:
        self._facts.setdefault(user_id, {})[fact.key] = fact.value

    async def forget(self, user_id: UserId, key: str) -> bool:
        return self._facts.get(user_id, {}).pop(key, None) is not None

    async def forget_all(self, user_id: UserId) -> None:
        self._facts.pop(user_id, None)


# Passes every call through, noting what the model asked for, for the checks.
class RecordedTool:
    def __init__(self, tool: Tool, calls: list[Called]) -> None:
        self._tool = tool
        self._calls = calls

    @property
    def spec(self) -> ToolSpec:
        return self._tool.spec

    async def run(self, arguments: str) -> str:
        self._calls.append(Called(self.spec.name, arguments))
        return await self._tool.run(arguments)


# The model's settings with only its own provider's key, so nothing falls back.
def model_settings(settings: Settings, model: str) -> Settings:
    match model.split(":", 1):
        case ["claude", name]:
            return settings.model_copy(update={"llm_primary": "claude", "llm_api_key": None, "claude_model": name})
        case ["groq", name]:
            # gpt-oss always reasons, at "low" at least; Qwen can be told not to (D-96).
            effort = "low" if name.startswith("openai/gpt-oss") else "none"
            update = {"llm_primary": "groq", "anthropic_api_key": None, "llm_model": name, "llm_reasoning_effort": effort}
            return settings.model_copy(update=update)
        case _:
            message = f"unknown model {model}: use claude:<model> or groq:<model>"
            raise SystemExit(message)


def searches_in(calls: list[Called]) -> list[SearchToursArguments]:
    found: list[SearchToursArguments] = []
    for call in calls:
        if call.name == "search_tours":
            try:
                found.append(SearchToursArguments.model_validate_json(call.arguments))
            except ValidationError:
                continue
    return found


def forecasts_in(calls: list[Called]) -> list[GetWeatherArguments]:
    found: list[GetWeatherArguments] = []
    for call in calls:
        if call.name == "get_weather":
            try:
                found.append(GetWeatherArguments.model_validate_json(call.arguments))
            except ValidationError:
                continue
    return found


def searched_in(calls: list[Called], city: str) -> list[SearchToursArguments]:
    return [search for search in searches_in(calls) if (search.city or "").lower() == city]


# What each question needs: the right tool with the right arguments, the facts saved, or
# an answer from memory. Saying it well is not checked here; the replies are in the file.
def passed(clip: str, calls: list[Called], reply: str, facts: Mapping[str, str], today: datetime.date) -> bool:
    saved = " ".join(facts.values()).lower()
    forecasts = forecasts_in(calls)
    match clip:
        case "01-kids-under-400.wav":
            prices = [search.max_price_aed for search in searched_in(calls, "abu dhabi")]
            ok = any(price is not None and price <= SCRIPT_PRICE_LIMIT_AED for price in prices)
        case "02-colour-and-heights.wav":
            ok = "green" in saved and "height" in saved
        case "03-ask-colour.wav":
            ok = "green" in reply.lower()
        case "04-dubai-weekend.wav" | "07-what-in-dubai.wav":
            ok = bool(searched_in(calls, "dubai"))
        case "05-safari-tomorrow.wav":
            ok = any(forecast.date == today + datetime.timedelta(days=1) for forecast in forecasts)
        case "06-buggy-price.wav":
            # Its price is on request; a model may repeat that from its own earlier answer.
            ok = "request" in reply.lower()
        case "08-my-name.wav":
            ok = "sam" in saved
        case "09-abu-dhabi-weather.wav":
            ok = any(forecast.city.lower() == "abu dhabi" and forecast.date.weekday() == SATURDAY for forecast in forecasts)
        case "10-thanks.wav":
            ok = not calls and bool(reply)
        case _:
            ok = False
    return ok


@dataclass(frozen=True)
class Run:
    model: str
    number: int
    pause_seconds: float
    history_turns: int


# A question's turn, or None when it failed, and how often it waited for the rate limit.
@dataclass(frozen=True)
class Answered:
    turn: CompletedTurn | None
    waits: int


# One question, run again after a wait whenever the provider says it is over its limit.
async def answer(pipeline: TurnPipeline, conversation: Conversation) -> Answered:
    waits = 0
    while True:
        try:
            return Answered(await pipeline.run(b"typed", conversation, Quiet()), waits)
        except TurnError as error:
            if error.code != "rate_limited" or waits == MAX_WAITS_PER_TURN:
                logger.warning("  turn failed: %s", error.code)
                return Answered(None, waits)
            waits += 1
            await asyncio.sleep(RATE_LIMIT_WAIT_SECONDS)


async def play(services: Services, script: list[Line], run: Run) -> list[ModelTurn]:
    calls: list[Called] = []
    shared: list[Tool] = [
        SearchToursTool(services.catalogue),
        GetTourTool(services.catalogue),
        GetWeatherTool(services.weather, time.time),
    ]
    toolbox = Toolbox([RecordedTool(tool, calls) for tool in shared], time.monotonic, TOOL_TIMEOUT_SECONDS)
    stt = TypedQuestion()
    prompt = SystemPrompt(services.catalogue, lambda: datetime.datetime.now(UAE_TIME))
    pipeline = TurnPipeline(
        stt, services.llm, NoSpeech(), toolbox, system_prompt=prompt.build, clock=time.monotonic, sentence_streaming=True
    )
    store = DictFactStore()
    conversation = Conversation(max_turns=run.history_turns)
    conversation.tools = [
        RecordedTool(RememberFactTool(store, conversation, Quiet()), calls),
        RecordedTool(ForgetFactTool(store, conversation, Quiet()), calls),
    ]
    turns: list[ModelTurn] = []
    for line in script:
        calls.clear()
        stt.text = line.says
        answered = await answer(pipeline, conversation)
        turn = answered.turn
        reply = "" if turn is None else turn.reply
        first_word = None if turn is None else turn.marks["llm_first_token"] - turn.marks["stt_done"]
        ok = turn is not None and passed(line.clip, calls, reply, conversation.facts, datetime.datetime.now(UAE_TIME).date())
        turns.append(
            ModelTurn(
                model=run.model,
                run=run.number,
                clip=line.clip,
                says=line.says,
                first_word_ms=first_word,
                tool_calls=[f"{call.name} {call.arguments}" for call in calls],
                passed=ok,
                reply=reply,
                rate_limit_waits=answered.waits,
            )
        )
        shown = "-" if first_word is None else f"{first_word:.0f} ms"
        logger.info("%d %-28s %-9s %s  %s", run.number, line.clip, shown, "ok" if ok else "FAILED", reply[:90])
        await asyncio.sleep(run.pause_seconds)
    return turns


def summarise(model: str, turns: list[ModelTurn]) -> None:
    first_words = [turn.first_word_ms for turn in turns if turn.first_word_ms is not None]
    if first_words:
        logger.info(
            "%s: first word p50 %.0f ms, p95 %.0f ms over %d answered turns",
            model,
            percentile(first_words, 50),
            percentile(first_words, 95),
            len(first_words),
        )
    failed = [f"{turn.run}/{turn.clip}" for turn in turns if not turn.passed]
    waits = sum(turn.rate_limit_waits for turn in turns)
    logger.info("%d of %d checks passed; %d rate-limit waits", len(turns) - len(failed), len(turns), waits)
    if failed:
        logger.info("failed: %s", ", ".join(failed))


async def compare(model: str, script: list[Line], passes: int) -> list[ModelTurn]:
    settings = model_settings(Settings(), model)
    services = build_services(settings)
    pause = GROQ_PAUSE_SECONDS if model.startswith("groq:") else 0
    turns: list[ModelTurn] = []
    try:
        for number in range(1, passes + 1):
            turns += await play(services, script, Run(model, number, pause, settings.max_history_turns))
    finally:
        if services.http_client is not None:
            await services.http_client.aclose()
        if services.anthropic_client is not None:
            await services.anthropic_client.close()
    return turns


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)
    logging.getLogger("sarjy_gateway").setLevel(logging.ERROR)
    match sys.argv[1:]:
        case [model, label]:
            passes = 1
        case [model, label, times] if times.isdigit():
            passes = int(times)
        case _:
            model, label, passes = "", "", 0
    if not model or not re.fullmatch(r"[a-z0-9-]+", label):
        logger.error("usage: models.py PROVIDER:MODEL LABEL [PASSES]; the label is lower-case letters, digits and dashes")
        sys.exit(2)
    script = Script.model_validate_json(SCRIPT.read_text(encoding="utf-8")).root
    turns = asyncio.run(compare(model, script, passes))
    MODELS_FOLDER.mkdir(parents=True, exist_ok=True)
    output = MODELS_FOLDER / f"{label}.jsonl"
    output.write_text("".join(turn.model_dump_json() + "\n" for turn in turns), encoding="utf-8")
    logger.info("%s written", output)
    summarise(model, turns)


if __name__ == "__main__":
    main()
