"""Tests for the index storage contracts (doc 13 §6)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from turkish_code.getirim.depo import LexicalIndex, VectorIndex


class _FakeVectorIndex:
    def __init__(self) -> None:
        self._vectors: dict[str, Sequence[float]] = {}

    async def upsert(self, chunk_id: str, vector: Sequence[float]) -> None:
        self._vectors[chunk_id] = vector

    async def search(
        self, query_vector: Sequence[float], *, top_k: int
    ) -> Sequence[tuple[str, float]]:
        return [(chunk_id, 1.0) for chunk_id in self._vectors][:top_k]


class _FakeLexicalIndex:
    def __init__(self) -> None:
        self._texts: dict[str, str] = {}

    async def upsert(self, chunk_id: str, text: str) -> None:
        self._texts[chunk_id] = text

    async def search(
        self, query_text: str, *, top_k: int
    ) -> Sequence[tuple[str, float]]:
        hits = [(cid, 1.0) for cid, text in self._texts.items() if query_text in text]
        return hits[:top_k]


def test_vector_index_satisfies_protocol() -> None:
    assert isinstance(_FakeVectorIndex(), VectorIndex)


def test_lexical_index_satisfies_protocol() -> None:
    assert isinstance(_FakeLexicalIndex(), LexicalIndex)


@pytest.mark.asyncio
async def test_lexical_index_upsert_then_search() -> None:
    index = _FakeLexicalIndex()
    await index.upsert("c1", "def verifyToken(): ...")
    results = await index.search("verifyToken", top_k=5)
    assert results == [("c1", 1.0)]


@pytest.mark.asyncio
async def test_vector_index_upsert_then_search() -> None:
    index = _FakeVectorIndex()
    await index.upsert("c1", [0.1, 0.2])
    results = await index.search([0.1, 0.2], top_k=5)
    assert results == [("c1", 1.0)]
