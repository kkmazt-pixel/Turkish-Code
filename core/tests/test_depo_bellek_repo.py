"""Tests for the SQLite MemoryRepository (doc 11 §5/§6/§10, doc 29 §9)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from turkish_code.bellek.depo import MemoryRepository
from turkish_code.bellek.durum import MemoryState
from turkish_code.bellek.katman import MemoryKind, MemoryLayer, MemoryScope
from turkish_code.bellek.kayit import MemoryItem
from turkish_code.bellek.kimlik import MemoryId
from turkish_code.depo.db import Database
from turkish_code.depo.migrate import load_migrations, migrate
from turkish_code.depo.repos.bellek import SqliteMemoryRepository
from turkish_code.gomme.kimlik import VectorId
from turkish_code.graf.kimlik import EntityId
from turkish_code.ortak.kimlik import EventId, ProvenanceRef, RunId
from turkish_code.yapilandirma.depolama import StorageConfig

_TS = dt.datetime(2026, 1, 1, 12, 0, tzinfo=dt.UTC)


async def _repo(tmp_path: Path) -> tuple[Database, SqliteMemoryRepository]:
    db = await Database.open(tmp_path / "workspace.db", config=StorageConfig())
    await migrate(db, load_migrations("workspace"))
    return db, SqliteMemoryRepository(db)


def _item(
    mid: str = "m1",
    *,
    scope: MemoryScope = MemoryScope.WORKSPACE,
    layer: MemoryLayer = MemoryLayer.SEMANTIC,
    state: MemoryState = MemoryState.ACTIVE,
    salience: float = 0.5,
    pinned: bool = False,
    rich: bool = False,
) -> MemoryItem:
    return MemoryItem(
        id=MemoryId(mid),
        layer=layer,
        scope=scope,
        kind=MemoryKind.FACT,
        state=state,
        title="Başlık",
        body="Gövde şğüçöı",
        links=[EntityId("e1"), EntityId("e2")] if rich else [],
        embedding_ref=(
            VectorId(ref="v1", embedder_id="bge-m3", dim=1024) if rich else None
        ),
        salience=salience,
        source=(
            ProvenanceRef(run_id=RunId("r1"), event_id=EventId("ev1")) if rich else None
        ),
        pinned=pinned,
        created_at=_TS,
        last_used_at=_TS,
        use_count=3,
        confidence=0.9,
        ttl=dt.timedelta(hours=2) if rich else None,
    )


@pytest.mark.asyncio
async def test_repo_satisfies_the_protocol(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        assert isinstance(repo, MemoryRepository)
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_save_and_get_round_trip_full_fidelity(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        item = _item(rich=True)
        await repo.save(item)
        assert await repo.get(MemoryId("m1")) == item
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_save_and_get_with_all_optionals_absent(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        item = _item(rich=False)
        await repo.save(item)
        got = await repo.get(MemoryId("m1"))
        assert got == item
        assert got is not None and got.embedding_ref is None and got.source is None
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_get_missing_returns_none(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        assert await repo.get(MemoryId("nope")) is None
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_save_upserts(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.save(_item(salience=0.1))
        await repo.save(_item(salience=0.99))
        got = await repo.get(MemoryId("m1"))
        assert got is not None and got.salience == 0.99
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_recall_filters_by_scope(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.save(_item("w", scope=MemoryScope.WORKSPACE))
        await repo.save(_item("g", scope=MemoryScope.GLOBAL))
        recalled = await repo.recall(scope=MemoryScope.WORKSPACE, limit=10)
        assert [i.id.value for i in recalled] == ["w"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_recall_filters_by_layers(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.save(_item("s", layer=MemoryLayer.SEMANTIC))
        await repo.save(_item("e", layer=MemoryLayer.EPISODIC))
        recalled = await repo.recall(
            scope=MemoryScope.WORKSPACE, layers=[MemoryLayer.EPISODIC], limit=10
        )
        assert [i.id.value for i in recalled] == ["e"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_recall_orders_by_salience_and_honors_limit(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.save(_item("lo", salience=0.1))
        await repo.save(_item("hi", salience=0.9))
        await repo.save(_item("mid", salience=0.5))
        recalled = await repo.recall(scope=MemoryScope.WORKSPACE, limit=2)
        assert [i.id.value for i in recalled] == ["hi", "mid"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_recall_excludes_superseded(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.save(_item("active", state=MemoryState.ACTIVE))
        await repo.save(_item("old", state=MemoryState.SUPERSEDED))
        recalled = await repo.recall(scope=MemoryScope.WORKSPACE, limit=10)
        assert [i.id.value for i in recalled] == ["active"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_forget_hides_from_recall_but_get_still_returns(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.save(_item("m1"))
        await repo.forget(MemoryId("m1"))
        assert await repo.recall(scope=MemoryScope.WORKSPACE, limit=10) == []
        assert await repo.get(MemoryId("m1")) is not None  # retained for audit
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_forget_survives_a_later_save(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.save(_item("m1"))
        await repo.forget(MemoryId("m1"))
        await repo.save(_item("m1", salience=0.7))  # update entity fields
        assert await repo.recall(scope=MemoryScope.WORKSPACE, limit=10) == []
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_purge_leaves_no_residue(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.save(_item("m1"))
        await repo.purge(MemoryId("m1"))
        assert await repo.get(MemoryId("m1")) is None
        assert await repo.recall(scope=MemoryScope.WORKSPACE, limit=10) == []
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_pin_and_unpin_persist(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.save(_item("m1", pinned=False))
        await repo.pin(MemoryId("m1"))
        got = await repo.get(MemoryId("m1"))
        assert got is not None and got.pinned is True
        await repo.unpin(MemoryId("m1"))
        got = await repo.get(MemoryId("m1"))
        assert got is not None and got.pinned is False
    finally:
        await db.aclose()
