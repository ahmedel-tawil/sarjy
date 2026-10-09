from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, NewType, Protocol
import uuid

import psycopg
from psycopg.rows import class_row
from psycopg_pool import PoolTimeout

from sarjy_gateway.database import DatabaseUnavailableError


if TYPE_CHECKING:
    from sarjy_gateway.database import Pool
    from sarjy_gateway.identity import UserId


@dataclass(frozen=True)
class StoredUser:
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime


# A session's id, kept apart from user and turn ids by the type checker.
SessionId = NewType("SessionId", uuid.UUID)


@dataclass(frozen=True)
class NewSession:
    id: uuid.UUID


@dataclass(frozen=True)
class StoredTurn:
    id: uuid.UUID
    transcript: str
    reply: str
    tool_results: list[str]


# Who is talking and what was said (D-66): one row per user (browser), one per page visit,
# one per exchange.
class ConversationStore(Protocol):
    async def start_session(self, user_id: UserId) -> SessionId: ...

    async def save_turn(self, session_id: SessionId, turn: StoredTurn) -> None: ...

    async def user(self, user_id: UserId) -> StoredUser | None: ...

    async def turns(self, session_id: SessionId) -> list[StoredTurn]: ...


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


def unavailable(error: Exception) -> DatabaseUnavailableError:
    return DatabaseUnavailableError(f"database unreachable: {type(error).__name__}")
