import logging

from pydantic import BaseModel
from sarjy_gateway.logs import JsonFormatter


class LogLine(BaseModel):
    severity: str
    message: str
    logger: str
    time: str


def test_log_line_is_json_with_cloud_logging_fields() -> None:
    record = logging.LogRecord("sarjy", logging.WARNING, __file__, 1, "hello %s", ("there",), None)

    line = LogLine.model_validate_json(JsonFormatter().format(record))

    assert line.severity == "WARNING"
    assert line.message == "hello there"
    assert line.logger == "sarjy"
