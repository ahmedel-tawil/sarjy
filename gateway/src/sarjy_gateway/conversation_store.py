from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, NewType, Protocol
import uuid

import psycopg
from psycopg.rows import class_row
from psycopg_pool import PoolTimeout

from sarjy_gateway.database import DatabaseUnavailableError


if TYPE_CHECKING:
    from collections.abc import Mapping

    from sarjy_gateway.database import Pool
    from sarjy_gateway.identity import UserId


@dataclass(frozen=True)
class StoredUser:
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime


# A session's id, kept apart from user and turn ids by the type checker.
SessionId = NewType("SessionId", uuid.UUID)
# A turn's id: the pipeline's turn id, which turn_timings refers to (D-65).
TurnId = NewType("TurnId", uuid.UUID)


@dataclass(frozen=True)
class NewSession:
    id: uuid.UUID


@dataclass(frozen=True)
class StoredTurn:
    id: TurnId
    transcript: str
    reply: str
    tool_results: list[str]


@dataclass(frozen=True)
class StoredMark:
    mark: str
    at_ms: float


# One exchange of an earlier visit, as the history query returns it.
@dataclass(frozen=True)
class PastTurnRow:
    session_id: SessionId
    started_at: datetime
    id: TurnId
    transcript: str
    reply: str


@dataclass(frozen=True)
class PastTurn:
    id: TurnId
    transcript: str
    reply: str


# An earlier visit of the same user, with its exchanges in order (D-92).
@dataclass(frozen=True)
class PastVisit:
    started_at: datetime
    turns: list[PastTurn]


@dataclass(frozen=True)
class StoredReply:
    reply: str


# Who is talking and what was said (D-66): one row per user (browser), one per page visit,
# one per exchange, and each exchange's latency marks (M3.1).
class ConversationStore(Protocol):
    async def start_session(self, user_id: UserId) -> SessionId: ...

    async def save_turn(self, session_id: SessionId, turn: StoredTurn) -> None: ...

    async def user(self, user_id: UserId) -> StoredUser | None: ...

    async def turns(self, session_id: SessionId) -> list[StoredTurn]: ...

    async def save_marks(self, session_id: SessionId, turn_id: TurnId, marks: Mapping[str, float]) -> None: ...

    async def marks(self, turn_id: TurnId) -> dict[str, float]: ...

    async def earlier_visits(self, user_id: UserId, current: SessionId | None, *, visits: int) -> list[PastVisit]: ...

    async def reply_of(self, user_id: UserId, turn_id: TurnId) -> str | None: ...


class PostgresConversationStore(ConversationStore):
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    # A returning browser keeps its user and gets a fresh last_seen_at; every visit is a
    # new session.
    async def start_session(self, user_id: UserId) -> SessionId:
        try:
            async with self._pool.connection() as connection, connection.transaction():
                await connection.execute(
                    "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO UPDATE SET last_seen_at = now()",
                    (user_id,),
                )
                cursor = connection.cursor(row_factory=class_row(NewSession))
                await cursor.execute("INSERT INTO sessions (user_id) VALUES (%s) RETURNING id", (user_id,))
                session = await cursor.fetchone()
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error
        if session is None:
            message = "the new session's id was not returned"
            raise DatabaseUnavailableError(message)
        return SessionId(session.id)

    async def save_turn(self, session_id: SessionId, turn: StoredTurn) -> None:
        try:
            async with self._pool.connection() as connection, connection.transaction():
                await connection.execute(
                    "INSERT INTO turns (id, session_id, transcript, reply, tool_results) "
                    "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (turn.id, session_id, turn.transcript, turn.reply, turn.tool_results),
                )
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error

    async def user(self, user_id: UserId) -> StoredUser | None:
        try:
            async with self._pool.connection() as connection:
                cursor = connection.cursor(row_factory=class_row(StoredUser))
                await cursor.execute("SELECT id, created_at, last_seen_at FROM users WHERE id = %s", (user_id,))
                return await cursor.fetchone()
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error

    async def turns(self, session_id: SessionId) -> list[StoredTurn]:
        try:
            async with self._pool.connection() as connection:
                cursor = connection.cursor(row_factory=class_row(StoredTurn))
                await cursor.execute(
                    "SELECT id, transcript, reply, tool_results FROM turns WHERE session_id = %s ORDER BY id",
                    (session_id,),
                )
                return await cursor.fetchall()
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error

    # Stored only for a turn of this session, so a browser can't attach marks to someone
    # else's turn; a mark already stored is kept (D-74).
    async def save_marks(self, session_id: SessionId, turn_id: TurnId, marks: Mapping[str, float]) -> None:
        rows = [(mark, at_ms, turn_id, session_id) for mark, at_ms in marks.items()]
        try:
            async with self._pool.connection() as connection, connection.transaction(), connection.cursor() as cursor:
                await cursor.executemany(
                    "INSERT INTO turn_timings (turn_id, mark, at_ms) "
                    "SELECT id, %s::text, %s::double precision FROM turns WHERE id = %s AND session_id = %s "
                    "ON CONFLICT (turn_id, mark) DO NOTHING",
                    rows,
                )
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error

    async def marks(self, turn_id: TurnId) -> dict[str, float]:
        try:
            async with self._pool.connection() as connection:
                cursor = connection.cursor(row_factory=class_row(StoredMark))
                await cursor.execute("SELECT mark, at_ms FROM turn_timings WHERE turn_id = %s", (turn_id,))
                return {row.mark: row.at_ms for row in await cursor.fetchall()}
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error

    # The user's last few visits that had a question, newest first, never the current one.
    # Every page load is a visit, so visits without turns are skipped.
    async def earlier_visits(self, user_id: UserId, current: SessionId | None, *, visits: int) -> list[PastVisit]:
        try:
            async with self._pool.connection() as connection:
                cursor = connection.cursor(row_factory=class_row(PastTurnRow))
                await cursor.execute(
                    "SELECT s.id AS session_id, s.started_at, t.id, t.transcript, t.reply "
                    "FROM sessions s JOIN turns t ON t.session_id = s.id "
                    "WHERE s.id IN ("
                    "SELECT recent.id FROM sessions recent WHERE recent.user_id = %s "
                    "AND recent.id IS DISTINCT FROM %s "
                    "AND EXISTS (SELECT 1 FROM turns asked WHERE asked.session_id = recent.id) "
                    "ORDER BY recent.started_at DESC, recent.id DESC LIMIT %s) "
                    "ORDER BY s.started_at DESC, t.id",
                    (user_id, current, visits),
                )
                rows = await cursor.fetchall()
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error
        return group_visits(rows)

    # Only a turn of this user's own visits has a reply to give.
    async def reply_of(self, user_id: UserId, turn_id: TurnId) -> str | None:
        try:
            async with self._pool.connection() as connection:
                cursor = connection.cursor(row_factory=class_row(StoredReply))
                await cursor.execute(
                    "SELECT t.reply FROM turns t JOIN sessions s ON s.id = t.session_id "
                    "WHERE t.id = %s AND s.user_id = %s",
                    (turn_id, user_id),
                )
                found = await cursor.fetchone()
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error
        return None if found is None else found.reply


