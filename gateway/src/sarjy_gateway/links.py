from operator import itemgetter
import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, ValidationError

from sarjy_gateway.messages import TourLink


if TYPE_CHECKING:
    from collections.abc import Sequence


# Words that don't tell one tour from another, so they never count as naming one.
STOP_WORDS = frozenset(
    {
        "a",
        "abu",
        "an",
        "and",
        "at",
        "by",
        "dhabi",
        "dubai",
        "entry",
        "for",
        "from",
        "in",
        "of",
        "on",
        "the",
        "ticket",
        "tickets",
        "to",
        "tour",
        "tours",
        "uae",
        "with",
    }
)


class LinkedTour(BaseModel):
    name: str
    link: str | None = None


# What a tool returned, read only for tours: search_tours lists them under `tours`,
# get_tour is one. Anything else, such as the weather or an error, has neither.
class ToolTours(BaseModel):
    tours: list[LinkedTour] = []
    name: str | None = None
    link: str | None = None


# The pages of the tours a reply names, in the order it names them (D-90). Sarjy never
# says a web address, so the links travel beside the reply; only tours its tools returned
# this turn can be linked, so a link is never invented.
def tour_links(reply: str, tool_results: Sequence[str]) -> list[TourLink]:
    spoken = reply.lower()
    spoken_words = set(words_of(spoken))
    found: dict[str, tuple[int, TourLink]] = {}
    for tour in tours_in(tool_results):
        if tour.link is None or tour.link in found:
            continue
        distinctive = set(words_of(tour.name)) - STOP_WORDS
        named = distinctive & spoken_words
        if distinctive and len(named) >= min(2, len(distinctive)):
            first = min(spoken.find(word) for word in named)
            found[tour.link] = (first, TourLink(name=tour.name, url=tour.link))
    return [link for _, link in sorted(found.values(), key=itemgetter(0))]


def tours_in(tool_results: Sequence[str]) -> list[LinkedTour]:
    tours: list[LinkedTour] = []
    for result in tool_results:
        try:
            found = ToolTours.model_validate_json(result)
        except ValidationError:
            continue
        tours += found.tours
        if found.name is not None:
            tours.append(LinkedTour(name=found.name, link=found.link))
    return tours


def words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())
