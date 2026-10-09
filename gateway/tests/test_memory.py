import asyncio
from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

import pytest
from sarjy_gateway.conversation_store import PostgresConversationStore
from sarjy_gateway.database import DatabaseUnavailableError, database_pool
from sarjy_gateway.identity import new_user_id
from sarjy_gateway.llm import TextDelta, ToolCallDelta
from sarjy_gateway.memory import (
    UNAVAILABLE,
    Fact,
    ForgetFactTool,
    PostgresFactStore,
    RememberFactTool,
    normalise_key,
)
from sarjy_gateway.migrate import MIGRATIONS_FOLDER, MigrationRunner
from sarjy_gateway.tools import TOOL_TIMEOUT_SECONDS, Toolbox, ToolError
from sarjy_gateway.turn import Conversation, TurnPipeline

from gateway.tests.fakes import (
    FakeChatModel,
    FakeFactStore,
    FakePrompt,
    FakeSpeechToText,
    FakeTextToSpeech,
    RecordingListener,
    RecordingMemoryListener,
    TickingClock,
)


if TYPE_CHECKING:
    from pydantic import SecretStr
    from sarjy_gateway.identity import UserId


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("Favourite Colour", "favourite_colour"),
        ("favourite-colour", "favourite_colour"),
        ("  Travelling With!! ", "travelling_with"),
        ("avoids", "avoids"),
    ],
)
def test_keys_are_normalised_so_the_same_fact_keeps_one_key(key: str, expected: str) -> None:
    assert normalise_key(key) == expected


def test_remembering_saves_under_the_normalised_key_and_updates_the_visit_and_page() -> None:
    store = FakeFactStore()
    conversation = Conversation(max_turns=6)
    page = RecordingMemoryListener()

    result = asyncio.run(
        RememberFactTool(store, conversation, page).run('{"key": "Favourite Colour", "value": " green "}')
    )

    assert result == '{"saved":"favourite_colour","value":"green"}'
    assert store.saved == {conversation.user_id: {"favourite_colour": "green"}}
    assert conversation.facts == {"favourite_colour": "green"}
    assert page.pushes == [{"favourite_colour": "green"}]


def test_saying_it_again_replaces_the_value() -> None:
    store = FakeFactStore()
    conversation = Conversation(max_turns=6)
    remember = RememberFactTool(store, conversation, RecordingMemoryListener())

    asyncio.run(remember.run('{"key": "favourite_colour", "value": "green"}'))
    asyncio.run(remember.run('{"key": "favourite colour", "value": "blue"}'))

    assert store.saved[conversation.user_id] == {"favourite_colour": "blue"}


def test_forgetting_removes_the_fact_and_an_unknown_one_is_explained() -> None:
    conversation = Conversation(max_turns=6, facts={"favourite_colour": "green"})
    store = FakeFactStore({conversation.user_id: {"favourite_colour": "green"}})
    page = RecordingMemoryListener()
    forget = ForgetFactTool(store, conversation, page)

    result = asyncio.run(forget.run('{"key": "Favourite Colour"}'))
    with pytest.raises(ToolError, match=re.escape("Nothing was saved under favourite_colour.")):
        asyncio.run(forget.run('{"key": "favourite_colour"}'))

    assert result == '{"forgotten":"favourite_colour"}'
    assert (store.saved[conversation.user_id], conversation.facts) == ({}, {})
    # The second attempt changed nothing, so the page heard only the first.
    assert page.pushes == [{}]


@pytest.mark.parametrize(
    "tool", [RememberFactTool, ForgetFactTool], ids=["remember while down", "forget while down"]
)
def test_without_the_database_the_model_hears_that_memory_is_unavailable(
    tool: type[RememberFactTool | ForgetFactTool],
) -> None:
    store = FakeFactStore(error=DatabaseUnavailableError("database unreachable: PoolTimeout"))
    conversation = Conversation(max_turns=6)
    page = RecordingMemoryListener()

    with pytest.raises(ToolError, match=re.escape(UNAVAILABLE)):
        asyncio.run(tool(store, conversation, page).run('{"key": "favourite_colour", "value": "green"}'))

    assert (conversation.facts, page.pushes) == ({}, [])


