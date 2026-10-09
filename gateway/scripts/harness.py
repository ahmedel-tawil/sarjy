# Plays the latency script (docs/latency/script) against a gateway as a WebSocket client,
# N times, and records every turn's marks under a run label in docs/latency/runs, then
# prints p50 and p95 per gap (M3.3, D-75). Each repetition is one visit with a fresh
# identity, which forgets its facts at the end. Run from the repository root:
#     uv run python gateway/scripts/harness.py https://gateway-fvbd3h4ngq-ww.a.run.app baseline 3
# The last argument is how many times to play the whole script (1 when left out).

import asyncio
from dataclasses import dataclass
import io
import logging
from pathlib import Path
import re
import sys
import time
import wave

import httpx2
from pydantic import BaseModel, RootModel
from sarjy_gateway.identity import COOKIE_NAME
from sarjy_gateway.latency import ClientMarks, ServerMarks, TurnTiming, table
from sarjy_gateway.messages import BrowserMarks, ForgetMe, ServerError, Transcript, TurnEnd, TurnMarks
from websockets.asyncio.client import ClientConnection, connect


SCRIPT_FOLDER = Path("docs/latency/script")
RUNS_FOLDER = Path("docs/latency/runs")
# About a third of a second of the script's audio, like the browser's recorder chunks.
CHUNK_BYTES = 16_000
# A listener takes a moment before the next question; the gateway sees the same rhythm.
PAUSE_SECONDS = 2.0
TURN_END = TurnEnd(type="turn_end").model_dump_json()
FORGET_ME = ForgetMe(type="forget_me").model_dump_json()

logger = logging.getLogger("harness")


class Line(BaseModel):
    clip: str
    says: str


class Script(RootModel[list[Line]]):
    pass


# Reads only the type of a message from the gateway, to pick the model that parses it.
class Envelope(BaseModel):
    type: str


class TurnFailedError(Exception):
    pass


@dataclass(frozen=True)
class PlayedTurn:
    heard: str
    timing: TurnTiming


def now_ms() -> float:
    return time.perf_counter() * 1000


# Sends the clip at the pace it was spoken, as a browser streams while the button is held,
# so when speech ends only the last chunk is still on its way.
async def speak(socket: ClientConnection, audio: bytes) -> float:
    with wave.open(io.BytesIO(audio), "rb") as clip:
        bytes_per_second = clip.getframerate() * clip.getsampwidth() * clip.getnchannels()
    for start in range(0, len(audio), CHUNK_BYTES):
        chunk = audio[start : start + CHUNK_BYTES]
        await socket.send(chunk)
        await asyncio.sleep(len(chunk) / bytes_per_second)
    speech_end = now_ms()
    await socket.send(TURN_END)
    return speech_end


# Reads the gateway's messages until the turn's marks; the first audio byte stands in for
# the browser starting playback (docs/LATENCY.md says how they differ).
async def listen(socket: ClientConnection, run: str, speech_end: float) -> PlayedTurn:
    heard = ""
    playback_start: float | None = None
    while True:
        message = await socket.recv()
        if isinstance(message, bytes):
            if playback_start is None:
                playback_start = now_ms()
            continue
        match Envelope.model_validate_json(message).type:
            case "transcript":
                heard = Transcript.model_validate_json(message).text
            case "error":
                raise TurnFailedError(ServerError.model_validate_json(message).code)
            case "marks":
                if playback_start is None:
                    no_audio = "the turn ended without audio"
                    raise TurnFailedError(no_audio)
                marks = TurnMarks.model_validate_json(message)
                timing = TurnTiming(
                    run=run,
                    turn_id=marks.turn_id,
                    server=ServerMarks.model_validate(marks.marks),
                    client=ClientMarks(speech_end=speech_end, playback_start=playback_start),
                )
                return PlayedTurn(heard, timing)
            case _:
                continue


# The same message a browser sends once playback starts, so the gateway stores and logs
# the harness's turns like any other.
async def report_marks(socket: ClientConnection, timing: TurnTiming) -> None:
    marks = BrowserMarks(
        type="browser_marks",
        turn_id=timing.turn_id,
        speech_end=timing.client.speech_end,
        playback_start=timing.client.playback_start,
    )
    await socket.send(marks.model_dump_json())


async def identity(base_url: str) -> str:
    async with httpx2.AsyncClient() as client:
        response = await client.get(f"{base_url}/health")
        return response.cookies[COOKIE_NAME]


@dataclass(frozen=True)
class Visit:
    base_url: str
    run: str


async def play_visit(visit: Visit, script: list[Line], repetition: int) -> list[TurnTiming]:
    cookie = await identity(visit.base_url)
    socket_url = re.sub(r"^http", "ws", visit.base_url) + "/ws"
    timings: list[TurnTiming] = []
    # A long reply's WAV passes the client's default limit of 1 MiB; a browser has none.
    headers = {"Cookie": f"{COOKIE_NAME}={cookie}"}
    async with connect(socket_url, additional_headers=headers, max_size=None) as socket:
        # Every visit opens with the memory panel's list.
        await socket.recv()
        for number, line in enumerate(script, start=1):
            speech_end = await speak(socket, (SCRIPT_FOLDER / line.clip).read_bytes())
            try:
                played = await listen(socket, visit.run, speech_end)
            except TurnFailedError as error:
                logger.warning("%d.%d %s failed: %s", repetition, number, line.clip, error)
                continue
            await report_marks(socket, played.timing)
            timings.append(played.timing)
            ttfa = played.timing.client.playback_start - played.timing.client.speech_end
            logger.info("%d.%d %-28s TTFA %6.0f ms  heard: %s", repetition, number, line.clip, ttfa, played.heard)
            await asyncio.sleep(PAUSE_SECONDS)
        await socket.send(FORGET_ME)
        await socket.recv()
    return timings


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    match sys.argv[1:]:
        case [url, run]:
            repeat = 1
        case [url, run, times] if times.isdigit():
            repeat = int(times)
        case _:
            url, run, repeat = "", "", 0
    if not url or not re.fullmatch(r"[a-z0-9-]+", run):
        logger.error("usage: harness.py URL RUN-LABEL [REPEAT]; the label is lower-case letters, digits and dashes")
        sys.exit(2)
    output = RUNS_FOLDER / f"{run}.jsonl"
    if output.exists():
        logger.error("%s already exists; a run is recorded once, so pick another label", output)
        sys.exit(2)
    script = Script.model_validate_json((SCRIPT_FOLDER / "script.json").read_text(encoding="utf-8")).root
    visit = Visit(base_url=url.rstrip("/"), run=run)
    timings: list[TurnTiming] = []
    for repetition in range(1, repeat + 1):
        timings += await play_visit(visit, script, repetition)
    if not timings:
        logger.error("no turn finished, so nothing was recorded")
        sys.exit(1)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(f"{timing.model_dump_json()}\n" for timing in timings), encoding="utf-8")
    logger.info("%s (%d turns) written to %s", run, len(timings), output)
    for line in table(timings):
        logger.info(line)


if __name__ == "__main__":
    asyncio.run(main())
