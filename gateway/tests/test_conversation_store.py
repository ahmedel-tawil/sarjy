import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from sarjy_gateway.conversation_store import PostgresConversationStore, StoredTurn, StoredUser
from sarjy_gateway.database import database_pool
from sarjy_gateway.migrate import MIGRATIONS_FOLDER, MigrationRunner


if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from pydantic import SecretStr


# Each test gets the schema and a store on its own pool, inside one event loop.
def with_store[Result](url: SecretStr, body: Callable[[PostgresConversationStore], Awaitable[Result]]) -> Result:
    async def run() -> Result:
        pool = database_pool(url, max_size=2, wait_seconds=5.0)
        await pool.open(wait=True)
        try:
            await MigrationRunner(pool, MIGRATIONS_FOLDER).apply_pending()
            return await body(PostgresConversationStore(pool))
        finally:
            await pool.close()

    return asyncio.run(run())


@dataclass(frozen=True)
class TwoVisits:
    first_session: uuid.UUID
    second_session: uuid.UUID
    after_first: StoredUser | None
    after_second: StoredUser | None


def test_a_new_user_is_created_with_their_first_session(database_url: SecretStr) -> None:
    user_id = uuid.uuid7()

    async def visit(store: PostgresConversationStore) -> StoredUser | None:
        await store.start_session(user_id)
        return await store.user(user_id)

    user = with_store(database_url, visit)

    assert user is not None
    assert user.id == user_id
    assert user.created_at == user.last_seen_at


def test_a_returning_user_keeps_their_id_and_gets_a_new_session(database_url: SecretStr) -> None:
    user_id = uuid.uuid7()

    async def visit_twice(store: PostgresConversationStore) -> TwoVisits:
        first = await store.start_session(user_id)
        after_first = await store.user(user_id)
        second = await store.start_session(user_id)
        return TwoVisits(first, second, after_first, await store.user(user_id))

    visits = with_store(database_url, visit_twice)

    assert visits.first_session != visits.second_session
    assert visits.after_first is not None
    assert visits.after_second is not None
    assert visits.after_second.created_at == visits.after_first.created_at
    assert visits.after_second.last_seen_at > visits.after_first.last_seen_at


def test_a_saved_turn_comes_back_with_its_session(database_url: SecretStr) -> None:
    turn = StoredTurn(
        id=uuid.uuid7(), transcript="How much is the buggy tour?", reply="It's on request.", tool_results=['{"a": 1}']
    )

    async def save_twice(store: PostgresConversationStore) -> list[StoredTurn]:
        session_id = await store.start_session(uuid.uuid7())
        await store.save_turn(session_id, turn)
        # Saving the same turn again changes nothing (ON CONFLICT DO NOTHING).
        await store.save_turn(session_id, turn)
        return await store.turns(session_id)

    assert with_store(database_url, save_twice) == [turn]


def test_an_unknown_user_is_none(database_url: SecretStr) -> None:
    async def look_up(store: PostgresConversationStore) -> StoredUser | None:
        return await store.user(uuid.uuid7())

    assert with_store(database_url, look_up) is None
