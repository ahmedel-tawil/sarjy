import asyncio
from dataclasses import dataclass
from functools import partial
import logging

import pytest
from sarjy_gateway.catalogue import CatalogueQueryError, CatalogueUnavailableError, TourQuery, TourSearch
from sarjy_gateway.catalogue_cache import CachedCatalogue, LastGoodCache

from gateway.tests.fakes import FERRARI, FakeCatalogue, ManualClock


FIVE_MINUTES = 300.0
ABU_DHABI = TourQuery(query=None, city="Abu Dhabi", category=None, max_price_aed=400, accessible=None, limit=5)
DUBAI = TourQuery(query=None, city="Dubai", category=None, max_price_aed=None, accessible=None, limit=5)
SHARJAH = TourQuery(query=None, city="Sharjah", category=None, max_price_aed=None, accessible=None, limit=5)


@dataclass(frozen=True)
class Cached:
    catalogue: CachedCatalogue
    saytech: FakeCatalogue
    clock: ManualClock


def cached() -> Cached:
    saytech = FakeCatalogue()
    clock = ManualClock()
    return Cached(CachedCatalogue(saytech, clock, FIVE_MINUTES), saytech, clock)


def test_a_repeated_search_within_five_minutes_is_not_asked_again() -> None:
    setup = cached()

    asyncio.run(setup.catalogue.search(ABU_DHABI))
    setup.clock.now = FIVE_MINUTES - 1
    asyncio.run(setup.catalogue.search(ABU_DHABI))

    assert setup.saytech.queries == [ABU_DHABI]


def test_an_older_copy_is_refreshed() -> None:
    setup = cached()

    asyncio.run(setup.catalogue.search(ABU_DHABI))
    setup.clock.now = FIVE_MINUTES
    asyncio.run(setup.catalogue.search(ABU_DHABI))

    assert setup.saytech.queries == [ABU_DHABI, ABU_DHABI]


def test_different_questions_are_cached_separately() -> None:
    setup = cached()

    for query in (ABU_DHABI, DUBAI, ABU_DHABI):
        asyncio.run(setup.catalogue.search(query))
    for _ in range(2):
        asyncio.run(setup.catalogue.tour("tour", FERRARI.slug))
        asyncio.run(setup.catalogue.context())

    assert setup.saytech.queries == [ABU_DHABI, DUBAI]
    assert setup.saytech.lookups == [("tour", FERRARI.slug)]


def test_when_saytech_is_down_the_last_good_copy_is_served_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    setup = cached()
    first = asyncio.run(setup.catalogue.search(ABU_DHABI))

    setup.saytech.error = CatalogueUnavailableError("SayTech answered HTTP 503")
    setup.clock.now = 3600
    with caplog.at_level(logging.WARNING, logger="sarjy_gateway.catalogue_cache"):
        again = asyncio.run(setup.catalogue.search(ABU_DHABI))

    assert again == first
    assert caplog.messages == ["SayTech unavailable, serving a copy 3600 s old"]


def test_when_saytech_is_down_and_there_is_no_copy_the_failure_stands() -> None:
    setup = cached()
    setup.saytech.error = CatalogueUnavailableError("SayTech request failed: ConnectTimeout")

    with pytest.raises(CatalogueUnavailableError):
        asyncio.run(setup.catalogue.search(ABU_DHABI))


def test_a_refusal_is_saytechs_answer_not_an_outage() -> None:
    setup = cached()
    asyncio.run(setup.catalogue.search(ABU_DHABI))

    setup.saytech.error = CatalogueQueryError("No destination matches 'abu dhabi'.")
    setup.clock.now = FIVE_MINUTES

    with pytest.raises(CatalogueQueryError):
        asyncio.run(setup.catalogue.search(ABU_DHABI))


def test_past_the_limit_the_copy_stored_longest_ago_is_dropped() -> None:
    saytech = FakeCatalogue()
    cache: LastGoodCache[TourQuery, TourSearch] = LastGoodCache(ManualClock(), FIVE_MINUTES, max_entries=2)

    async def ask(*queries: TourQuery) -> None:
        for query in queries:
            await cache.get(query, partial(saytech.search, query))

    asyncio.run(ask(ABU_DHABI, DUBAI, ABU_DHABI, SHARJAH, ABU_DHABI, DUBAI))

    # Reusing Abu Dhabi doesn't make it newer. Storing Sharjah drops Abu Dhabi, stored
    # longest ago; storing Abu Dhabi again drops Dubai; so both are asked a second time.
    assert saytech.queries == [ABU_DHABI, DUBAI, SHARJAH, ABU_DHABI, DUBAI]
