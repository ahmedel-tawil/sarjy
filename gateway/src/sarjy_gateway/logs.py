from collections.abc import Mapping
from datetime import UTC, datetime
import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Cloud Logging reads "severity", "message" and "time" from JSON lines.
        entry: dict[str, object] = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
        }
        # logger.info("turn completed", {"turn_id": ...}): the standard library keeps a single
        # mapping argument as record.args, and here it becomes searchable JSON fields.
        if isinstance(record.args, Mapping):
            entry.update({str(key): value for key, value in record.args.items()})
        if record.exc_info is not None:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler], force=True)
