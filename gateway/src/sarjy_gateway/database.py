from typing import TYPE_CHECKING, Protocol

import psycopg
from psycopg_pool import AsyncConnectionPool, PoolTimeout


if TYPE_CHECKING:
    from psycopg import AsyncConnection
    from psycopg.rows import TupleRow
    from pydantic import SecretStr


type Pool = AsyncConnectionPool[AsyncConnection[TupleRow]]

# How long a query waits for a free connection before the database counts as unavailable.
CONNECTION_WAIT_SECONDS = 5.0


class DatabaseUnavailableError(Exception):
    pass


class Database(Protocol):
    async def ping(self) -> None: ...


class PostgresDatabase:
    def __init__(self, pool: Pool) -> None:
        self._pool = pool

    async def ping(self) -> None:
        try:
            async with self._pool.connection() as connection:
                await connection.execute("SELECT 1")
        except (psycopg.Error, PoolTimeout) as error:
            message = f"database unreachable: {type(error).__name__}"
            raise DatabaseUnavailableError(message) from error


# Without SARJY_DATABASE_URL the gateway still starts, for example for frontend work;
# anything needing the database says why it can't have it.
class MissingDatabase:
    async def ping(self) -> None:
        message = "SARJY_DATABASE_URL is not set"
        raise DatabaseUnavailableError(message)


# A few connections kept open, so a turn doesn't wait for a new one. The app opens the pool
# at startup without waiting for it: if the database is down, voice still works and
# /ready says so.
def database_pool(url: SecretStr, max_size: int) -> Pool:
    return AsyncConnectionPool(
        url.get_secret_value(), min_size=1, max_size=max_size, timeout=CONNECTION_WAIT_SECONDS, open=False
    )
