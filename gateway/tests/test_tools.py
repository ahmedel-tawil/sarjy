import asyncio
import time

from pydantic import BaseModel
import pytest
from sarjy_gateway.llm import ToolCall, ToolSpec
from sarjy_gateway.tools import TOOL_TIMEOUT_SECONDS, Toolbox, ToolError, ToolFailure

from gateway.tests.fakes import FakeWeatherTool, TickingClock


class NapArguments(BaseModel):
    seconds: float


# Sleeps for as long as each call asks, then returns that number.
class NapTool:
    spec = ToolSpec("nap", "Sleeps.", NapArguments.model_json_schema())

    async def run(self, arguments: str) -> str:
        nap = NapArguments.model_validate_json(arguments)
        await asyncio.sleep(nap.seconds)
        return str(nap.seconds)


def weather_call(arguments: str, name: str = "get_weather") -> ToolCall:
    return ToolCall(call_id="call-1", name=name, arguments=arguments)


def test_specs_list_every_tool() -> None:
    toolbox = Toolbox([FakeWeatherTool(), NapTool()], TickingClock(), TOOL_TIMEOUT_SECONDS)

    assert [spec.name for spec in toolbox.specs] == ["get_weather", "nap"]


@pytest.mark.parametrize(
    ("tool", "call", "expected"),
    [
        (
            FakeWeatherTool(),
            weather_call('{"city": "Dubai"}'),
            "Invalid arguments: date: Field required",
        ),
        (
            FakeWeatherTool(),
            weather_call('{"city": '),
            "Invalid arguments: arguments: Invalid JSON: EOF while parsing a value at line 1 column 9",
        ),
        (
            FakeWeatherTool(),
            weather_call("{}", name="book_tour"),
            "There is no tool called book_tour.",
        ),
        (
            FakeWeatherTool(error=ToolError("The forecast service is down.")),
            weather_call('{"city": "Dubai", "date": "2026-10-09"}'),
            "The forecast service is down.",
        ),
        (
            FakeWeatherTool(seconds=0.2),
            weather_call('{"city": "Dubai", "date": "2026-10-09"}'),
            "get_weather took longer than 0.05 seconds.",
        ),
    ],
    ids=["missing argument", "broken JSON", "unknown tool", "tool error", "too slow"],
)
def test_a_bad_call_becomes_an_error_result(tool: FakeWeatherTool, call: ToolCall, expected: str) -> None:
    toolbox = Toolbox([tool], TickingClock(), timeout_seconds=0.05)

    (result,) = asyncio.run(toolbox.run_all([call], "turn-1"))

    assert ToolFailure.model_validate_json(result).error == expected


def test_calls_run_side_by_side_and_results_keep_the_call_order() -> None:
    toolbox = Toolbox([NapTool()], TickingClock(), TOOL_TIMEOUT_SECONDS)
    calls = [
        ToolCall(call_id="slow", name="nap", arguments='{"seconds": 0.2}'),
        ToolCall(call_id="quick", name="nap", arguments='{"seconds": 0.1}'),
    ]

    started = time.perf_counter()
    results = asyncio.run(toolbox.run_all(calls, "turn-1"))

    assert results == ["0.2", "0.1"]
    # One after the other would take 0.3 s.
    assert time.perf_counter() - started < 0.28
