from dataclasses import dataclass
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import psycopg
from psycopg.rows import class_row
from psycopg_pool import PoolTimeout


if TYPE_CHECKING:
    from sarjy_gateway.database import Pool


logger = logging.getLogger(__name__)

# Shipped inside the package, so the Docker image carries the schema with the code.
MIGRATIONS_FOLDER = Path(__file__).parent / "migrations"

# Any fixed number, shared by every runner: Postgres lets one holder at a time take it.
MIGRATION_LOCK = 4_170_220_510


class MigrationError(Exception):
    pass


@dataclass(frozen=True)
class AppliedMigration:
    name: str


class Migrations(Protocol):
    async def apply_pending(self) -> list[str]: ...

    async def applied(self) -> list[str]: ...


# Applies numbered SQL files in name order, each once, recorded in schema_migrations
# (D-65). Every pending file runs in one transaction, so a failing file leaves the schema
# as it was, and an advisory lock makes two instances starting together take turns.
class MigrationRunner(Migrations):
    def __init__(self, pool: Pool, folder: Path) -> None:
        self._pool = pool
        self._folder = folder

    async def apply_pending(self) -> list[str]:
        try:
            applied = await self._apply_pending()
        except (psycopg.Error, PoolTimeout) as error:
            message = f"migrations not applied: {type(error).__name__}: {error}"
            raise MigrationError(message) from error
        for name in applied:
            logger.info("migration %(name)s applied", {"name": name})
        return applied

    async def applied(self) -> list[str]:
        try:
            async with self._pool.connection() as connection:
                cursor = connection.cursor(row_factory=class_row(AppliedMigration))
                await cursor.execute("SELECT name FROM schema_migrations ORDER BY name")
                return [row.name for row in await cursor.fetchall()]
        except (psycopg.Error, PoolTimeout) as error:
            message = f"migrations unreadable: {type(error).__name__}"
            raise MigrationError(message) from error

    async def _apply_pending(self) -> list[str]:
        files = sorted(self._folder.glob("*.sql"))
        applied: list[str] = []
        async with self._pool.connection() as connection:
            # The record of applied files is created on its own, so a failing migration
            # below can't take it with it when it rolls back.
            async with connection.transaction():
                await connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations "
                    "(name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
                )
            async with connection.transaction():
                await connection.execute("SELECT pg_advisory_xact_lock(%s)", (MIGRATION_LOCK,))
                cursor = connection.cursor(row_factory=class_row(AppliedMigration))
                await cursor.execute("SELECT name FROM schema_migrations")
                done = {row.name for row in await cursor.fetchall()}
                for file in files:
                    if file.name in done:
                        continue
                    # Bytes, not text: a file's statements run as written, with no parameters.
                    await connection.execute(file.read_bytes())
                    await connection.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (file.name,))
                    applied.append(file.name)
        return applied
