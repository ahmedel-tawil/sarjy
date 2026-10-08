from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Final, Protocol

import httpx2
from pydantic import BaseModel, ValidationError


# The UAE keeps Gulf Standard Time all year, with no daylight saving, so a fixed offset is
# exact and needs no time zone database in the container.
UAE_TIME = timezone(timedelta(hours=4), "GST")

# Open-Meteo forecasts today and the next 15 days.
FORECAST_DAYS = 16

# The hours read out for a day, in UAE time: enough to suggest a cooler time to go out.
HOURS = (6, 9, 12, 15, 18, 21)


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float


# Fixed coordinates for the UAE's cities, so a forecast needs no geocoding call.
UAE_PLACES = (
    Place("Abu Dhabi", 24.4539, 54.3773),
    Place("Dubai", 25.2048, 55.2708),
    Place("Sharjah", 25.3463, 55.4209),
    Place("Ajman", 25.4052, 55.5136),
    Place("Umm Al Quwain", 25.5647, 55.5552),
    Place("Ras Al Khaimah", 25.8007, 55.9762),
    Place("Fujairah", 25.1288, 56.3265),
    Place("Al Ain", 24.2075, 55.7447),
)


# "Abu Dhabi", "abu-dhabi" and "ABUDHABI" are the same place, as in SayTech's search.
def find_place(name: str) -> Place | None:
    wanted = letters_only(name)
    return next((place for place in UAE_PLACES if letters_only(place.name) == wanted), None)


def letters_only(text: str) -> str:
    return "".join(character for character in text.lower() if character.isalpha())


# Words for the WMO weather codes Open-Meteo uses.
CONDITIONS: Final[dict[int, str]] = {
    0: "clear sky",
    1: "mainly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    80: "light showers",
    81: "showers",
    82: "heavy showers",
    95: "thunderstorms",
    96: "thunderstorms with hail",
    99: "thunderstorms with hail",
}


def conditions_text(code: int) -> str:
    return CONDITIONS.get(code, f"weather code {code}")


class Hour(BaseModel):
    time: str
    temperature_c: float


class DayForecast(BaseModel):
    city: str
    date: str
    conditions: str
    high_c: float
    low_c: float
    chance_of_rain_percent: int | None
    hours: list[Hour]


# The weather service couldn't answer: a timeout, a network error, an error status or a
# response that doesn't match what Open-Meteo sends.
class WeatherUnavailableError(Exception):
    pass


class Weather(Protocol):
    async def forecast(self, place: Place, day: date) -> DayForecast: ...


# --- What Open-Meteo sends for one day, reduced to the fields Sarjy reads.


class ApiDaily(BaseModel):
    time: list[date]
    weather_code: list[int]
    temperature_2m_max: list[float]
    temperature_2m_min: list[float]
    precipitation_probability_max: list[int | None]


class ApiHourly(BaseModel):
    time: list[datetime]
    temperature_2m: list[float | None]


class ApiForecast(BaseModel):
    daily: ApiDaily
    hourly: ApiHourly


class OpenMeteoWeather:
    def __init__(self, client: httpx2.AsyncClient, url: str, timeout_seconds: float) -> None:
        self._client = client
        self._url = url
        self._timeout_seconds = timeout_seconds

    async def forecast(self, place: Place, day: date) -> DayForecast:
        params = (
            ("latitude", str(place.latitude)),
            ("longitude", str(place.longitude)),
            ("daily", "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max"),
            ("hourly", "temperature_2m"),
            # Days and hours in UAE time, so "tomorrow afternoon" means the traveller's.
            ("timezone", "Asia/Dubai"),
            ("start_date", day.isoformat()),
            ("end_date", day.isoformat()),
        )
        try:
            response = await self._client.get(self._url, params=params, timeout=self._timeout_seconds)
        except httpx2.HTTPError as error:
            message = f"Open-Meteo request failed: {type(error).__name__}"
            raise WeatherUnavailableError(message) from error
        if response.is_error:
            message = f"Open-Meteo answered HTTP {response.status_code}"
            raise WeatherUnavailableError(message)
        return day_forecast(place, parse_forecast(response.content))


def parse_forecast(body: bytes) -> ApiForecast:
    try:
        forecast = ApiForecast.model_validate_json(body)
    except ValidationError as error:
        message = "Open-Meteo sent a forecast that does not match its format"
        raise WeatherUnavailableError(message) from error
    if not forecast.daily.time:
        message = "Open-Meteo sent no day"
        raise WeatherUnavailableError(message)
    return forecast


def day_forecast(place: Place, forecast: ApiForecast) -> DayForecast:
    daily = forecast.daily
    hours = [
        Hour(time=f"{moment:%H:%M}", temperature_c=temperature)
        for moment, temperature in zip(forecast.hourly.time, forecast.hourly.temperature_2m, strict=True)
        if moment.hour in HOURS and temperature is not None
    ]
    return DayForecast(
        city=place.name,
        date=daily.time[0].isoformat(),
        conditions=conditions_text(daily.weather_code[0]),
        high_c=daily.temperature_2m_max[0],
        low_c=daily.temperature_2m_min[0],
        chance_of_rain_percent=daily.precipitation_probability_max[0],
        hours=hours,
    )
