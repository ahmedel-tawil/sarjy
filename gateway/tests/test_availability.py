import asyncio
import datetime
from pathlib import Path

import httpx2
from pydantic import ValidationError
import pytest
from sarjy_gateway.activity import activity_of
from sarjy_gateway.catalogue import (
    AvailabilityQuery,
    CatalogueQueryError,
    SayTechCatalogue,
    TourAvailability,
)
from sarjy_gateway.links import tour_links
from sarjy_gateway.llm import ToolCall
from sarjy_gateway.tour_tools import CheckAvailabilityTool

from gateway.tests.fakes import FakeAvailability


# Real answers from SayTech's availability endpoint, on a copy of Magic Experience's
# catalogue on 10 Oct 2026 (its README in the SayTech repo, D-99).
FIXTURES = Path(__file__).parent / "fixtures" / "saytech"
BASE_URL = "https://magicexperience.api.saytech.ae/api/v1/public/assistant"
SATURDAY = datetime.date(2026, 10, 17)


def saved(name: str, status: int = 200) -> httpx2.Response:
    return httpx2.Response(status, content=(FIXTURES / f"{name}.json").read_bytes())


def availability(answer: httpx2.Response, query: AvailabilityQuery, seen: list[httpx2.Request]) -> TourAvailability:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return answer

    catalogue = SayTechCatalogue(httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), BASE_URL, 3.0)
    return asyncio.run(catalogue.availability(query))


def query(slug: str, *, days: int = 1, adults: int | None = None, children: int | None = None) -> AvailabilityQuery:
    return AvailabilityQuery(
        product_type="tour", slug=slug, first_day=SATURDAY, days=days, adults=adults, children=children, infants=None
    )


def test_one_day_for_a_party_sends_the_date_and_party_and_keeps_the_price() -> None:
    seen: list[httpx2.Request] = []

    found = availability(
        saved("availability_ferrari_party"), query("ferrari-world-abu-dhbai", adults=2, children=2), seen
    )

    assert seen[0].url.path == "/api/v1/public/assistant/products/tour/ferrari-world-abu-dhbai/availability/"
    assert dict(seen[0].url.params) == {"date": "2026-10-17", "adults": "2", "children": "2"}
    assert (found.name, found.link, found.tracked) == (
        "Ferrari World Abu Dhabi Tickets",
        "https://magicexperience.ae/tours/ferrari-world-abu-dhbai",
        True,
    )
    general = found.days[0].tickets[1]
    assert (general.name, general.status, general.times) == ("Ferrari World General Admission", "available", [])
    assert (general.price, general.party_total) == ("from AED 345", "AED 1380 for the party")


def test_a_range_sends_from_and_to_and_gives_each_days_status_without_times() -> None:
    seen: list[httpx2.Request] = []

    found = availability(saved("availability_louvre_range"), query("louvre-abu-dhabi-18-years-and-above", days=4), seen)

    assert dict(seen[0].url.params) == {"from": "2026-10-17", "to": "2026-10-20"}
    assert [(day.weekday, day.status) for day in found.days] == [
        ("Saturday", "available"),
        ("Sunday", "available"),
        ("Monday", "closed"),
        ("Tuesday", "available"),
    ]
    assert all(ticket.times is None and ticket.price is None for day in found.days for ticket in day.tickets)


# SayTech has no availability data for the buggy: "unknown", never "sold out".
def test_an_untracked_tour_stays_unknown_with_no_total() -> None:
    found = availability(saved("availability_buggy_untracked"), query("DUNE- BUGGY", adults=2, children=2), [])

    ticket = found.days[0].tickets[0]
    assert (found.tracked, found.days[0].status, ticket.status) == (False, "unknown", "unknown")
    assert (ticket.price, ticket.party_total) == ("price on request", None)


def test_a_slug_with_spaces_is_encoded_and_departures_are_kept_for_one_day() -> None:
    seen: list[httpx2.Request] = []

    found = availability(saved("availability_helicopter_unknown"), query("Helicopter - Flight", adults=2), seen)

    assert seen[0].url.raw_path.startswith(
        b"/api/v1/public/assistant/products/tour/Helicopter%20-%20Flight/availability/"
    )
    times = found.days[0].tickets[0].times
    assert times is not None
    assert [(time.time, time.status, time.left) for time in times] == [
        ("09:25", "unknown", None),
        ("09:40", "unknown", None),
        ("09:50", "unknown", None),
    ]


def test_a_date_in_the_past_is_explained_for_the_model() -> None:
    with pytest.raises(CatalogueQueryError) as raised:
        availability(saved("error_date_in_past", 400), query("ferrari-world-abu-dhbai"), [])

    assert str(raised.value) == "2026-10-09 is in the past."


def louvre_week() -> TourAvailability:
    return availability(saved("availability_louvre_range"), query("louvre-abu-dhabi-18-years-and-above", days=4), [])


def test_the_tool_asks_for_the_days_and_party_the_model_gave() -> None:
    catalogue = FakeAvailability(louvre_week())
    arguments = '{"slug": "louvre-abu-dhabi-18-years-and-above", "date": "2026-10-17", "days": 4, "adults": 2}'

    answer = asyncio.run(CheckAvailabilityTool(catalogue).run(arguments))

    assert catalogue.queries == [
        AvailabilityQuery(
            product_type="tour",
            slug="louvre-abu-dhabi-18-years-and-above",
            first_day=SATURDAY,
            days=4,
            adults=2,
            children=None,
            infants=None,
        )
    ]
    assert '"status":"closed"' in answer


def test_the_tool_refuses_more_than_a_week() -> None:
    with pytest.raises(ValidationError):
        asyncio.run(
            CheckAvailabilityTool(FakeAvailability(louvre_week())).run('{"slug": "x", "date": "2026-10-17", "days": 8}')
        )


# The answer names the tour at its top level, like get_tour's, so its page goes beside the
# reply and the next check can be named on the line under the orb.
def test_an_availability_answer_links_and_names_its_tour() -> None:
    answer = louvre_week().model_dump_json(exclude_none=True)
    arguments = '{"slug": "louvre-abu-dhabi-18-years-and-above", "date": "2026-10-17"}'
    call = ToolCall(call_id="call-1", name="check_availability", arguments=arguments)

    links = tour_links("The Louvre Abu Dhabi is open on Saturday.", [answer])

    assert [link.url for link in links] == ["https://magicexperience.ae/tours/louvre-abu-dhabi-18-years-and-above"]
    assert activity_of(call, SATURDAY, [answer]) == "Checking availability for Louvre Abu Dhabi Ticket"
