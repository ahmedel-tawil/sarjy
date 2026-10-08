from dataclasses import dataclass
from typing import Literal, Protocol
from urllib.parse import quote

import httpx2
from pydantic import BaseModel, ValidationError


type ProductType = Literal["tour", "transfer"]


# --- What SayTech's assistant API sends (D-56). Fields Sarjy doesn't use are left out,
# and Pydantic ignores them, so SayTech can add fields without breaking Sarjy.


class ApiPrice(BaseModel):
    currency: str
    from_amount: float | None
    on_request: bool


class ApiPriceLine(BaseModel):
    label: str
    amount: float


class ApiTicketPrice(ApiPrice):
    lines: list[ApiPriceLine]


class ApiProduct(BaseModel):
    type: ProductType
    slug: str
    name: str
    city: str | None
    accessible: bool
    price: ApiPrice
    url: str | None


class ApiSearch(BaseModel):
    results: list[ApiProduct]
    total: int


class ApiDuration(BaseModel):
    value: float
    unit: str


class ApiChildren(BaseModel):
    age_from: int | None
    age_to: int | None
    infant_max_age: int | None
    note: str | None


class ApiCancellation(BaseModel):
    refundable: bool
    note: str | None


class ApiTicket(BaseModel):
    name: str
    price: ApiTicketPrice
    duration: ApiDuration | None
    children: ApiChildren | None
    cancellation: ApiCancellation | None


class ApiProductDetail(ApiProduct):
    summary: str
    duration: ApiDuration | None
    tickets: list[ApiTicket]
    restrictions: list[str]
    notes: list[str]
    requirements: list[str]
    languages: list[str]


class ApiOperator(BaseModel):
    name: str
    website: str | None


class ApiCity(BaseModel):
    name: str
    tour_count: int


class Faq(BaseModel):
    question: str
    answer: str


class ApiContext(BaseModel):
    operator: ApiOperator
    cities: list[ApiCity]
    categories: list[str]
    faqs: list[Faq]


class ApiErrorDetails(BaseModel):
    known_cities: list[str] = []
    known_categories: list[str] = []


class ApiErrorBody(BaseModel):
    code: str
    message: str
    details: ApiErrorDetails


class ApiError(BaseModel):
    error: ApiErrorBody


# --- What the model reads: only what it needs to answer, so tool results stay small
# (experiment 5). A price is already words, so a missing one can never be read as zero.


class Tour(BaseModel):
    name: str
    type: ProductType
    slug: str
    # As SayTech has it: null for a product with no destination, never guessed.
    city: str | None
    price: str
    accessible: bool
    link: str | None


class TourSearch(BaseModel):
    tours: list[Tour]
    # Matches before the limit, so the model can say "and 2 more".
    total: int


class TicketDetails(BaseModel):
    name: str
    # "adult: AED 345", one per passenger type; empty when the price is on request.
    prices: list[str]
    price: str
    duration: str | None
    children: ApiChildren | None
    cancellation: ApiCancellation | None


class TourDetails(Tour):
    summary: str
    duration: str | None
    tickets: list[TicketDetails]
    restrictions: list[str]
    notes: list[str]
    requirements: list[str]
    languages: list[str]


class City(BaseModel):
    name: str
    tours: int


class CatalogueContext(BaseModel):
    operator: str
    website: str | None
    cities: list[City]
    categories: list[str]
    faqs: list[Faq]


# A search; None leaves that filter out.
@dataclass(frozen=True)
class TourQuery:
    query: str | None
    city: str | None
    category: str | None
    max_price_aed: float | None
    accessible: bool | None
    limit: int


# SayTech understood the question and turned it down, for example an unknown city. The
# message says why in words the model can use, including the values it knows.
class CatalogueQueryError(Exception):
    pass


# SayTech couldn't answer: a timeout, a network error, rate limiting, a server error or
# a response that doesn't match the contract.
class CatalogueUnavailableError(Exception):
    pass


class Catalogue(Protocol):
    async def context(self) -> CatalogueContext: ...

    async def search(self, query: TourQuery) -> TourSearch: ...

    async def tour(self, product_type: ProductType, slug: str) -> TourDetails: ...


