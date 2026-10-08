import asyncio
from datetime import UTC, date, datetime

from pydantic import ValidationError
import pytest
from sarjy_gateway.tools import ToolError
from sarjy_gateway.weather import DayForecast, WeatherUnavailableError
from sarjy_gateway.weather_tool import UNAVAILABLE, GetWeatherTool

from gateway.tests.fakes import FakeWeather


# 18:00 in UAE time on 8 October 2026.
EVENING_OF_THE_8TH = datetime(2026, 10, 8, 14, 0, tzinfo=UTC).timestamp()
# 01:30 in UAE time on 9 October, while it is still the 8th in UTC.
AFTER_MIDNIGHT_IN_THE_UAE = datetime(2026, 10, 8, 21, 30, tzinfo=UTC).timestamp()


def tool_at(timestamp: float, weather: FakeWeather) -> GetWeatherTool:
    return GetWeatherTool(weather, lambda: timestamp)


def test_a_forecast_is_asked_for_the_place_and_day() -> None:
    weather = FakeWeather()

    result = asyncio.run(tool_at(EVENING_OF_THE_8TH, weather).run('{"city": "dubai", "date": "2026-10-09"}'))

    assert weather.requests == [("Dubai", date(2026, 10, 9))]
    assert DayForecast.model_validate_json(result).high_c == pytest.approx(38.3)


@pytest.mark.parametrize("day", ["2026-10-08", "2026-10-23"], ids=["today", "fifteen days ahead"])
def test_today_and_the_last_forecast_day_are_both_covered(day: str) -> None:
    weather = FakeWeather()

    asyncio.run(tool_at(EVENING_OF_THE_8TH, weather).run(f'{{"city": "Dubai", "date": "{day}"}}'))

    assert len(weather.requests) == 1


@pytest.mark.parametrize(
    ("timestamp", "day", "expected"),
    [
        (EVENING_OF_THE_8TH, "2026-10-24", "No forecast for 2026-10-24: forecasts cover 2026-10-08 to 2026-10-23."),
        (EVENING_OF_THE_8TH, "2026-10-07", "No forecast for 2026-10-07: forecasts cover 2026-10-08 to 2026-10-23."),
        (
            AFTER_MIDNIGHT_IN_THE_UAE,
            "2026-10-08",
            "No forecast for 2026-10-08: forecasts cover 2026-10-09 to 2026-10-24.",
        ),
    ],
    ids=["too far ahead", "already past", "today is the UAE's date, not UTC's"],
)
def test_a_day_without_a_forecast_is_explained_without_asking(timestamp: float, day: str, expected: str) -> None:
    weather = FakeWeather()

    with pytest.raises(ToolError) as raised:
        asyncio.run(tool_at(timestamp, weather).run(f'{{"city": "Dubai", "date": "{day}"}}'))

    assert str(raised.value) == expected
    assert weather.requests == []


def test_an_unknown_city_lists_the_known_ones() -> None:
    with pytest.raises(ToolError) as raised:
        asyncio.run(tool_at(EVENING_OF_THE_8TH, FakeWeather()).run('{"city": "Paris", "date": "2026-10-09"}'))

    assert str(raised.value).startswith("No forecast for Paris. Known places: Abu Dhabi, Dubai, Sharjah")


def test_an_outage_reaches_the_model_as_one_sentence() -> None:
    weather = FakeWeather(error=WeatherUnavailableError("Open-Meteo answered HTTP 503"))

    with pytest.raises(ToolError) as raised:
        asyncio.run(tool_at(EVENING_OF_THE_8TH, weather).run('{"city": "Dubai", "date": "2026-10-09"}'))

    assert str(raised.value) == UNAVAILABLE


@pytest.mark.parametrize(
    "arguments",
    ['{"city": "Dubai", "date": "tomorrow"}', '{"city": "Dubai"}', '{"city": "", "date": "2026-10-09"}'],
    ids=["date in words", "no date", "empty city"],
)
def test_invalid_arguments_are_caught_before_asking(arguments: str) -> None:
    weather = FakeWeather()

    with pytest.raises(ValidationError):
        asyncio.run(tool_at(EVENING_OF_THE_8TH, weather).run(arguments))

    assert weather.requests == []
