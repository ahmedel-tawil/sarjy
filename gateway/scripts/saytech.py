# Asks the real SayTech assistant API the demo scenarios' questions, and reports each
# call's time and how big its lean result is for the model. No key needed.
# Run from the repository root:
#     uv run python gateway/scripts/saytech.py

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import httpx2
from sarjy_gateway.catalogue import SayTechCatalogue, TourQuery
from sarjy_gateway.settings import Settings


if TYPE_CHECKING:
    from collections.abc import Awaitable

    from pydantic import BaseModel


logger = logging.getLogger("saytech")

ABU_DHABI_UNDER_400 = TourQuery(
    query=None, city="Abu Dhabi", category=None, max_price_aed=400, accessible=None, limit=5
)
BUGGY_BY_NAME = TourQuery(
    query="buggy dune bashing tour", city=None, category=None, max_price_aed=None, accessible=None, limit=5
)


async def timed(label: str, call: Awaitable[BaseModel]) -> None:
    started = time.perf_counter()
    result = await call
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("%-34s %5.0f ms  %5d bytes for the model", label, elapsed_ms, len(result.model_dump_json()))


async def ask_all() -> None:
    settings = Settings()
    # One client, as in the gateway, so later calls reuse the open connection.
    async with httpx2.AsyncClient() as client:
        catalogue = SayTechCatalogue(client, settings.saytech_base_url, settings.saytech_timeout_seconds)
        await timed("context (first call, new connection)", catalogue.context())
        await timed("context (connection reused)", catalogue.context())
        await timed("scenario 1: Abu Dhabi under 400", catalogue.search(ABU_DHABI_UNDER_400))
        await timed("scenario 4: buggy by name", catalogue.search(BUGGY_BY_NAME))
        await timed("detail: buggy (on request)", catalogue.tour("tour", "DUNE- BUGGY"))
        await timed("detail: helicopter (slow before)", catalogue.tour("tour", "Helicopter - Flight"))
        search = await catalogue.search(ABU_DHABI_UNDER_400)
        for tour in search.tours:
            logger.info("  %s: %s (%s)", tour.name, tour.price, tour.city)
        buggy = await catalogue.search(BUGGY_BY_NAME)
        logger.info("  %s: %s", buggy.tours[0].name, buggy.tours[0].price)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(ask_all())


if __name__ == "__main__":
    main()
