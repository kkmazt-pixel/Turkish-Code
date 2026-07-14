"""Tests for the content-addressed blob store (doc 29 §6/§14)."""

from __future__ import annotations

from pathlib import Path

import pytest
from turkish_code.depo.blobs import BlobHash, BlobStore
from turkish_code.depo.db import Database
from turkish_code.depo.migrate import load_migrations, migrate
from turkish_code.yapilandirma.depolama import StorageConfig


async def _store(tmp_path: Path, *, fsync: bool = True) -> tuple[Database, BlobStore]:
    db = await Database.open(
        tmp_path / "workspace.db", config=StorageConfig(fsync_durable=fsync)
    )
    await migrate(db, load_migrations("workspace"))
    return db, BlobStore(tmp_path / "blobs", db, fsync=fsync)


def _count_blobs(root: Path) -> int:
    return sum(1 for p in root.glob("*/*/*") if p.is_file())


def test_bad_blob_hash_is_rejected() -> None:
    with pytest.raises(ValueError):
        BlobHash("not-a-hash")
    with pytest.raises(ValueError):
        BlobHash("XYZ" * 21 + "x")  # right length, non-hex


@pytest.mark.asyncio
async def test_put_then_get_is_byte_identical(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    try:
        data = "şğüçöı İstanbul — binary\x00\xff".encode()
        h = await store.put(data)
        assert await store.get(h) == data
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_hashing_is_deterministic(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    try:
        a = await store.put(b"same content")
        b = await store.put(b"same content")
        assert a == b
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_identical_content_is_stored_once(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    try:
        await store.put(b"dup")
        await store.put(b"dup")
        assert _count_blobs(tmp_path / "blobs") == 1
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_content_is_sharded_by_prefix(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    try:
        h = await store.put(b"shard me")
        expected = tmp_path / "blobs" / h.value[:2] / h.value[2:4] / h.value
        assert expected.is_file()
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_get_and_exists_for_missing_blob(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    try:
        absent = BlobHash("0" * 64)
        assert await store.get(absent) is None
        assert await store.exists(absent) is False
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_gc_reclaims_orphan_but_keeps_referenced(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    try:
        kept = await store.put(b"referenced")
        await store.retain(kept)
        orphan = await store.put(b"orphaned")  # never retained

        reclaimed = await store.collect_garbage()

        assert reclaimed == 1
        assert await store.get(kept) == b"referenced"
        assert await store.get(orphan) is None
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_release_to_zero_makes_blob_collectable(tmp_path: Path) -> None:
    db, store = await _store(tmp_path)
    try:
        h = await store.put(b"temp ref")
        await store.retain(h)
        await store.retain(h)  # refcount 2
        await store.release(h)  # refcount 1 → still kept
        assert await store.collect_garbage() == 0
        assert await store.get(h) == b"temp ref"

        await store.release(h)  # refcount 0 → collectable
        assert await store.collect_garbage() == 1
        assert await store.get(h) is None
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_works_under_a_data_dir_with_spaces(tmp_path: Path) -> None:
    spaced = tmp_path / "Turkish Code"
    spaced.mkdir()
    db, store = await _store(spaced)
    try:
        h = await store.put(b"spaced path content")
        assert await store.get(h) == b"spaced path content"
    finally:
        await db.aclose()
