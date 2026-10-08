import asyncio
from datetime import date
from pathlib import Path

import httpx2
import pytest
from sarjy_gateway.weather import UAE_PLACES, OpenMeteoWeather, Place, WeatherUnavailableError, find_place


FIXTURES = Path(__file__).parent / "fixtures" / "open_meteo"
URL = "https://api.open-meteo.com/v1/forecast"
DUBAI = Place("Dubai", 25.2048, 55.2708)
TOMORROW = date(2026, 10, 9)


def weather_answering(answer: httpx2.Response, seen: list[httpx2.Request]) -> OpenMeteoWeather:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return answer

    return OpenMeteoWeather(httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), URL, timeout_seconds=3.0)


def saved_dubai_forecast() -> httpx2.Response:
    return httpx2.Response(200, content=(FIXTURES / "dubai_2026_10_09.json").read_bytes())


def test_asks_for_one_day_at_the_places_coordinates_in_uae_time() -> None:
    seen: list[httpx2.Request] = []

    asyncio.run(weather_answering(saved_dubai_forecast(), seen).forecast(DUBAI, TOMORROW))

    (request,) = seen
    params = dict(request.url.params)
    assert (params["latitude"], params["longitude"]) == ("25.2048", "55.2708")
    assert (params["start_date"], params["end_date"]) == ("2026-10-09", "2026-10-09")
    assert params["timezone"] == "Asia/Dubai"
    assert request.extensions["timeout"]["read"] == pytest.approx(3.0)


def test_a_saved_forecast_becomes_a_short_day_summary() -> None:
    forecast = asyncio.run(weather_answering(saved_dubai_forecast(), []).forecast(DUBAI, TOMORROW))

    assert forecast.model_dump() == {
        "city": "Dubai",
        "date": "2026-10-09",
        "conditions": "clear sky",
        "high_c": 38.3,
        "low_c": 30.9,
        "chance_of_rain_percent": 0,
        "hours": [
            {"time": "06:00", "temperature_c": 30.9},
            {"time": "09:00", "temperature_c": 33.1},
            {"time": "12:00", "temperature_c": 37.5},
            {"time": "15:00", "temperature_c": 35.4},
            {"time": "18:00", "temperature_c": 33.3},
            {"time": "21:00", "temperature_c": 32.3},
        ],
    }


@pytest.mark.parametrize(
    "answer",
    [
        httpx2.Response(400, content=(FIXTURES / "error_out_of_range.json").read_bytes()),
        httpx2.Response(503, text="Service unavailable"),
        httpx2.Response(200, json={"daily": {"time": []}, "hourly": {"time": [], "temperature_2m": []}}),
        httpx2.Response(200, json={"reason": "not a forecast"}),
    ],
    ids=["out of range", "server error", "no day", "not a forecast"],
)
def test_a_failed_answer_means_the_weather_is_unavailable(answer: httpx2.Response) -> None:
    with pytest.raises(WeatherUnavailableError):
        asyncio.run(weather_answering(answer, []).forecast(DUBAI, TOMORROW))


def test_a_timeout_means_the_weather_is_unavailable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        message = "Open-Meteo is slow"
        raise httpx2.ReadTimeout(message, request=request)

    weather = OpenMeteoWeather(httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), URL, 3.0)

    with pytest.raises(WeatherUnavailableError):
        asyncio.run(weather.forecast(DUBAI, TOMORROW))


@pytest.mark.parametrize("name", ["Abu Dhabi", "abu-dhabi", "ABUDHABI", " abu dhabi "])
def test_a_city_is_found_however_it_is_written(name: str) -> None:
    assert find_place(name) == UAE_PLACES[0]


def test_a_city_outside_the_uae_is_not_found() -> None:
    assert find_place("Paris") is None
