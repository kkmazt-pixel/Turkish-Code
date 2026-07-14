"""Tests for the forward-only migration runner (doc 29 §10/§14)."""

from __future__ import annotations

from pathlib import Path

import pytest
from turkish_code.depo.db import Database
from turkish_code.depo.migrate import (
    MIGRATION_FAILED_CODE,
    SCHEMA_DOWNGRADE_CODE,
    Migration,
    load_migrations,
    migrate,
)
from turkish_code.hata import AppError, ErrorKind
from turkish_code.yapilandirma.depolama import StorageConfig


async def _open(tmp_path: Path) -> Database:
    return await Database.open(tmp_path / "m.db", config=StorageConfig())


async def _version(db: Database) -> int:
    row = await db.fetchone("PRAGMA user_version")
    assert row is not None
    return int(row[0])


def test_load_shipped_app_migrations() -> None:
    migrations = load_migrations("app")
    assert migrations[0].version == 1
    assert migrations[0].name == "initial"
    assert any("meta" in s for s in migrations[0].statements)


def test_load_shipped_workspace_migrations() -> None:
    migrations = load_migrations("workspace")
    assert migrations[0].version == 1


@pytest.mark.asyncio
async def test_migrate_fresh_db_applies_baseline(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        migrations = load_migrations("app")
        target = migrations[-1].version
        final = await migrate(db, migrations)
        assert final == target
        assert await _version(db) == target
        # the baseline meta table exists and is usable
        async with db.transaction() as tx:
            await tx.execute("INSERT INTO meta (key, value) VALUES ('k', 'v')")
        row = await db.fetchone("SELECT value FROM meta WHERE key = 'k'")
        assert row is not None and row["value"] == "v"
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_migrate_is_idempotent(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        migrations = load_migrations("app")
        target = migrations[-1].version
        await migrate(db, migrations)
        again = await migrate(db, migrations)
        assert again == target
        assert await _version(db) == target
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_pending_migrations_apply_in_order(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        migrations = [
            Migration(1, "one", ("CREATE TABLE a (x INTEGER);",)),
            Migration(2, "two", ("CREATE TABLE b (y INTEGER);",)),
        ]
        assert await migrate(db, migrations) == 2
        assert await _version(db) == 2
        # both tables exist
        rows = await db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('a', 'b') ORDER BY name"
        )
        assert [r["name"] for r in rows] == ["a", "b"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_only_newer_migrations_run(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        await migrate(db, [Migration(1, "one", ("CREATE TABLE a (x INTEGER);",))])
        # Add a v2 while v1 already applied; v1 must NOT re-run (would error on
        # duplicate CREATE TABLE a) — only v2 applies.
        migrations = [
            Migration(1, "one", ("CREATE TABLE a (x INTEGER);",)),
            Migration(2, "two", ("CREATE TABLE b (y INTEGER);",)),
        ]
        assert await migrate(db, migrations) == 2
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_failed_migration_rolls_back_atomically(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        bad = [
            Migration(
                1,
                "bad",
                ("CREATE TABLE good (x INTEGER);", "THIS IS NOT VALID SQL;"),
            )
        ]
        with pytest.raises(AppError) as exc_info:
            await migrate(db, bad)
        assert exc_info.value.code == MIGRATION_FAILED_CODE
        # version untouched and the partial CREATE was rolled back
        assert await _version(db) == 0
        tables = await db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='good'"
        )
        assert tables == []
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_downgrade_is_refused(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        await db.executescript("PRAGMA user_version = 99")
        with pytest.raises(AppError) as exc_info:
            await migrate(db, load_migrations("app"))
        assert exc_info.value.code == SCHEMA_DOWNGRADE_CODE
        assert exc_info.value.kind is ErrorKind.CONFLICT
    finally:
        await db.aclose()


def test_duplicate_versions_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        # load_migrations validates; here we exercise the validator directly
        from turkish_code.depo.migrate import _validate

        _validate([Migration(1, "a", ()), Migration(1, "b", ())])
