"""The retriever contract (doc 13 §7) — interface only.

Three retriever kinds run in parallel per doc 13 §4/§7 (vector, lexical,
graph-seed); each implements this same, minimal Protocol so the fuser
(doc 13 §7) can treat them uniformly.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from turkish_code.getirim.parca import Chunk
from turkish_code.getirim.sorgu import RetrievalQuery


@dataclass(frozen=True, slots=True)
class RetrievedCandidate:
    """One retriever's scored hit (doc 13 §7)."""

    chunk: Chunk
    score: float
    retriever: str
    """Which retriever produced this: ``"vector"``/``"lexical"``/``"graph"``."""


@runtime_checkable
class Retriever(Protocol):
    """One retrieval signal (vector, lexical, or graph-seed) (doc 13 §7)."""

    async def retrieve(self, query: RetrievalQuery) -> Sequence[RetrievedCandidate]:
        """Return scored candidates for ``query``, bounded by ``query.top_k``."""
        ...
