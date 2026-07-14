"""Tests for workspace storage assembly + composition wiring (doc 29 §5, doc 25 §4)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from turkish_code.bellek.depo import MemoryRepository
from turkish_code.bellek.durum import MemoryState
from turkish_code.bellek.katman import MemoryKind, MemoryLayer, MemoryScope
from turkish_code.bellek.kayit import MemoryItem
from turkish_code.bellek.kimlik import MemoryId
from turkish_code.depo.alan import StorageEngine, WorkspaceStore
from turkish_code.depo.yerlesim import StorageLayout
from turkish_code.getirim.depo import LexicalIndex
from turkish_code.graf.depo import KnowledgeRepository
from turkish_code.graf.kimlik import EntityId
from turkish_code.kompozisyon import build_storage
from turkish_code.yapilandirma.depolama import StorageConfig

_TS = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


def _memory(mid: str) -> MemoryItem:
    return MemoryItem(
        id=MemoryId(mid),
        layer=MemoryLayer.EPISODIC,
        scope=MemoryScope.WORKSPACE,
        kind=MemoryKind.FACT,
        state=MemoryState.ACTIVE,
        title="başlık",
        body="gövde",
        links=(),
        embedding_ref=None,
        salience=0.5,
        source=None,
        pinned=False,
        created_at=_TS,
        last_used_at=_TS,
        use_count=0,
        confidence=1.0,
        ttl=None,
    )


async def _engine(tmp_path: Path) -> StorageEngine:
    layout = StorageLayout(tmp_path)
    return await StorageEngine.open(layout, StorageConfig())


@pytest.mark.asyncio
async def test_engine_app_memory_is_a_repository(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    try:
        assert isinstance(engine.app_memory, MemoryRepository)
        # App DB migrated: a global-scope memory round-trips.
        await engine.app_memory.save(_memory("g1"))
        assert await engine.app_memory.get(MemoryId("g1")) is not None
    finally:
        await engine.aclose()


@pytest.mark.asyncio
async def test_open_workspace_yields_scoped_repositories(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    ws: WorkspaceStore = await engine.open_workspace("ws-abc")
    try:
        assert isinstance(ws.memory, MemoryRepository)
        assert isinstance(ws.knowledge, KnowledgeRepository)
        assert isinstance(ws.lexical, LexicalIndex)
        # Each substrate is migrated and usable.
        await ws.memory.save(_memory("m1"))
        assert await ws.memory.get(MemoryId("m1")) is not None
        # graph is query-only through the Protocol (doc 12 §8); the migrated
        # tables answer queries even though writes go through the extraction path.
        assert await ws.knowledge.get_node(EntityId("n1")) is None
        assert await ws.knowledge.search("anything", limit=5) == []
        await ws.lexical.upsert("c1", "verifyToken auth")
        assert [cid for cid, _ in await ws.lexical.search("verifyToken", top_k=5)] == [
            "c1"
        ]
        seq = await ws.journal.append(b"event")
        assert seq == 1
    finally:
        await ws.aclose()
        await engine.aclose()


@pytest.mark.asyncio
async def test_workspaces_are_physically_isolated(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    a = await engine.open_workspace("alpha")
    b = await engine.open_workspace("beta")
    try:
        await a.memory.save(_memory("only-in-a"))
        # b has its own DB file — a's memory is not visible there.
        assert await b.memory.get(MemoryId("only-in-a")) is None
        layout = StorageLayout(tmp_path)
        assert layout.workspace_db_path("alpha").exists()
        assert layout.workspace_db_path("beta").exists()
        assert layout.workspace_db_path("alpha") != layout.workspace_db_path("beta")
    finally:
        await a.aclose()
        await b.aclose()
        await engine.aclose()


@pytest.mark.asyncio
async def test_open_workspace_rejects_unsafe_id(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    try:
        with pytest.raises(ValueError, match="unsafe workspace id"):
            await engine.open_workspace("../escape")
    finally:
        await engine.aclose()


@pytest.mark.asyncio
async def test_build_storage_wires_engine_from_settings(tmp_path: Path) -> None:
    from turkish_code.yapilandirma.yukleyici import load_settings

    settings = load_settings(environ={"TURKISH_CODE_DATA_DIR": str(tmp_path)})
    engine = await build_storage(settings)
    try:
        ws = await engine.open_workspace("ws1")
        try:
            await ws.memory.save(_memory("wired"))
            assert await ws.memory.get(MemoryId("wired")) is not None
        finally:
            await ws.aclose()
    finally:
        await engine.aclose()


@pytest.mark.asyncio
async def test_vector_index_opens_or_reports_unsupported(tmp_path: Path) -> None:
    engine = await _engine(tmp_path)
    ws = await engine.open_workspace("ws-vec")
    try:
        if ws.db.vector_ready:
            index = await ws.open_vector_index(dim=4)
            await index.upsert("a", [1.0, 0.0, 0.0, 0.0])
            hits = await index.search([1.0, 0.0, 0.0, 0.0], top_k=1)
            assert [cid for cid, _ in hits] == ["a"]
        else:  # pragma: no cover - depends on optional backend availability
            from turkish_code.hata import AppError

            with pytest.raises(AppError):
                await ws.open_vector_index(dim=4)
    finally:
        await ws.aclose()
        await engine.aclose()
