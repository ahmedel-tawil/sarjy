import asyncio
from dataclasses import dataclass
import shutil
from typing import TYPE_CHECKING

from pydantic import SecretStr
import pytest
from sarjy_gateway.database import database_pool
from sarjy_gateway.migrate import MIGRATIONS_FOLDER, MigrationError, MigrationRunner


if TYPE_CHECKING:
    from pathlib import Path

    from sarjy_gateway.database import Pool


SHIPPED = sorted(file.name for file in MIGRATIONS_FOLDER.glob("*.sql"))


async def open_pool(url: SecretStr) -> Pool:
    pool = database_pool(url, max_size=2, wait_seconds=5.0)
    await pool.open(wait=True)
    return pool


@dataclass(frozen=True)
class TwoRuns:
    first: list[str]
    second: list[str]
    recorded: list[str]


async def run_twice(url: SecretStr) -> TwoRuns:
    pool = await open_pool(url)
    try:
        runner = MigrationRunner(pool, MIGRATIONS_FOLDER)
        first = await runner.apply_pending()
        second = await runner.apply_pending()
        return TwoRuns(first, second, await runner.applied())
    finally:
        await pool.close()


@dataclass(frozen=True)
class FailedRun:
    error: MigrationError | None
    before: list[str]
    after: list[str]


# Brings the database up to date with the shipped files, then runs a folder that adds a
# broken one.
async def run_broken(url: SecretStr, folder: Path) -> FailedRun:
    pool = await open_pool(url)
    try:
        await MigrationRunner(pool, MIGRATIONS_FOLDER).apply_pending()
        runner = MigrationRunner(pool, folder)
        before = await runner.applied()
        error = None
        try:
            await runner.apply_pending()
        except MigrationError as raised:
            error = raised
        return FailedRun(error, before, await runner.applied())
    finally:
        await pool.close()


def test_the_shipped_migrations_are_numbered_sql_files() -> None:
    assert SHIPPED
    assert all(name[:3].isdigit() and name[3] == "_" for name in SHIPPED)


def test_migrations_apply_once_and_record_every_file(database_url: SecretStr) -> None:
    runs = asyncio.run(run_twice(database_url))

    # The first run applies whatever an earlier test run hasn't; the second finds nothing.
    assert set(runs.first) <= set(SHIPPED)
    assert runs.second == []
    assert [name for name in runs.recorded if name in SHIPPED] == SHIPPED


def test_a_failing_migration_leaves_the_record_as_it_was(database_url: SecretStr, tmp_path: Path) -> None:
    for name in SHIPPED:
        shutil.copy(MIGRATIONS_FOLDER / name, tmp_path / name)
    (tmp_path / "999_broken.sql").write_text("CREATE TABLE broken (")

    run = asyncio.run(run_broken(database_url, tmp_path))

    assert run.error is not None
    assert run.after == run.before
    assert "999_broken.sql" not in run.after


def test_an_unreachable_database_is_a_migration_error() -> None:
    async def unreachable() -> None:
        pool = database_pool(SecretStr("postgresql://nobody@127.0.0.1:1/none"), max_size=1, wait_seconds=0.2)
        await pool.open()
        try:
            await MigrationRunner(pool, MIGRATIONS_FOLDER).apply_pending()
        finally:
            await pool.close()

    with pytest.raises(MigrationError):
        asyncio.run(unreachable())
