import asyncio

from pydantic import ValidationError
import pytest
from sarjy_gateway.catalogue import CatalogueQueryError, CatalogueUnavailableError, TourQuery, TourSearch
from sarjy_gateway.tools import ToolError
from sarjy_gateway.tour_tools import UNAVAILABLE, GetTourTool, SearchToursTool

from gateway.tests.fakes import FERRARI, FakeCatalogue


def test_a_search_sends_the_models_filters_with_a_limit_of_five() -> None:
    catalogue = FakeCatalogue()

    result = asyncio.run(SearchToursTool(catalogue).run('{"city": "Abu Dhabi", "max_price_aed": 400}'))

    assert catalogue.queries == [
        TourQuery(query=None, city="Abu Dhabi", category=None, max_price_aed=400, accessible=None, limit=5)
    ]
    assert TourSearch.model_validate_json(result).tours == [FERRARI]


def test_get_tour_looks_up_the_type_and_slug_from_a_search_result() -> None:
    catalogue = FakeCatalogue()

    result = asyncio.run(GetTourTool(catalogue).run('{"slug": "DUNE- BUGGY"}'))

    assert catalogue.lookups == [("tour", "DUNE- BUGGY")]
    assert '"prices":["adult: AED 345","child: AED 345"]' in result
    # Empty fields cost tokens on every request of the turn, so they are left out.
    assert "null" not in result


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        (SearchToursTool, '{"max_price_aed": 0}'),
        (SearchToursTool, '{"max_price_aed": "cheap"}'),
        (SearchToursTool, '{"category": "go"}'),
        (SearchToursTool, '{"query": "' + "x" * 101 + '"}'),
        (GetTourTool, '{"product_type": "hotel", "slug": "atlantis"}'),
        (GetTourTool, '{"slug": ""}'),
        (GetTourTool, '{"product_type": "tour"}'),
    ],
    ids=[
        "price of zero",
        "price in words",
        "category too short",
        "query too long",
        "unknown product type",
        "empty slug",
        "missing slug",
    ],
)
def test_invalid_arguments_are_caught_before_asking_saytech(
    tool: type[SearchToursTool | GetTourTool], arguments: str
) -> None:
    catalogue = FakeCatalogue()

    with pytest.raises(ValidationError):
        asyncio.run(tool(catalogue).run(arguments))

    assert (catalogue.queries, catalogue.lookups) == ([], [])


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            CatalogueQueryError("No destination matches 'paris'. Known cities: Abu Dhabi, Dubai, Sharjah."),
            "No destination matches 'paris'. Known cities: Abu Dhabi, Dubai, Sharjah.",
        ),
        (CatalogueUnavailableError("SayTech answered HTTP 503"), UNAVAILABLE),
    ],
    ids=["saytech refuses", "saytech is down"],
)
def test_catalogue_problems_reach_the_model_as_words(error: Exception, expected: str) -> None:
    with pytest.raises(ToolError) as raised:
        asyncio.run(SearchToursTool(FakeCatalogue(error=error)).run('{"city": "Paris"}'))

    assert str(raised.value) == expected
