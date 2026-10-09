# Prints p50 and p95 per gap for one or more labelled runs, each a JSON Lines file the
# experiment harness wrote (one turn per line). Gaps are defined in docs/LATENCY.md.
# Run from the repository root:
#     uv run python gateway/scripts/latency.py docs/latency/runs/baseline.jsonl

import logging
from pathlib import Path
import sys

from sarjy_gateway.latency import TurnTiming, table


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
        for line in table(timings):
            logger.info(line)


if __name__ == "__main__":
    main()