def test_a_key_without_letters_or_digits_is_refused() -> None:
    with pytest.raises(ToolError):
        asyncio.run(
            RememberFactTool(FakeFactStore(), Conversation(max_turns=6), RecordingMemoryListener()).run(
                '{"key": "!!!", "value": "x"}'
            )
        )


def test_a_fact_saved_in_one_turn_is_in_the_next_turns_prompt() -> None:
    save = ToolCallDelta(0, "call-1", "remember_fact", '{"key": "favourite_colour", "value": "green"}')
    llm = FakeChatModel(rounds=[[save], [TextDelta("Noted, green.")], [TextDelta("Green!")]])
    prompt = FakePrompt()
    conversation = Conversation(max_turns=6)
    conversation.tools = [RememberFactTool(FakeFactStore(), conversation, RecordingMemoryListener())]
    pipeline = TurnPipeline(
        FakeSpeechToText(),
        llm,
        FakeTextToSpeech(),
        Toolbox([], TickingClock(), TOOL_TIMEOUT_SECONDS),
        system_prompt=prompt.build,
        clock=TickingClock(),
        sentence_streaming=False,
    )

    for _ in range(2):
        asyncio.run(pipeline.run(b"clip", conversation, RecordingListener()))

    assert prompt.facts_seen == [{}, {"favourite_colour": "green"}]
    assert llm.offered_tools[0] == ["remember_fact"]


@dataclass(frozen=True)
class Memories:
    after_saving_twice: list[Fact]
    forgotten: bool
    after_forgetting: list[Fact]
    forgotten_again: bool
    someone_else: list[Fact]


def test_postgres_keeps_one_fact_per_key_and_forgets_it(database_url: SecretStr) -> None:
    async def run() -> Memories:
        pool = database_pool(database_url, max_size=2, wait_seconds=5.0)
        await pool.open(wait=True)
        try:
            await MigrationRunner(pool, MIGRATIONS_FOLDER).apply_pending()
            visits, facts = PostgresConversationStore(pool), PostgresFactStore(pool)
            user, other = new_user_id(), new_user_id()
            await visits.start_session(user)
            await visits.start_session(other)
            await facts.remember(user, Fact("favourite_colour", "green"))
            await facts.remember(user, Fact("favourite_colour", "blue"))
            await facts.remember(other, Fact("favourite_colour", "red"))
            after_saving_twice = await facts.facts(user)
            forgotten = await facts.forget(user, "favourite_colour")
            return Memories(
                after_saving_twice=after_saving_twice,
                forgotten=forgotten,
                after_forgetting=await facts.facts(user),
                forgotten_again=await facts.forget(user, "favourite_colour"),
                someone_else=await facts.facts(other),
            )
        finally:
            await pool.close()

    memories = asyncio.run(run())

    assert memories.after_saving_twice == [Fact("favourite_colour", "blue")]
    assert (memories.forgotten, memories.after_forgetting, memories.forgotten_again) == (True, [], False)
    assert memories.someone_else == [Fact("favourite_colour", "red")]


@dataclass(frozen=True)
class AfterForgetMe:
    mine: list[Fact]
    theirs: list[Fact]


def test_postgres_forget_me_deletes_only_that_users_facts(database_url: SecretStr) -> None:
    async def run() -> AfterForgetMe:
        pool = database_pool(database_url, max_size=2, wait_seconds=5.0)
        await pool.open(wait=True)
        try:
            await MigrationRunner(pool, MIGRATIONS_FOLDER).apply_pending()
            visits, facts = PostgresConversationStore(pool), PostgresFactStore(pool)
            user, other = new_user_id(), new_user_id()
            owners: list[UserId] = [user, other]
            for owner in owners:
                await visits.start_session(owner)
                await facts.remember(owner, Fact("favourite_colour", "green"))
                await facts.remember(owner, Fact("travelling_with", "two children"))
            await facts.forget_all(user)
            return AfterForgetMe(mine=await facts.facts(user), theirs=await facts.facts(other))
        finally:
            await pool.close()

    after = asyncio.run(run())

    assert after.mine == []
    assert [fact.key for fact in after.theirs] == ["favourite_colour", "travelling_with"]
