import datetime
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from sarjy_gateway.catalogue import (
    AvailabilityQuery,
    CatalogueQueryError,
    CatalogueUnavailableError,
    ProductType,
    TourQuery,
)
from sarjy_gateway.llm import ToolSpec
from sarjy_gateway.tools import ToolError


if TYPE_CHECKING:
    from collections.abc import Awaitable

    from sarjy_gateway.catalogue import AvailabilityCatalogue, Catalogue, RawCatalogue


# A spoken answer names two or three tours; five leaves the model room to choose.
SEARCH_LIMIT = 5

UNAVAILABLE = "The tour catalogue can't be reached right now."


# The field descriptions are part of the JSON schema the model reads, so they say how to
# fill each field. The limits match SayTech's, so a bad value is caught before the call.
class SearchToursArguments(BaseModel):
    query: str | None = Field(
        default=None,
        max_length=100,
        description="Words from the tour's name, for a tour asked about by name, such as 'buggy dune bashing'.",
    )
    city: str | None = Field(default=None, max_length=60, description="A UAE city, such as 'Abu Dhabi'.")
    max_price_aed: float | None = Field(
        default=None,
        gt=0,
        le=100_000,
        description="Only tours whose lowest price is at most this many dirhams. Tours with no price are left out.",
    )
    category: str | None = Field(
        default=None, min_length=3, max_length=60, description="A kind of tour, such as 'safari' or 'theme parks'."
    )
    accessible: bool | None = Field(default=None, description="True for wheelchair-accessible tours only.")


# Not called `type`: Qwen sometimes filled an argument of that name with `true`, which
# Groq rejects before Sarjy sees the call (D-59).
class GetTourArguments(BaseModel):
    slug: str = Field(min_length=1, max_length=200, description="The slug from a search result, exactly as given.")
    product_type: ProductType = Field(
        default="tour", description="'transfer' when the search result's type is transfer; otherwise leave it out."
    )


# SayTech's limits: a range of at most a week, and parties of 0 to 50 of each kind.
class CheckAvailabilityArguments(BaseModel):
    slug: str = Field(min_length=1, max_length=200, description="The slug from a search result, exactly as given.")
    product_type: ProductType = Field(
        default="tour", description="'transfer' when the search result's type is transfer; otherwise leave it out."
    )
    date: datetime.date = Field(description="The day to check in UAE time, as YYYY-MM-DD; the first day of a range.")
    days: int = Field(
        default=1,
        ge=1,
        le=7,
        description="How many days from `date` to check, up to 7. Leave it out for one day, which also gives prices.",
    )
    adults: int | None = Field(default=None, ge=0, le=50, description="Adults in the party, when the traveller said.")
    children: int | None = Field(default=None, ge=0, le=50, description="Children in the party.")
    infants: int | None = Field(default=None, ge=0, le=50, description="Infants in the party; they take a place.")


class SearchToursTool:
    spec = ToolSpec(
        "search_tours",
        "Search Magic Experience's tours and activities. Use it for any question about what "
        "to do, what something costs, or a tour by name. Returns up to five tours with their "
        "lowest price, or 'price on request' when there is none.",
        SearchToursArguments.model_json_schema(),
    )

    def __init__(self, catalogue: Catalogue) -> None:
        self._catalogue = catalogue

    async def run(self, arguments: str) -> str:
        query = tour_query(SearchToursArguments.model_validate_json(arguments))
        return await answer_from(self._catalogue.search(query))


class GetTourTool:
    spec = ToolSpec(
        "get_tour",
        "Get one tour's details from a search result: each ticket's adult and child prices, "
        "durations, who children's tickets are for, and the cancellation policy.",
        GetTourArguments.model_json_schema(),
    )

    def __init__(self, catalogue: Catalogue) -> None:
        self._catalogue = catalogue

    async def run(self, arguments: str) -> str:
        tour = GetTourArguments.model_validate_json(arguments)
        return await answer_from(self._catalogue.tour(tour.product_type, tour.slug))


# Live availability straight from SayTech, never from the catalogue's cache: it changes as
# people book (D-99).
class CheckAvailabilityTool:
    spec = ToolSpec(
        "check_availability",
        "Check whether a tour from a search result can be booked on a date, or each day of up "
        "to a week, for the traveller's party: each ticket's status, departure times and places "
        "left, and for a single day the price, with the party's total when SayTech has one.",
        CheckAvailabilityArguments.model_json_schema(),
    )

    def __init__(self, catalogue: AvailabilityCatalogue) -> None:
        self._catalogue = catalogue

    async def run(self, arguments: str) -> str:
        check = CheckAvailabilityArguments.model_validate_json(arguments)
        query = AvailabilityQuery(
            product_type=check.product_type,
            slug=check.slug,
            first_day=check.date,
            days=check.days,
            adults=check.adults,
            children=check.children,
            infants=check.infants,
        )
        return await answer_from(self._catalogue.availability(query))


# Experiment 5 (M3.9): the same two tools, answering with SayTech's response exactly as
# it came instead of the lean results, so only what the model reads changes.
class RawSearchToursTool:
    spec = SearchToursTool.spec

    def __init__(self, catalogue: RawCatalogue) -> None:
        self._catalogue = catalogue

    async def run(self, arguments: str) -> str:
        query = tour_query(SearchToursArguments.model_validate_json(arguments))
        return await raw_answer_from(self._catalogue.raw_search(query))


class RawGetTourTool:
    spec = GetTourTool.spec

    def __init__(self, catalogue: RawCatalogue) -> None:
        self._catalogue = catalogue

    async def run(self, arguments: str) -> str:
        tour = GetTourArguments.model_validate_json(arguments)
        return await raw_answer_from(self._catalogue.raw_tour(tour.product_type, tour.slug))


def tour_query(search: SearchToursArguments) -> TourQuery:
    return TourQuery(
        query=search.query,
        city=search.city,
        category=search.category,
        max_price_aed=search.max_price_aed,
        accessible=search.accessible,
        limit=SEARCH_LIMIT,
    )


async def raw_answer_from(request: Awaitable[str]) -> str:
    try:
        return await request
    except CatalogueQueryError as error:
        raise ToolError(str(error)) from error
    except CatalogueUnavailableError as error:
        raise ToolError(UNAVAILABLE) from error


# SayTech's refusals already explain themselves ("Known cities: ..."), so the model can
# retry; an outage gets one plain sentence the model can pass on. Empty fields are left
# out: every token is sent again on each request of the turn.
async def answer_from(request: Awaitable[BaseModel]) -> str:
    try:
        result = await request
    except CatalogueQueryError as error:
        raise ToolError(str(error)) from error
    except CatalogueUnavailableError as error:
        raise ToolError(UNAVAILABLE) from error
    return result.model_dump_json(exclude_none=True)
