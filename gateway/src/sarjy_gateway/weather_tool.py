import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from sarjy_gateway.llm import ToolSpec
from sarjy_gateway.tools import ToolError
from sarjy_gateway.weather import FORECAST_DAYS, UAE_PLACES, UAE_TIME, WeatherUnavailableError, find_place


if TYPE_CHECKING:
    from collections.abc import Callable

    from sarjy_gateway.weather import Weather


UNAVAILABLE = "The weather service can't be reached right now."


# Dubai is the default in code, not only in the prompt: told to assume Dubai, the model
# still filled in Abu Dhabi for "is tomorrow good for a desert safari?".
class GetWeatherArguments(BaseModel):
    city: str = Field(
        default="Dubai",
        min_length=1,
        max_length=60,
        description="A UAE city the traveller named. Leave it out if they named none: it is then Dubai.",
    )
    date: datetime.date = Field(description="The day in UAE time, as YYYY-MM-DD.")


class GetWeatherTool:
    spec = ToolSpec(
        "get_weather",
        "The forecast for one day in a UAE city: conditions, high and low in Celsius, chance "
        "of rain, and the temperature through the day in UAE time. Covers today and the next "
        "15 days.",
        GetWeatherArguments.model_json_schema(),
    )

    # `clock` gives the current time in seconds since the epoch, to know today's date.
    def __init__(self, weather: Weather, clock: Callable[[], float]) -> None:
        self._weather = weather
        self._clock = clock

    async def run(self, arguments: str) -> str:
        request = GetWeatherArguments.model_validate_json(arguments)
        place = find_place(request.city)
        if place is None:
            known = ", ".join(place.name for place in UAE_PLACES)
            message = f"No forecast for {request.city}. Known places: {known}."
            raise ToolError(message)
        # Checked here rather than left to Open-Meteo, so the model hears the range in words.
        today = datetime.datetime.fromtimestamp(self._clock(), UAE_TIME).date()
        last = today + datetime.timedelta(days=FORECAST_DAYS - 1)
        if not today <= request.date <= last:
            message = f"No forecast for {request.date}: forecasts cover {today} to {last}."
            raise ToolError(message)
        try:
            forecast = await self._weather.forecast(place, request.date)
        except WeatherUnavailableError as error:
            raise ToolError(UNAVAILABLE) from error
        return forecast.model_dump_json(exclude_none=True)
