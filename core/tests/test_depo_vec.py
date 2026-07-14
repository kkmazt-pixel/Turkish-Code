"""Tests for the optional sqlite-vec VectorIndex (ADR-C, doc 29 §4/§6, doc 13 §6).

The happy-path tests require the sqlite-vec extension; they skip cleanly when it
is absent so the suite stays green on installs without the optional backend.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from turkish_code.depo.db import Database
from turkish_code.depo.vec import VECTOR_UNSUPPORTED_CODE, SqliteVectorIndex
from turkish_code.getirim.depo import VectorIndex
from turkish_code.hata import AppError, ErrorKind
from turkish_code.yapilandirma.depolama import StorageConfig, VectorBackend


async def _open(tmp_path: Path, backend: VectorBackend) -> Database:
    return await Database.open(
        tmp_path / "workspace.db",
        config=StorageConfig(vector_backend=backend),
    )


@pytest.mark.asyncio
async def test_open_without_backend_raises_typed_unsupported(tmp_path: Path) -> None:
    # vector_backend=none: the store still opens, but building the index raises.
    db = await _open(tmp_path, VectorBackend.NONE)
    try:
        assert db.vector_ready is False
        with pytest.raises(AppError) as exc_info:
            await SqliteVectorIndex.open(db, dim=4)
        assert exc_info.value.code == VECTOR_UNSUPPORTED_CODE
        assert exc_info.value.kind is ErrorKind.RESOURCE
        assert exc_info.value.retryable is False
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_store_opens_even_without_vector_backend(tmp_path: Path) -> None:
    # ADR-C: the rest of storage stays fully usable with the backend disabled.
    db = await _open(tmp_path, VectorBackend.NONE)
    try:
        await db.executescript("CREATE TABLE t (x INTEGER)")
        async with db.transaction() as tx:
            await tx.execute("INSERT INTO t (x) VALUES (1)")
        row = await db.fetchone("SELECT x FROM t")
        assert row is not None and row["x"] == 1
    finally:
        await db.aclose()


def _requires_vec(db: Database) -> None:
    if not db.vector_ready:
        pytest.skip("sqlite-vec extension not available")


@pytest.mark.asyncio
async def test_index_satisfies_the_protocol(tmp_path: Path) -> None:
    db = await _open(tmp_path, VectorBackend.SQLITE_VEC)
    try:
        _requires_vec(db)
        index = await SqliteVectorIndex.open(db, dim=4)
        assert isinstance(index, VectorIndex)
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_upsert_and_nearest_neighbor_search(tmp_path: Path) -> None:
    db = await _open(tmp_path, VectorBackend.SQLITE_VEC)
    try:
        _requires_vec(db)
        index = await SqliteVectorIndex.open(db, dim=4)
        await index.upsert("a", [1.0, 0.0, 0.0, 0.0])
        await index.upsert("b", [0.0, 1.0, 0.0, 0.0])
        hits = await index.search([1.0, 0.0, 0.0, 0.0], top_k=2)
        assert [cid for cid, _ in hits] == ["a", "b"]  # nearest first
        assert hits[0][1] >= hits[1][1]  # higher score = nearer
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_upsert_replaces_prior_vector(tmp_path: Path) -> None:
    db = await _open(tmp_path, VectorBackend.SQLITE_VEC)
    try:
        _requires_vec(db)
        index = await SqliteVectorIndex.open(db, dim=4)
        await index.upsert("a", [1.0, 0.0, 0.0, 0.0])
        await index.upsert("a", [0.0, 0.0, 0.0, 1.0])  # replace
        hits = await index.search([0.0, 0.0, 0.0, 1.0], top_k=5)
        assert [cid for cid, _ in hits] == ["a"]
        row = await db.fetchone("SELECT count(*) AS n FROM chunk_vec")
        assert row is not None and row["n"] == 1
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_search_respects_top_k(tmp_path: Path) -> None:
    db = await _open(tmp_path, VectorBackend.SQLITE_VEC)
    try:
        _requires_vec(db)
        index = await SqliteVectorIndex.open(db, dim=4)
        for i in range(5):
            await index.upsert(f"c{i}", [float(i), 0.0, 0.0, 0.0])
        hits = await index.search([0.0, 0.0, 0.0, 0.0], top_k=3)
        assert len(hits) == 3
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_dimension_mismatch_is_rejected(tmp_path: Path) -> None:
    db = await _open(tmp_path, VectorBackend.SQLITE_VEC)
    try:
        _requires_vec(db)
        index = await SqliteVectorIndex.open(db, dim=4)
        with pytest.raises(ValueError, match="4-dim"):
            await index.upsert("a", [1.0, 2.0])
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_non_positive_dimension_is_rejected(tmp_path: Path) -> None:
    db = await _open(tmp_path, VectorBackend.SQLITE_VEC)
    try:
        _requires_vec(db)
        with pytest.raises(ValueError, match="positive"):
            await SqliteVectorIndex.open(db, dim=0)
    finally:
        await db.aclose()
