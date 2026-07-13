"""The reranker contract (doc 14 §4) — interface only.

A domain-level reranker (used by Getirim's final-precision step, doc 13 §8),
distinct from the raw ``Provider.rerank()`` call (doc 21 §5) a concrete
implementation would route through. Kept as its own small value type here
(rather than importing the provider-layer one) so ``gomme`` never depends on
``saglayicilar`` — the dependency already runs the other way (doc 21 §5 uses
``gomme.EmbeddingKind``).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class RerankedCandidate:
    """One reranked candidate: its original index and relevance score."""

    index: int
    score: float


@runtime_checkable
class Reranker(Protocol):
    """Re-scores candidates against a query for final precision (doc 14 §4)."""

    @property
    def id(self) -> str:
        """This reranker's model identity."""
        ...

    async def rerank(
        self, query: str, candidates: Sequence[str]
    ) -> Sequence[RerankedCandidate]:
        """Score each of ``candidates`` against ``query`` (doc 14 §4).

        Results are unordered; callers sort by ``score`` themselves.
        """
        ...