# Without SARJY_DATABASE_URL nothing is stored; the voice loop carries on without it.
class MissingConversationStore(ConversationStore):
    async def start_session(self, user_id: UserId) -> SessionId:
        message = f"SARJY_DATABASE_URL is not set: no session stored for user {user_id}"
        raise DatabaseUnavailableError(message)

    async def save_turn(self, session_id: SessionId, turn: StoredTurn) -> None:
        message = f"SARJY_DATABASE_URL is not set: turn {turn.id} of session {session_id} not stored"
        raise DatabaseUnavailableError(message)

    async def user(self, user_id: UserId) -> StoredUser | None:
        message = f"SARJY_DATABASE_URL is not set: user {user_id} can't be read"
        raise DatabaseUnavailableError(message)

    async def turns(self, session_id: SessionId) -> list[StoredTurn]:
        message = f"SARJY_DATABASE_URL is not set: session {session_id} can't be read"
        raise DatabaseUnavailableError(message)

    async def save_marks(self, session_id: SessionId, turn_id: TurnId, marks: Mapping[str, float]) -> None:
        message = f"SARJY_DATABASE_URL is not set: {len(marks)} marks of turn {turn_id} in session {session_id} not stored"
        raise DatabaseUnavailableError(message)

    async def marks(self, turn_id: TurnId) -> dict[str, float]:
        message = f"SARJY_DATABASE_URL is not set: marks of turn {turn_id} can't be read"
        raise DatabaseUnavailableError(message)

    async def earlier_visits(self, user_id: UserId, current: SessionId | None, *, visits: int) -> list[PastVisit]:
        message = f"SARJY_DATABASE_URL is not set: no {visits} earlier visits of user {user_id} before {current}"
        raise DatabaseUnavailableError(message)

    async def reply_of(self, user_id: UserId, turn_id: TurnId) -> str | None:
        message = f"SARJY_DATABASE_URL is not set: turn {turn_id} of user {user_id} can't be read"
        raise DatabaseUnavailableError(message)


def unavailable(error: Exception) -> DatabaseUnavailableError:
    return DatabaseUnavailableError(f"database unreachable: {type(error).__name__}")


# How many of a visit's exchanges the page is sent: its last ten.
TURNS_PER_VISIT = 10


# Rows come newest visit first, each visit's turns in order; the page gets each visit's
# last few exchanges.
def group_visits(rows: list[PastTurnRow]) -> list[PastVisit]:
    grouped: dict[SessionId, PastVisit] = {}
    for row in rows:
        visit = grouped.setdefault(row.session_id, PastVisit(started_at=row.started_at, turns=[]))
        visit.turns.append(PastTurn(id=row.id, transcript=row.transcript, reply=row.reply))
    return [PastVisit(started_at=visit.started_at, turns=visit.turns[-TURNS_PER_VISIT:]) for visit in grouped.values()]
