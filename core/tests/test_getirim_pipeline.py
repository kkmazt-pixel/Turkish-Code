"""Tests for the retrieval pipeline contracts (doc 13 §4/§7/§8/§9)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from turkish_code.getirim.birlestirici import Fuser
from turkish_code.getirim.getirici import RetrievedCandidate, Retriever
from turkish_code.getirim.kurulum import AssembledContext, ContextAssembler
from turkish_code.getirim.parca import Chunk, FileChunkSource
from turkish_code.getirim.planlayici import RetrievalPlanner
from turkish_code.getirim.siralama import RankingStage
from turkish_code.getirim.sorgu import RetrievalQuery


def _chunk(chunk_id: str) -> Chunk:
    return Chunk(
        id=chunk_id,
        source=FileChunkSource(file_path="f.py"),
        language="python",
        symbol=None,
        content_hash="h",
        tokens=10,
        embedding_ref=None,
    )


class _FakeRetriever:
    def __init__(self, name: str, chunk_ids: Sequence[str]) -> None:
        self._name = name
        self._chunk_ids = chunk_ids

    async def retrieve(self, query: RetrievalQuery) -> Sequence[RetrievedCandidate]:
        return [
            RetrievedCandidate(chunk=_chunk(cid), score=1.0, retriever=self._name)
            for cid in self._chunk_ids
        ]


class _FakeFuser:
    def fuse(
        self, candidate_lists: Sequence[Sequence[RetrievedCandidate]]
    ) -> Sequence[RetrievedCandidate]:
        merged: dict[str, RetrievedCandidate] = {}
        for candidates in candidate_lists:
            for c in candidates:
                merged[c.chunk.id] = c
        return list(merged.values())


class _FakeRankingStage:
    async def rank(
        self, query: str, candidates: Sequence[RetrievedCandidate]
    ) -> Sequence[RetrievedCandidate]:
        return sorted(candidates, key=lambda c: c.chunk.id)


class _FakeContextAssembler:
    def assemble(
        self, candidates: Sequence[RetrievedCandidate], *, token_budget: int
    ) -> AssembledContext:
        chunks = [c.chunk for c in candidates]
        total = sum(c.tokens for c in chunks)
        return AssembledContext(chunks=chunks, total_tokens=min(total, token_budget))


class _FakePlanner:
    async def plan(self, query: RetrievalQuery) -> AssembledContext:
        return AssembledContext(chunks=[_chunk("c1")], total_tokens=10)


def test_retriever_satisfies_protocol() -> None:
    assert isinstance(_FakeRetriever("vector", []), Retriever)


def test_fuser_satisfies_protocol() -> None:
    assert isinstance(_FakeFuser(), Fuser)


def test_ranking_stage_satisfies_protocol() -> None:
    assert isinstance(_FakeRankingStage(), RankingStage)


def test_context_assembler_satisfies_protocol() -> None:
    assert isinstance(_FakeContextAssembler(), ContextAssembler)


def test_planner_satisfies_protocol() -> None:
    assert isinstance(_FakePlanner(), RetrievalPlanner)


@pytest.mark.asyncio
async def test_retrieve_fuse_rank_assemble_roundtrip() -> None:
    """A minimal end-to-end pass through the pipeline shape (doc 13 §4)."""
    query = RetrievalQuery(text="auth")
    vector = _FakeRetriever("vector", ["c2", "c1"])
    lexical = _FakeRetriever("lexical", ["c1"])

    vector_hits = await vector.retrieve(query)
    lexical_hits = await lexical.retrieve(query)
    fused = _FakeFuser().fuse([vector_hits, lexical_hits])
    ranked = await _FakeRankingStage().rank(query.text, fused)
    context = _FakeContextAssembler().assemble(ranked, token_budget=100)

    assert [c.id for c in context.chunks] == ["c1", "c2"]
    assert context.total_tokens == 20
