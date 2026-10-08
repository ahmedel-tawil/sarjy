from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from sarjy_gateway.catalogue import CatalogueQueryError, CatalogueUnavailableError, ProductType, TourQuery
from sarjy_gateway.llm import ToolSpec
from sarjy_gateway.tools import ToolError


if TYPE_CHECKING:
    from collections.abc import Awaitable

    from sarjy_gateway.catalogue import Catalogue


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
        search = SearchToursArguments.model_validate_json(arguments)
        query = TourQuery(
            query=search.query,
            city=search.city,
            category=search.category,
            max_price_aed=search.max_price_aed,
            accessible=search.accessible,
            limit=SEARCH_LIMIT,
        )
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
