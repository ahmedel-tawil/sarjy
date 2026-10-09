from dataclasses import asdict, dataclass, fields
import math
from typing import TYPE_CHECKING

from pydantic import BaseModel


if TYPE_CHECKING:
    from collections.abc import Sequence


# The gateway's five marks, in milliseconds since `audio_received` on its own clock.
class ServerMarks(BaseModel):
    audio_received: float
    stt_done: float
    llm_first_token: float
    first_sentence_ready: float
    tts_first_byte: float


# The browser's two marks, from `performance.now()` on its own clock (D-04).
class ClientMarks(BaseModel):
    speech_end: float
    playback_start: float


# One turn of a labelled run, as the experiment harness records it: one JSON object per
# line of `docs/latency/runs/<label>.jsonl` (D-74).
class TurnTiming(BaseModel):
    run: str
    turn_id: str
    server: ServerMarks
    client: ClientMarks


# One turn's gaps in milliseconds, in the order a turn runs (docs/LATENCY.md).
@dataclass(frozen=True)
class TurnGaps:
    stt: float
    llm_first_word: float
    first_sentence: float
    tts: float
    server_total: float
    network_and_browser: float
    ttfa: float


GAPS = tuple(field.name for field in fields(TurnGaps))


# The two clocks are never mixed: the stages use the gateway's, TTFA the browser's, and
# what TTFA has beyond the gateway's own time is the network and the browser.
def gaps(timing: TurnTiming) -> TurnGaps:
    server, client = timing.server, timing.client
    server_total = server.tts_first_byte - server.audio_received
    ttfa = client.playback_start - client.speech_end
    return TurnGaps(
        stt=server.stt_done - server.audio_received,
        llm_first_word=server.llm_first_token - server.stt_done,
        first_sentence=server.first_sentence_ready - server.llm_first_token,
        tts=server.tts_first_byte - server.first_sentence_ready,
        server_total=server_total,
        network_and_browser=ttfa - server_total,
        ttfa=ttfa,
    )


# Nearest rank: the smallest value with at least p% of the values at or below it, so
# every reported number is one that was measured.
def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        message = "no values to take a percentile of"
        raise ValueError(message)
    ordered = sorted(values)
    rank = max(math.ceil(p / 100 * len(ordered)), 1)
    return ordered[rank - 1]


@dataclass(frozen=True)
class GapSummary:
    gap: str
    turns: int
    p50_ms: float
    p95_ms: float


def summarise(timings: Sequence[TurnTiming]) -> list[GapSummary]:
    per_turn = [asdict(gaps(timing)) for timing in timings]
    summaries: list[GapSummary] = []
    for gap in GAPS:
        values = [turn[gap] for turn in per_turn]
        summaries.append(GapSummary(gap, len(values), percentile(values, 50), percentile(values, 95)))
    return summaries
