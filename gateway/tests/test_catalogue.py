import asyncio
from pathlib import Path

import httpx2
import pytest
from sarjy_gateway.catalogue import (
    ApiCancellation,
    ApiProductDetail,
    Catalogue,
    CatalogueQueryError,
    CatalogueUnavailableError,
    SayTechCatalogue,
    TourQuery,
)

from gateway.tests.fakes import FERRARI, FakeCatalogue


FIXTURES = Path(__file__).parent / "fixtures" / "saytech"
BASE_URL = "https://magicexperience.api.saytech.ae/api/v1/public/assistant"
NO_FILTERS = TourQuery(query=None, city=None, category=None, max_price_aed=None, accessible=None, limit=5)


def saved(name: str, status: int = 200) -> httpx2.Response:
    return httpx2.Response(status, content=(FIXTURES / f"{name}.json").read_bytes())


def catalogue_answering(answer: httpx2.Response, seen: list[httpx2.Request]) -> SayTechCatalogue:
    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return answer

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(handler))
    return SayTechCatalogue(client, BASE_URL, timeout_seconds=3.0)


def test_a_search_sends_only_the_filters_given_and_returns_lean_tours() -> None:
    seen: list[httpx2.Request] = []
    catalogue = catalogue_answering(saved("search_abu_dhabi_under_400"), seen)
    query = TourQuery(query=None, city="Abu Dhabi", category=None, max_price_aed=400, accessible=None, limit=5)

    search = asyncio.run(catalogue.search(query))

    (request,) = seen
    assert request.url.path == "/api/v1/public/assistant/products/"
    assert dict(request.url.params) == {"city": "Abu Dhabi", "max_price": "400", "limit": "5"}
    assert request.extensions["timeout"]["read"] == pytest.approx(3.0)
    assert (len(search.tours), search.total) == (5, 7)
    ferrari = search.tours[0]
    assert ferrari.model_dump() == {
        "name": "Ferrari World Abu Dhabi Tickets",
        "type": "tour",
        "slug": "ferrari-world-abu-dhbai",
        "city": "Abu Dhabi",
        "price": "from AED 345",
        "accessible": True,
        "link": "https://magicexperience.ae/tours/ferrari-world-abu-dhbai",
    }


def test_a_product_without_a_price_is_on_request_never_zero() -> None:
    search = asyncio.run(catalogue_answering(saved("search_buggy_on_request"), []).search(NO_FILTERS))

    buggy = search.tours[0]
    assert (buggy.slug, buggy.price) == ("DUNE- BUGGY", "price on request")


def test_a_product_without_a_destination_keeps_its_missing_city() -> None:
    # SayTech stores the Fujairah safari with no destination; Sarjy doesn't guess one.
    search = asyncio.run(catalogue_answering(saved("search_safari_no_city"), []).search(NO_FILTERS))

    safari = next(tour for tour in search.tours if tour.slug == "dune-desert-safari-from-fujairah")
    assert safari.city is None


def test_a_slug_with_spaces_is_percent_encoded_in_the_detail_path() -> None:
    seen: list[httpx2.Request] = []

    details = asyncio.run(catalogue_answering(saved("detail_helicopter_partly_priced"), seen).tour("tour", "Helicopter - Flight"))

    assert seen[0].url.raw_path == b"/api/v1/public/assistant/products/tour/Helicopter%20-%20Flight/"
    assert details.price == "from AED 715"
    priced = [ticket for ticket in details.tickets if ticket.prices]
    assert len(priced) == 4
    assert all(ticket.price == "price on request" for ticket in details.tickets if not ticket.prices)
    assert any("110" in note for note in details.notes)


def test_a_detail_maps_ticket_prices_policies_and_duration() -> None:
    details = asyncio.run(catalogue_answering(saved("detail_ferrari"), []).tour("tour", "ferrari-world-abu-dhbai"))

    general = next(ticket for ticket in details.tickets if ticket.name == "Ferrari World General Admission")
    # Labels come as SayTech stores them, lower case for Magic Experience.
    assert general.prices == ["adult: AED 345", "child: AED 345"]
    assert general.price == "from AED 345"
    assert general.duration == "8 hours"
    # Both tickets have the same policies, so they are stated once for the tour.
    assert details.every_ticket is not None
    assert details.every_ticket.children is not None
    assert details.every_ticket.children.age_from == 3
    assert details.every_ticket.cancellation is not None
    assert not details.every_ticket.cancellation.refundable
    assert (general.children, general.cancellation) == (None, None)


