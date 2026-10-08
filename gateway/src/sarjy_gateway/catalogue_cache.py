from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from sarjy_gateway.catalogue import CatalogueUnavailableError


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sarjy_gateway.catalogue import (
        Catalogue,
        CatalogueContext,
        ProductType,
        TourDetails,
        TourQuery,
        TourSearch,
    )


logger = logging.getLogger(__name__)

# Searches come from what travellers say, so the number of different keys has no natural
# limit on a public URL; past this, the oldest copy goes.
MAX_ENTRIES = 256


@dataclass(frozen=True)
class Entry[Value]:
    value: Value
    stored_at: float


# Serves a copy younger than `fresh_seconds` without asking SayTech. Older copies are
# kept as the last known good answer: if SayTech is unavailable, the copy is served at
# any age, with a warning, so a demo survives an outage (D-58).
class LastGoodCache[Key, Value]:
    def __init__(self, clock: Callable[[], float], fresh_seconds: float, max_entries: int) -> None:
        self._clock = clock
        self._fresh_seconds = fresh_seconds
        self._max_entries = max_entries
        self._entries: dict[Key, Entry[Value]] = {}

    async def get(self, key: Key, fetch: Callable[[], Awaitable[Value]]) -> Value:
        entry = self._entries.get(key)
        now = self._clock()
        if entry is not None and now - entry.stored_at < self._fresh_seconds:
            return entry.value
        # A refusal such as an unknown city is SayTech's real answer, so only
        # unavailability falls back to the old copy.
        try:
            value = await fetch()
        except CatalogueUnavailableError as error:
            if entry is None:
                raise
            logger.warning(
                "SayTech unavailable, serving a copy %(age_seconds)s s old",
                {"age_seconds": round(now - entry.stored_at), "error": str(error)},
            )
            return entry.value
        self._store(key, Entry(value, now))
        return value

    def _store(self, key: Key, entry: Entry[Value]) -> None:
        # Deleting first moves the key to the end, so the first key is always the copy
        # stored longest ago. Serving a copy doesn't move it: only storing does.
        self._entries.pop(key, None)
        self._entries[key] = entry
        if len(self._entries) > self._max_entries:
            self._entries.pop(next(iter(self._entries)))


class CachedCatalogue:
    def __init__(self, catalogue: Catalogue, clock: Callable[[], float], fresh_seconds: float) -> None:
        self._catalogue = catalogue
        self._contexts: LastGoodCache[str, CatalogueContext] = LastGoodCache(clock, fresh_seconds, MAX_ENTRIES)
        self._searches: LastGoodCache[TourQuery, TourSearch] = LastGoodCache(clock, fresh_seconds, MAX_ENTRIES)
        self._tours: LastGoodCache[tuple[ProductType, str], TourDetails] = LastGoodCache(
            clock, fresh_seconds, MAX_ENTRIES
        )

    async def context(self) -> CatalogueContext:
        return await self._contexts.get("context", self._catalogue.context)

    async def search(self, query: TourQuery) -> TourSearch:
        return await self._searches.get(query, lambda: self._catalogue.search(query))

    async def tour(self, product_type: ProductType, slug: str) -> TourDetails:
        return await self._tours.get((product_type, slug), lambda: self._catalogue.tour(product_type, slug))
