"""The reranking stage contract (doc 13 §8) — Getirim's consumption boundary
over a :class:`~turkish_code.gomme.reranker.Reranker` (doc 14 §4).

Kept as its own small Protocol (rather than calling ``gomme.Reranker``
directly everywhere) so the pipeline can skip/shrink this step under low
effort (doc 13 §8, PR-7) without every caller knowing about ``gomme``.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from turkish_code.getirim.getirici import RetrievedCandidate


@runtime_checkable
class RankingStage(Protocol):
    """Re-scores fused candidates against the exact query (doc 13 §8)."""

    async def rank(
        self, query: str, candidates: Sequence[RetrievedCandidate]
    ) -> Sequence[RetrievedCandidate]:
        """Return ``candidates`` with updated scores, most relevant first."""
        ...