def test_tickets_with_different_policies_each_keep_their_own() -> None:
    detail = ApiProductDetail.model_validate_json((FIXTURES / "detail_ferrari.json").read_bytes())
    free = ApiCancellation(refundable=True, note="Free cancellation.")
    first = detail.tickets[0].model_copy(update={"cancellation": free})
    changed = detail.model_copy(update={"tickets": [first, *detail.tickets[1:]]})
    catalogue = catalogue_answering(httpx2.Response(200, content=changed.model_dump_json()), [])

    details = asyncio.run(catalogue.tour("tour", "ferrari-world-abu-dhbai"))

    assert details.every_ticket is None
    assert [ticket.cancellation.refundable for ticket in details.tickets if ticket.cancellation] == [True, False]


def test_an_unpriced_product_has_no_ticket_prices() -> None:
    details = asyncio.run(catalogue_answering(saved("detail_buggy_on_request"), []).tour("tour", "DUNE- BUGGY"))

    assert details.price == "price on request"
    assert {ticket.price for ticket in details.tickets} == {"price on request"}
    assert all(ticket.prices == [] for ticket in details.tickets)
    assert details.link == "https://magicexperience.ae/tours/DUNE-%20BUGGY"


def test_the_context_lists_cities_with_their_tour_counts_and_the_faqs() -> None:
    context = asyncio.run(catalogue_answering(saved("context"), []).context())

    assert context.operator == "Magic Experience"
    assert [(city.name, city.tours) for city in context.cities] == [("Abu Dhabi", 7), ("Dubai", 8), ("Sharjah", 0)]
    assert len(context.faqs) == 7
    assert "safari" in context.categories


@pytest.mark.parametrize(
    ("fixture", "status", "expected"),
    [
        ("error_unknown_city", 400, "No destination matches 'paris'. Known cities: Abu Dhabi, Dubai, Sharjah."),
        ("error_no_searchable_words", 400, "q has no searchable words."),
        ("error_not_found", 404, "No tour matches 'does-not-exist'."),
    ],
    ids=["unknown city", "no searchable words", "unknown product"],
)
def test_a_refused_question_explains_itself_for_the_model(fixture: str, status: int, expected: str) -> None:
    with pytest.raises(CatalogueQueryError) as raised:
        asyncio.run(catalogue_answering(saved(fixture, status), []).search(NO_FILTERS))

    assert str(raised.value) == expected


def test_an_unknown_category_lists_the_known_ones() -> None:
    with pytest.raises(CatalogueQueryError) as raised:
        asyncio.run(catalogue_answering(saved("error_unknown_category", 400), []).search(NO_FILTERS))

    assert str(raised.value).startswith("No category matches 'zzz'. Known categories: ")
    assert "safari" in str(raised.value)


@pytest.mark.parametrize(
    "answer",
    [
        httpx2.Response(429, json={"error": "Rate limit exceeded."}),
        httpx2.Response(500, text="Server error"),
        httpx2.Response(400, json={"error": "Organization not specified."}),
        httpx2.Response(200, json={"results": "not a list"}),
    ],
    ids=["rate limited", "server error", "middleware refusal", "response off contract"],
)
def test_saytech_failures_are_unavailable_not_the_models_fault(answer: httpx2.Response) -> None:
    with pytest.raises(CatalogueUnavailableError):
        asyncio.run(catalogue_answering(answer, []).search(NO_FILTERS))


def test_a_timeout_is_unavailable() -> None:
    def handler(request: httpx2.Request) -> httpx2.Response:
        message = "SayTech is slow"
        raise httpx2.ReadTimeout(message, request=request)

    catalogue = SayTechCatalogue(httpx2.AsyncClient(transport=httpx2.MockTransport(handler)), BASE_URL, 3.0)

    with pytest.raises(CatalogueUnavailableError):
        asyncio.run(catalogue.search(NO_FILTERS))


def test_new_fields_from_saytech_are_ignored() -> None:
    answer = httpx2.Response(200, json={"results": [], "total": 0, "added_later": {"anything": True}})

    search = asyncio.run(catalogue_answering(answer, []).search(NO_FILTERS))

    assert (search.tours, search.total) == ([], 0)


def test_the_fake_catalogue_answers_like_the_real_one() -> None:
    fake = FakeCatalogue()
    catalogue: Catalogue = fake

    search = asyncio.run(catalogue.search(NO_FILTERS))
    details = asyncio.run(catalogue.tour("tour", FERRARI.slug))

    assert search.tours == [FERRARI]
    assert details.price == FERRARI.price
    assert (fake.queries, fake.lookups) == ([NO_FILTERS], [("tour", FERRARI.slug)])
