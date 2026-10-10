from typing import TYPE_CHECKING, Final

from pydantic import ValidationError

from sarjy_gateway.links import tours_in
from sarjy_gateway.tour_tools import CheckAvailabilityArguments, GetTourArguments, SearchToursArguments
from sarjy_gateway.weather_tool import GetWeatherArguments


if TYPE_CHECKING:
    from collections.abc import Sequence
    import datetime

    from sarjy_gateway.llm import ToolCall


# Tools whose activity says the same whatever their arguments.
FIXED_ACTIVITIES: Final = {"remember_fact": "Noting that down", "forget_fact": "Forgetting that"}

# A weekday name is clear only within the coming week.
DAYS_IN_A_WEEK = 7


# What Sarjy is doing while a tool runs, shown under the orb and read by screen readers
# (D-94). Made from fixed templates and the call's arguments, never by the model. `today`
# is the date the model was told, so "tomorrow" means what the model meant; a call whose
# arguments don't parse has no activity, and the tool's error reaches the model as usual.
def activity_of(call: ToolCall, today: datetime.date, tool_results: Sequence[str]) -> str | None:
    if call.name in FIXED_ACTIVITIES:
        return FIXED_ACTIVITIES[call.name]
    try:
        return described(call, today, tool_results)
    except ValidationError:
        return None


# The words for a call whose wording depends on its arguments.
def described(call: ToolCall, today: datetime.date, tool_results: Sequence[str]) -> str | None:
    match call.name:
        case "search_tours":
            return search_activity(SearchToursArguments.model_validate_json(call.arguments))
        case "get_tour":
            return tour_activity(GetTourArguments.model_validate_json(call.arguments), tool_results)
        case "check_availability":
            return availability_activity(CheckAvailabilityArguments.model_validate_json(call.arguments), tool_results)
        case "get_weather":
            return weather_activity(GetWeatherArguments.model_validate_json(call.arguments), today)
        case _:
            return None


def search_activity(search: SearchToursArguments) -> str:
    return "Looking for tours" if search.city is None else f"Looking for tours in {search.city}"


# The model takes a tour's slug from a search result, so this turn's searches give its name.
def tour_activity(tour: GetTourArguments, tool_results: Sequence[str]) -> str:
    names = {found.slug: found.name for found in tours_in(tool_results) if found.slug is not None}
    return f"Reading about {names[tour.slug]}" if tour.slug in names else "Reading about that tour"


def availability_activity(check: CheckAvailabilityArguments, tool_results: Sequence[str]) -> str:
    names = {found.slug: found.name for found in tours_in(tool_results) if found.slug is not None}
    return f"Checking availability for {names[check.slug]}" if check.slug in names else "Checking availability"


def weather_activity(weather: GetWeatherArguments, today: datetime.date) -> str:
    match (weather.date - today).days:
        case 0:
            day = "today's"
        case 1:
            day = "tomorrow's"
        case days if 1 < days < DAYS_IN_A_WEEK:
            day = f"{weather.date:%A}'s"
        case _:
            return f"Checking the weather in {weather.city} for {weather.date.day} {weather.date:%B}"
    return f"Checking {day} weather in {weather.city}"
