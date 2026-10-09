import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
import uuid

from sarjy_gateway.conversation_store import (
    PastVisit,
    PostgresConversationStore,
    SessionId,
    StoredTurn,
    StoredUser,
    TurnId,
)
from sarjy_gateway.database import database_pool
from sarjy_gateway.identity import new_user_id
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
    first_session: SessionId
    second_session: SessionId
    after_first: StoredUser | None
    after_second: StoredUser | None


def test_a_new_user_is_created_with_their_first_session(database_url: SecretStr) -> None:
    user_id = new_user_id()

    async def visit(store: PostgresConversationStore) -> StoredUser | None:
        await store.start_session(user_id)
        return await store.user(user_id)

    user = with_store(database_url, visit)

    assert user is not None
    assert user.id == user_id
    assert user.created_at == user.last_seen_at


def test_a_returning_user_keeps_their_id_and_gets_a_new_session(database_url: SecretStr) -> None:
    user_id = new_user_id()

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
        id=TurnId(uuid.uuid7()), transcript="How much is the buggy tour?", reply="It's on request.", tool_results=['{"a": 1}']
    )

    async def save_twice(store: PostgresConversationStore) -> list[StoredTurn]:
        session_id = await store.start_session(new_user_id())
        await store.save_turn(session_id, turn)
        # Saving the same turn again changes nothing (ON CONFLICT DO NOTHING).
        await store.save_turn(session_id, turn)
        return await store.turns(session_id)

    assert with_store(database_url, save_twice) == [turn]


def test_an_unknown_user_is_none(database_url: SecretStr) -> None:
    async def look_up(store: PostgresConversationStore) -> StoredUser | None:
        return await store.user(new_user_id())

    assert with_store(database_url, look_up) is None


@dataclass(frozen=True)
class StoredMarks:
    own: dict[str, float]
    someone_elses: dict[str, float]


def test_marks_are_kept_for_a_turn_of_the_same_session_only(database_url: SecretStr) -> None:
    async def body(store: PostgresConversationStore) -> StoredMarks:
        mine, theirs = await store.start_session(new_user_id()), await store.start_session(new_user_id())
        own_turn, their_turn = TurnId(uuid.uuid7()), TurnId(uuid.uuid7())
        await store.save_turn(mine, StoredTurn(own_turn, "Hi", "Hello", []))
        await store.save_turn(theirs, StoredTurn(their_turn, "Hi", "Hello", []))
        await store.save_marks(mine, own_turn, {"audio_received": 0.0, "tts_first_byte": 2400.5})
        await store.save_marks(mine, own_turn, {"speech_end": 1000.0, "playback_start": 4100.0})
        # Sent again with another value: the first one stays.
        await store.save_marks(mine, own_turn, {"playback_start": 9999.0})
        # A visit can't attach marks to another session's turn.
        await store.save_marks(mine, their_turn, {"speech_end": 1.0})
        return StoredMarks(own=await store.marks(own_turn), someone_elses=await store.marks(their_turn))

    marks = with_store(database_url, body)

    assert marks.own == {"audio_received": 0.0, "tts_first_byte": 2400.5, "speech_end": 1000.0, "playback_start": 4100.0}
    assert marks.someone_elses == {}


@dataclass(frozen=True)
class History:
    visits: list[PastVisit]
    own_reply: str | None
    someone_elses_reply: str | None


def test_earlier_visits_are_the_users_own_with_questions_newest_first(database_url: SecretStr) -> None:
    async def body(store: PostgresConversationStore) -> History:
        user, other = new_user_id(), new_user_id()
        first = await store.start_session(user)
        await store.save_turn(first, StoredTurn(TurnId(uuid.uuid7()), "Hi", "Hello", []))
        await store.start_session(user)  # a page load with no question
        second = await store.start_session(user)
        asked = TurnId(uuid.uuid7())
        await store.save_turn(second, StoredTurn(asked, "Safari tomorrow?", "It will be hot.", []))
        theirs = await store.start_session(other)
        their_turn = TurnId(uuid.uuid7())
        await store.save_turn(theirs, StoredTurn(their_turn, "Mine", "Not yours", []))
        current = await store.start_session(user)
        return History(
            visits=await store.earlier_visits(user, current, visits=3),
            own_reply=await store.reply_of(user, asked),
            someone_elses_reply=await store.reply_of(user, their_turn),
        )

    history = with_store(database_url, body)

    assert [[turn.transcript for turn in visit.turns] for visit in history.visits] == [["Safari tomorrow?"], ["Hi"]]
    assert (history.own_reply, history.someone_elses_reply) == ("It will be hot.", None)