class SayTechCatalogue:
    def __init__(self, client: httpx2.AsyncClient, base_url: str, timeout_seconds: float) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def context(self) -> CatalogueContext:
        context = parse(ApiContext, await self._get("context/", ()))
        return CatalogueContext(
            operator=context.operator.name,
            website=context.operator.website,
            cities=[City(name=city.name, tours=city.tour_count) for city in context.cities],
            categories=context.categories,
            faqs=context.faqs,
        )

    async def search(self, query: TourQuery) -> TourSearch:
        search = parse(ApiSearch, await self._get("products/", search_params(query)))
        return TourSearch(tours=[lean_tour(product) for product in search.results], total=search.total)

    async def tour(self, product_type: ProductType, slug: str) -> TourDetails:
        # Slugs are stored as typed, spaces included ("DUNE- BUGGY"); safe="" also encodes
        # a slash, so a slug can never reach another path.
        detail = parse(ApiProductDetail, await self._get(f"products/{product_type}/{quote(slug, safe='')}/", ()))
        return TourDetails(
            name=detail.name,
            type=detail.type,
            slug=detail.slug,
            city=detail.city,
            price=price_text(detail.price),
            accessible=detail.accessible,
            link=detail.url,
            summary=detail.summary,
            duration=duration_text(detail.duration),
            tickets=[lean_ticket(ticket) for ticket in detail.tickets],
            restrictions=detail.restrictions,
            notes=detail.notes,
            requirements=detail.requirements,
            languages=detail.languages,
        )

    async def _get(self, path: str, params: tuple[tuple[str, str], ...]) -> bytes:
        try:
            response = await self._client.get(
                f"{self._base_url}/{path}", params=params, timeout=self._timeout_seconds
            )
        except httpx2.HTTPError as error:
            message = f"SayTech request failed: {type(error).__name__}"
            raise CatalogueUnavailableError(message) from error
        if response.status_code in {httpx2.codes.BAD_REQUEST, httpx2.codes.NOT_FOUND}:
            raise CatalogueQueryError(refusal(response))
        if response.is_error:
            message = f"SayTech answered HTTP {response.status_code}"
            raise CatalogueUnavailableError(message)
        return response.content


def parse[ApiModel: BaseModel](model: type[ApiModel], body: bytes) -> ApiModel:
    try:
        return model.model_validate_json(body)
    except ValidationError as error:
        message = f"SayTech sent a {model.__name__} that does not match the contract"
        raise CatalogueUnavailableError(message) from error


# Only the filters that are set: SayTech refuses unknown parameters, and an empty one would
# still filter.
def search_params(query: TourQuery) -> tuple[tuple[str, str], ...]:
    params = [("limit", str(query.limit))]
    if query.query is not None:
        params.append(("q", query.query))
    if query.city is not None:
        params.append(("city", query.city))
    if query.category is not None:
        params.append(("category", query.category))
    if query.max_price_aed is not None:
        params.append(("max_price", amount_text(query.max_price_aed)))
    if query.accessible is not None:
        params.append(("accessible", "true" if query.accessible else "false"))
    return tuple(params)


# A 400 or 404 from the assistant module explains itself; a 400 in the shared
# middleware's shape (no organisation) is a setup problem, not the model's question.
def refusal(response: httpx2.Response) -> str:
    try:
        error = ApiError.model_validate_json(response.content).error
    except ValidationError as invalid:
        message = f"SayTech answered HTTP {response.status_code} without an assistant error"
        raise CatalogueUnavailableError(message) from invalid
    if error.details.known_cities:
        return f"{error.message} Known cities: {', '.join(error.details.known_cities)}."
    if error.details.known_categories:
        return f"{error.message} Known categories: {', '.join(error.details.known_categories)}."
    return error.message


def lean_tour(product: ApiProduct) -> Tour:
    return Tour(
        name=product.name,
        type=product.type,
        slug=product.slug,
        city=product.city,
        price=price_text(product.price),
        accessible=product.accessible,
        link=product.url,
    )


def lean_ticket(ticket: ApiTicket) -> TicketDetails:
    return TicketDetails(
        name=ticket.name,
        prices=[f"{line.label}: {ticket.price.currency} {amount_text(line.amount)}" for line in ticket.price.lines],
        price=price_text(ticket.price),
        duration=duration_text(ticket.duration),
        children=ticket.children,
        cancellation=ticket.cancellation,
    )


def price_text(price: ApiPrice) -> str:
    if price.on_request or price.from_amount is None:
        return "price on request"
    return f"from {price.currency} {amount_text(price.from_amount)}"


# 345.0 reads as "345", and 112.5 as "112.50".
def amount_text(amount: float) -> str:
    return str(int(amount)) if amount.is_integer() else f"{amount:.2f}"


def duration_text(duration: ApiDuration | None) -> str | None:
    if duration is None:
        return None
    return f"{amount_text(duration.value)} {duration.unit}"
