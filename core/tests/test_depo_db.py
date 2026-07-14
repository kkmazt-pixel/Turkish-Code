"""Tests for the Database/Connection/Transaction core (doc 29 §8/§14, ADR-A/D).

Real temp SQLite files (never mocks) so these exercise genuine WAL, transaction,
and single-writer behavior — a mock can't prove crash-safety semantics.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from turkish_code.depo.db import Database
from turkish_code.hata import AppError, ErrorKind
from turkish_code.yapilandirma.depolama import StorageConfig


async def _open(tmp_path: Path, name: str = "t.db") -> Database:
    db = await Database.open(tmp_path / name, config=StorageConfig())
    await db.executescript("CREATE TABLE kv (k TEXT PRIMARY KEY, v INTEGER)")
    return db


@pytest.mark.asyncio
async def test_open_enables_wal_mode(tmp_path: Path) -> None:
    db = await Database.open(tmp_path / "w.db", config=StorageConfig())
    try:
        row = await db.fetchone("PRAGMA journal_mode")
        assert row is not None and row[0] == "wal"
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_open_creates_missing_parent_dirs(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b" / "c.db"
    db = await Database.open(nested, config=StorageConfig())
    try:
        assert nested.exists()
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_committed_transaction_persists(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        async with db.transaction() as tx:
            await tx.execute("INSERT INTO kv (k, v) VALUES ('a', 1)")
        row = await db.fetchone("SELECT v FROM kv WHERE k = 'a'")
        assert row is not None and row["v"] == 1
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_transaction_rolls_back_on_exception(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        with pytest.raises(RuntimeError, match="boom"):
            async with db.transaction() as tx:
                await tx.execute("INSERT INTO kv (k, v) VALUES ('a', 1)")
                raise RuntimeError("boom")
        assert await db.fetchall("SELECT * FROM kv") == []
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_reads_your_writes_within_a_transaction(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        async with db.transaction() as tx:
            await tx.execute("INSERT INTO kv (k, v) VALUES ('a', 5)")
            row = await tx.fetchone("SELECT v FROM kv WHERE k = 'a'")
            assert row is not None and row["v"] == 5
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_executemany_inserts_all_rows(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        async with db.transaction() as tx:
            await tx.executemany(
                "INSERT INTO kv (k, v) VALUES (?, ?)",
                [("a", 1), ("b", 2), ("c", 3)],
            )
        rows = await db.fetchall("SELECT count(*) AS n FROM kv")
        assert rows[0]["n"] == 3
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_concurrent_transactions_are_serialized(tmp_path: Path) -> None:
    # Single-writer discipline (doc 29 §14): two concurrent read-modify-writes
    # must not interleave into a lost update.
    db = await _open(tmp_path)
    try:
        async with db.transaction() as tx:
            await tx.execute("INSERT INTO kv (k, v) VALUES ('n', 0)")

        async def increment() -> None:
            async with db.transaction() as tx:
                row = await tx.fetchone("SELECT v FROM kv WHERE k = 'n'")
                assert row is not None
                await asyncio.sleep(0)  # yield: invite interleaving if unserialized
                await tx.execute("UPDATE kv SET v = ? WHERE k = 'n'", (row["v"] + 1,))

        await asyncio.gather(*(increment() for _ in range(10)))
        row = await db.fetchone("SELECT v FROM kv WHERE k = 'n'")
        assert row is not None and row["v"] == 10
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_constraint_violation_is_typed_conflict(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        async with db.transaction() as tx:
            await tx.execute("INSERT INTO kv (k, v) VALUES ('dup', 1)")
        with pytest.raises(AppError) as exc_info:
            async with db.transaction() as tx:
                await tx.execute("INSERT INTO kv (k, v) VALUES ('dup', 2)")
        assert exc_info.value.kind is ErrorKind.CONFLICT
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_bad_sql_is_typed_not_raw_sqlite_error(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    try:
        with pytest.raises(AppError) as exc_info:
            await db.fetchone("SELECT * FROM does_not_exist")
        assert exc_info.value.kind is ErrorKind.INTERNAL
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_aclose_is_idempotent_and_blocks_further_use(tmp_path: Path) -> None:
    db = await _open(tmp_path)
    await db.aclose()
    await db.aclose()  # must not raise
    with pytest.raises(RuntimeError, match="closed"):
        await db.fetchone("SELECT 1")


@pytest.mark.asyncio
async def test_data_survives_reopen(tmp_path: Path) -> None:
    db = await _open(tmp_path, "persist.db")
    async with db.transaction() as tx:
        await tx.execute("INSERT INTO kv (k, v) VALUES ('keep', 42)")
    await db.aclose()

    reopened = await Database.open(tmp_path / "persist.db", config=StorageConfig())
    try:
        row = await reopened.fetchone("SELECT v FROM kv WHERE k = 'keep'")
        assert row is not None and row["v"] == 42
    finally:
        await reopened.aclose()
