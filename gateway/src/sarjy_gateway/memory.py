from dataclasses import dataclass
import re
from typing import TYPE_CHECKING, Protocol

import psycopg
from psycopg.rows import class_row
from psycopg_pool import PoolTimeout
from pydantic import BaseModel, Field

from sarjy_gateway.database import DatabaseUnavailableError
from sarjy_gateway.llm import ToolSpec
from sarjy_gateway.tools import ToolError


if TYPE_CHECKING:
    from collections.abc import Mapping

    from sarjy_gateway.database import Pool
    from sarjy_gateway.identity import UserId
    from sarjy_gateway.turn import Conversation


UNAVAILABLE = "Memory isn't available right now, so nothing was saved."


@dataclass(frozen=True)
class Fact:
    key: str
    value: str


# What Sarjy remembers about each user (D-67). One fact per key: saving a key again
# replaces its value, which is how "actually, my favourite colour is blue" works.
class FactStore(Protocol):
    async def facts(self, user_id: UserId) -> list[Fact]: ...

    async def remember(self, user_id: UserId, fact: Fact) -> None: ...

    async def forget(self, user_id: UserId, key: str) -> bool: ...

    async def forget_all(self, user_id: UserId) -> None: ...


class PostgresFactStore(FactStore):
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def facts(self, user_id: UserId) -> list[Fact]:
        try:
            async with self._pool.connection() as connection:
                cursor = connection.cursor(row_factory=class_row(Fact))
                await cursor.execute("SELECT key, value FROM facts WHERE user_id = %s ORDER BY key", (user_id,))
                return await cursor.fetchall()
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error

    async def remember(self, user_id: UserId, fact: Fact) -> None:
        try:
            async with self._pool.connection() as connection, connection.transaction():
                await connection.execute(
                    "INSERT INTO facts (user_id, key, value) VALUES (%s, %s, %s) "
                    "ON CONFLICT (user_id, key) DO UPDATE SET value = excluded.value, updated_at = now()",
                    (user_id, fact.key, fact.value),
                )
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error

    # True when a fact was there to forget.
    async def forget(self, user_id: UserId, key: str) -> bool:
        try:
            async with self._pool.connection() as connection, connection.transaction():
                cursor = await connection.execute(
                    "DELETE FROM facts WHERE user_id = %s AND key = %s", (user_id, key)
                )
                return cursor.rowcount > 0
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error

    async def forget_all(self, user_id: UserId) -> None:
        try:
            async with self._pool.connection() as connection, connection.transaction():
                await connection.execute("DELETE FROM facts WHERE user_id = %s", (user_id,))
        except (psycopg.Error, PoolTimeout) as error:
            raise unavailable(error) from error


# Without SARJY_DATABASE_URL Sarjy remembers nothing between visits.
class MissingFactStore(FactStore):
    async def facts(self, user_id: UserId) -> list[Fact]:
        message = f"SARJY_DATABASE_URL is not set: no facts for user {user_id}"
        raise DatabaseUnavailableError(message)

    async def remember(self, user_id: UserId, fact: Fact) -> None:
        message = f"SARJY_DATABASE_URL is not set: {fact.key} not saved for user {user_id}"
        raise DatabaseUnavailableError(message)

    async def forget(self, user_id: UserId, key: str) -> bool:
        message = f"SARJY_DATABASE_URL is not set: {key} not forgotten for user {user_id}"
        raise DatabaseUnavailableError(message)

    async def forget_all(self, user_id: UserId) -> None:
        message = f"SARJY_DATABASE_URL is not set: facts not forgotten for user {user_id}"
        raise DatabaseUnavailableError(message)


# Hears every change to the visit's facts, so the page's memory panel can show it at once.
class MemoryListener(Protocol):
    async def memory(self, facts: Mapping[str, str]) -> None: ...


def unavailable(error: Exception) -> DatabaseUnavailableError:
    return DatabaseUnavailableError(f"database unreachable: {type(error).__name__}")


# "Favourite Colour" and "favourite-colour" are the same fact: lower case, words joined by
# underscores. The model also sees the keys it saved before, so it reuses them.
def normalise_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_")


class RememberFactArguments(BaseModel):
    key: str = Field(
        min_length=1,
        max_length=60,
        description="A short name for the fact, such as 'favourite_colour' or 'travelling_with'. "
        "Reuse a key you already know to change that fact.",
    )
    value: str = Field(
        min_length=1, max_length=200, description="The fact itself, such as 'green' or 'two children'."
    )


class ForgetFactArguments(BaseModel):
    key: str = Field(min_length=1, max_length=60, description="The key of a fact you know.")


class SavedFact(BaseModel):
    saved: str
    value: str


class ForgottenFact(BaseModel):
    forgotten: str


# Memory tools belong to one visit: they save for its user, and keep the conversation's
# copy of the facts current, so the next turn's prompt already knows (D-67) and the page's
# panel shows the change (D-68).
class RememberFactTool:
    spec = ToolSpec(
        "remember_fact",
        "Save a lasting fact or preference the traveller shared about themselves, so you know "
        "it on later visits too. Not for one-off requests.",
        RememberFactArguments.model_json_schema(),
    )

    def __init__(self, store: FactStore, conversation: Conversation, listener: MemoryListener) -> None:
        self._store = store
        self._conversation = conversation
        self._listener = listener

    async def run(self, arguments: str) -> str:
        request = RememberFactArguments.model_validate_json(arguments)
        fact = Fact(key=normalise_key(request.key), value=request.value.strip())
        if not fact.key:
            message = "The key needs at least one letter or digit."
            raise ToolError(message)
        try:
            await self._store.remember(self._conversation.user_id, fact)
        except DatabaseUnavailableError as error:
            raise ToolError(UNAVAILABLE) from error
        self._conversation.facts[fact.key] = fact.value
        await self._listener.memory(self._conversation.facts)
        return SavedFact(saved=fact.key, value=fact.value).model_dump_json()


class ForgetFactTool:
    spec = ToolSpec(
        "forget_fact",
        "Forget one fact you know about the traveller, when they ask you to.",
        ForgetFactArguments.model_json_schema(),
    )

    def __init__(self, store: FactStore, conversation: Conversation, listener: MemoryListener) -> None:
        self._store = store
        self._conversation = conversation
        self._listener = listener

    async def run(self, arguments: str) -> str:
        key = normalise_key(ForgetFactArguments.model_validate_json(arguments).key)
        try:
            forgotten = await self._store.forget(self._conversation.user_id, key)
        except DatabaseUnavailableError as error:
            raise ToolError(UNAVAILABLE) from error
        if self._conversation.facts.pop(key, None) is not None:
            await self._listener.memory(self._conversation.facts)
        if not forgotten:
            message = f"Nothing was saved under {key}."
            raise ToolError(message)
        return ForgottenFact(forgotten=key).model_dump_json()
