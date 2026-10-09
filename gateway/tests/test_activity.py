import datetime

import pytest
from sarjy_gateway.activity import activity_of
from sarjy_gateway.catalogue import Tour, TourSearch
from sarjy_gateway.llm import ToolCall


FRIDAY = datetime.date(2026, 10, 9)
BUGGY = Tour(
    name="Buggy Dune Bashing",
    type="tour",
    slug="buggy-dune-bashing",
    city="Dubai",
    price="price on request",
    accessible=False,
    link="https://me.example/buggy",
)
BUGGY_SEARCH = TourSearch(tours=[BUGGY], total=1).model_dump_json()


def activity(name: str, arguments: str, tool_results: list[str] | None = None) -> str | None:
    return activity_of(ToolCall(call_id="call-1", name=name, arguments=arguments), FRIDAY, tool_results or [])


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ('{"city": "Abu Dhabi", "max_price_aed": 400}', "Looking for tours in Abu Dhabi"),
        ('{"query": "buggy dune bashing"}', "Looking for tours"),
    ],
    ids=["a city", "no city"],
)
def test_a_search_names_its_city(arguments: str, expected: str) -> None:
    assert activity("search_tours", arguments) == expected


def test_a_tour_is_named_from_this_turns_search() -> None:
    reading = activity("get_tour", '{"slug": "buggy-dune-bashing"}', [BUGGY_SEARCH])

    assert reading == "Reading about Buggy Dune Bashing"


def test_a_tour_no_search_returned_is_that_tour() -> None:
    assert activity("get_tour", '{"slug": "louvre-abu-dhabi"}', [BUGGY_SEARCH]) == "Reading about that tour"


@pytest.mark.parametrize(
    ("arguments", "expected"),
    [
        ('{"city": "Abu Dhabi", "date": "2026-10-09"}', "Checking today's weather in Abu Dhabi"),
        ('{"date": "2026-10-10"}', "Checking tomorrow's weather in Dubai"),
        ('{"city": "Dubai", "date": "2026-10-15"}', "Checking Thursday's weather in Dubai"),
        ('{"city": "Dubai", "date": "2026-10-16"}', "Checking the weather in Dubai for 16 October"),
    ],
    ids=["today", "tomorrow, no city", "within the week", "next week"],
)
def test_the_weather_day_is_said_as_the_traveller_would(arguments: str, expected: str) -> None:
    assert activity("get_weather", arguments) == expected


@pytest.mark.parametrize(
    ("name", "expected"), [("remember_fact", "Noting that down"), ("forget_fact", "Forgetting that")]
)
def test_memory_tools_have_fixed_words(name: str, expected: str) -> None:
    assert activity(name, '{"key": "name", "value": "Sam"}') == expected


@pytest.mark.parametrize(
    ("name", "arguments"), [("get_weather", '{"city": "Dubai"}'), ("search_tours", "{"), ("book_tour", "{}")]
)
def test_a_call_that_cant_be_read_has_no_activity(name: str, arguments: str) -> None:
    assert activity(name, arguments) is None
