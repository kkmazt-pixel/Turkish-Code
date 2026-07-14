"""Forward-only, atomic, startup schema migrations (doc 29 §10).

Each DB carries its schema version in ``PRAGMA user_version``. On open, pending
migrations (version > current) are applied **in order, each in one transaction**
so a failure rolls back cleanly and blocks startup rather than leaving a
half-migrated DB (doc 29 §10, fail-safe). Opening a DB newer than the app knows
about is refused — migrations are forward-only (doc 29 §14/§24).

Migrations are ``NNNN_name.sql`` files under ``schema/<kind>/`` (the source of
truth, doc 29 §9). Statements are split SQLite-aware (:func:`sqlite3.
complete_statement`) so each runs individually inside the transaction — SQLite's
``executescript`` can't be used here because it force-commits (no atomicity).
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from importlib.resources import files

from turkish_code.depo.db import Database
from turkish_code.hata import AppError, ErrorKind

SCHEMA_DOWNGRADE_CODE = "storage.schema_downgrade"
MIGRATION_FAILED_CODE = "storage.migration_failed"

_FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


@dataclass(frozen=True, slots=True)
class Migration:
    """One forward-only schema step (doc 29 §10)."""

    version: int
    name: str
    statements: tuple[str, ...]


def load_migrations(kind: str) -> list[Migration]:
    """Load and validate the ``NNNN_name.sql`` migrations for a DB kind.

    ``kind`` is ``"app"`` or ``"workspace"`` (doc 29 §5). Files are read from
    ``schema/<kind>/``; non-matching names are ignored.
    """
    root = files("turkish_code.depo.schema").joinpath(kind)
    migrations: list[Migration] = []
    for entry in root.iterdir():
        match = _FILENAME.match(entry.name)
        if match is None:
            continue
        script = entry.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=int(match.group(1)),
                name=match.group(2),
                statements=tuple(_split_statements(script)),
            )
        )
    migrations.sort(key=lambda m: m.version)
    _validate(migrations)
    return migrations


async def migrate(db: Database, migrations: list[Migration]) -> int:
    """Bring ``db`` up to the latest migration; return the resulting version."""
    current = await _current_version(db)
    if not migrations:
        return current

    target = migrations[-1].version
    if current > target:
        raise AppError(
            kind=ErrorKind.CONFLICT,
            code=SCHEMA_DOWNGRADE_CODE,
            message_key=f"hata.{SCHEMA_DOWNGRADE_CODE}",
            retryable=False,
            context={"db_version": current, "app_supports": target},
        )

    for migration in migrations:
        if migration.version > current:
            await _apply(db, migration)
    return target


async def _apply(db: Database, migration: Migration) -> None:
    try:
        async with db.transaction() as tx:
            for statement in migration.statements:
                await tx.execute(statement)
            await tx.execute(f"PRAGMA user_version = {migration.version}")
    except AppError as exc:
        raise AppError(
            kind=ErrorKind.INTERNAL,
            code=MIGRATION_FAILED_CODE,
            message_key=f"hata.{MIGRATION_FAILED_CODE}",
            retryable=False,
            context={"version": migration.version, "name": migration.name},
            cause=exc,
        ) from exc


async def _current_version(db: Database) -> int:
    row = await db.fetchone("PRAGMA user_version")
    return int(row[0]) if row is not None else 0


def _split_statements(script: str) -> list[str]:
    """Split a SQL script into complete statements (SQLite-aware)."""
    statements: list[str] = []
    buffer = ""
    for line in script.splitlines(keepends=True):
        buffer += line
        if sqlite3.complete_statement(buffer):
            statement = buffer.strip()
            if statement:
                statements.append(statement)
            buffer = ""
    tail = buffer.strip()
    if tail:
        statements.append(tail)
    return statements


def _validate(migrations: list[Migration]) -> None:
    seen: set[int] = set()
    for migration in migrations:
        if migration.version < 1:
            raise ValueError(f"migration version must be >= 1: {migration.name}")
        if migration.version in seen:
            raise ValueError(f"duplicate migration version: {migration.version}")
        seen.add(migration.version)
