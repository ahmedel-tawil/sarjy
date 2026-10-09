# Prints p50 and p95 per gap for one or more labelled runs, each a JSON Lines file the
# experiment harness wrote (one turn per line). Gaps are defined in docs/LATENCY.md.
# Run from the repository root:
#     uv run python gateway/scripts/latency.py docs/latency/runs/baseline.jsonl

import logging
from pathlib import Path
import sys

from sarjy_gateway.latency import TurnTiming, summarise


logger = logging.getLogger("latency")


def read_run(path: Path) -> list[TurnTiming]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [TurnTiming.model_validate_json(line) for line in lines if line.strip()]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    paths = [Path(argument) for argument in sys.argv[1:]]
    if not paths:
        logger.error("usage: latency.py RUN.jsonl [RUN.jsonl ...]")
        sys.exit(2)
    for path in paths:
        timings = read_run(path)
        if not timings:
            logger.info("%s: no turns", path.name)
            continue
        logger.info("%s (%d turns)", path.stem, len(timings))
        logger.info("  %-20s %8s %8s", "gap", "p50 ms", "p95 ms")
        for summary in summarise(timings):
            logger.info("  %-20s %8.0f %8.0f", summary.gap, summary.p50_ms, summary.p95_ms)


if __name__ == "__main__":
    main()
