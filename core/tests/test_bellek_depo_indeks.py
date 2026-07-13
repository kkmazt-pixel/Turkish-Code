"""Tests for the memory repository + indexer contracts (doc 11 §6/§7/§10)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from turkish_code.bellek.depo import MemoryRepository
from turkish_code.bellek.durum import MemoryState
from turkish_code.bellek.indeks import MemoryIndexer
from turkish_code.bellek.katman import MemoryKind, MemoryLayer, MemoryScope
from turkish_code.bellek.kayit import MemoryItem
from turkish_code.bellek.kimlik import MemoryId
from turkish_code.gomme.kimlik import VectorId

_NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _item(memory_id: str, **overrides: object) -> MemoryItem:
    base: dict[str, object] = dict(
        id=MemoryId(memory_id),
        layer=MemoryLayer.SEMANTIC,
        scope=MemoryScope.WORKSPACE,
        kind=MemoryKind.FACT,
        state=MemoryState.ACTIVE,
        title="t",
        body="b",
        links=(),
        embedding_ref=None,
        salience=0.5,
        source=None,
        pinned=False,
        created_at=_NOW,
        last_used_at=_NOW,
        use_count=0,
        confidence=0.8,
    )
    base.update(overrides)
    return MemoryItem(**base)  # type: ignore[arg-type]


class _FakeMemoryRepository:
    """An in-memory conformance fixture — real logic, no persistence engine."""

    def __init__(self) -> None:
        self._items: dict[MemoryId, MemoryItem] = {}

    async def get(self, memory_id: MemoryId) -> MemoryItem | None:
        return self._items.get(memory_id)

    async def save(self, item: MemoryItem) -> None:
        self._items[item.id] = item

    async def recall(
        self,
        *,
        scope: MemoryScope,
        layers: Sequence[MemoryLayer] | None = None,
        limit: int,
    ) -> Sequence[MemoryItem]:
        items = [
            i
            for i in self._items.values()
            if i.scope == scope and i.state != MemoryState.PURGED
        ]
        if layers is not None:
            items = [i for i in items if i.layer in layers]
        return items[:limit]

    async def pin(self, memory_id: MemoryId) -> None:
        item = self._items[memory_id]
        self._items[memory_id] = replace(item, pinned=True, state=MemoryState.PINNED)

    async def unpin(self, memory_id: MemoryId) -> None:
        item = self._items[memory_id]
        self._items[memory_id] = replace(item, pinned=False, state=MemoryState.ACTIVE)

    async def forget(self, memory_id: MemoryId) -> None:
        item = self._items[memory_id]
        self._items[memory_id] = replace(item, state=MemoryState.PURGED)

    async def purge(self, memory_id: MemoryId) -> None:
        del self._items[memory_id]


class _FakeMemoryIndexer:
    async def index(self, item: MemoryItem) -> MemoryItem:
        return replace(
            item, embedding_ref=VectorId(ref="v1", embedder_id="fake", dim=4)
        )


def test_fake_repository_satisfies_protocol() -> None:
    assert isinstance(_FakeMemoryRepository(), MemoryRepository)


def test_fake_indexer_satisfies_protocol() -> None:
    assert isinstance(_FakeMemoryIndexer(), MemoryIndexer)


@pytest.mark.asyncio
async def test_save_then_get_round_trips() -> None:
    repo = _FakeMemoryRepository()
    await repo.save(_item("m1"))
    assert (await repo.get(MemoryId("m1"))).id == MemoryId("m1")  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_recall_filters_by_scope_and_layer() -> None:
    repo = _FakeMemoryRepository()
    await repo.save(
        _item("m1", scope=MemoryScope.WORKSPACE, layer=MemoryLayer.SEMANTIC)
    )
    await repo.save(_item("m2", scope=MemoryScope.GLOBAL, layer=MemoryLayer.PROFILE))

    results = await repo.recall(scope=MemoryScope.WORKSPACE, limit=10)
    assert [i.id.value for i in results] == ["m1"]


@pytest.mark.asyncio
async def test_pin_unpin_round_trip() -> None:
    repo = _FakeMemoryRepository()
    await repo.save(_item("m1"))
    await repo.pin(MemoryId("m1"))
    assert (await repo.get(MemoryId("m1"))).pinned is True  # type: ignore[union-attr]

    await repo.unpin(MemoryId("m1"))
    assert (await repo.get(MemoryId("m1"))).pinned is False  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_forget_hides_from_recall_but_keeps_record() -> None:
    repo = _FakeMemoryRepository()
    await repo.save(_item("m1", scope=MemoryScope.WORKSPACE))
    await repo.forget(MemoryId("m1"))

    assert await repo.get(MemoryId("m1")) is not None
    assert await repo.recall(scope=MemoryScope.WORKSPACE, limit=10) == []


@pytest.mark.asyncio
async def test_purge_leaves_no_recallable_residue() -> None:
    repo = _FakeMemoryRepository()
    await repo.save(_item("m1"))
    await repo.purge(MemoryId("m1"))
    assert await repo.get(MemoryId("m1")) is None


@pytest.mark.asyncio
async def test_indexer_populates_embedding_ref() -> None:
    indexed = await _FakeMemoryIndexer().index(_item("m1"))
    assert indexed.embedding_ref is not None
    assert indexed.embedding_ref.embedder_id == "fake"
