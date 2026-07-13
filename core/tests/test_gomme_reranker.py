"""Tests for the Reranker contract (doc 14 §4, doc 13 §8)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from turkish_code.gomme.reranker import RerankedCandidate, Reranker


class _FakeReranker:
    @property
    def id(self) -> str:
        return "fake-reranker"

    async def rerank(
        self, query: str, candidates: Sequence[str]
    ) -> Sequence[RerankedCandidate]:
        return [
            RerankedCandidate(index=i, score=1.0 if query in c else 0.0)
            for i, c in enumerate(candidates)
        ]


def test_fake_reranker_satisfies_protocol() -> None:
    assert isinstance(_FakeReranker(), Reranker)


@pytest.mark.asyncio
async def test_rerank_scores_each_candidate() -> None:
    reranker = _FakeReranker()
    results = await reranker.rerank("auth", ["auth token", "unrelated text"])
    assert results[0].score == 1.0
    assert results[1].score == 0.0
