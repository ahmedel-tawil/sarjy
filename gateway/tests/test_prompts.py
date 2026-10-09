import asyncio
from datetime import datetime
import logging
from typing import TYPE_CHECKING

from sarjy_gateway.catalogue import CatalogueUnavailableError
from sarjy_gateway.prompts import NO_CATALOGUE, SYSTEM_PROMPT, SystemPrompt, system_prompt

from gateway.tests.fakes import FakeCatalogue


if TYPE_CHECKING:
    import pytest


JUST_AFTER_MIDNIGHT = datetime.fromisoformat("2026-10-09T00:46+04:00")


def test_the_prompt_ends_with_the_date_and_time_in_the_uae() -> None:
    prompt = system_prompt(JUST_AFTER_MIDNIGHT, None, {})

    assert prompt.startswith(SYSTEM_PROMPT)
    assert prompt.endswith("Today is Friday 9 October 2026 (2026-10-09), and the time in the UAE is 00:46.\n")


def test_the_catalogue_gives_cities_kinds_of_tour_and_general_answers() -> None:
    context = asyncio.run(FakeCatalogue().context())

    prompt = system_prompt(JUST_AFTER_MIDNIGHT, context, {})

    assert "Cities: Abu Dhabi (7 tours), Dubai (8 tours)." in prompt
    assert "Categories you can search by: safari, theme parks." in prompt
    assert "- Can I cancel my booking? Up to 24 hours before." in prompt
    assert NO_CATALOGUE not in prompt


def test_the_builder_reads_the_catalogue_and_the_clock() -> None:
    builder = SystemPrompt(FakeCatalogue(), lambda: JUST_AFTER_MIDNIGHT)

    prompt = asyncio.run(builder.build({}))

    assert "From Magic Experience's catalogue:" in prompt
    assert "(2026-10-09)" in prompt


def test_without_saytech_the_turn_still_gets_a_prompt(caplog: pytest.LogCaptureFixture) -> None:
    catalogue = FakeCatalogue(error=CatalogueUnavailableError("SayTech answered HTTP 503"))
    builder = SystemPrompt(catalogue, lambda: JUST_AFTER_MIDNIGHT)

    with caplog.at_level(logging.WARNING, logger="sarjy_gateway.prompts"):
        prompt = asyncio.run(builder.build({}))

    assert NO_CATALOGUE in prompt
    assert caplog.messages == ["prompt built without the catalogue context: SayTech answered HTTP 503"]


def test_saved_facts_are_listed_with_their_keys() -> None:
    prompt = system_prompt(JUST_AFTER_MIDNIGHT, None, {"favourite_colour": "green", "avoids": "heights"})

    assert "What you know about this traveller from earlier (key: value):\n- avoids: heights\n- favourite_colour: green" in prompt


def test_a_new_traveller_is_known_to_be_new() -> None:
    assert "You know nothing about this traveller yet." in system_prompt(JUST_AFTER_MIDNIGHT, None, {})
