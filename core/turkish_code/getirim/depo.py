"""Index storage contracts (doc 13 §6) — interface only.

``VectorIndex`` (sqlite-vec, or hnsw/faiss behind the same interface for
scale, doc 13 §6/PR-8) and ``LexicalIndex`` (FTS5 + Turkish/code analyzers).
No concrete backend here — Storage (doc 29) doesn't exist yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable


@runtime_checkable
class VectorIndex(Protocol):
    """ANN vector search over indexed chunk embeddings (doc 13 §6)."""

    async def upsert(self, chunk_id: str, vector: Sequence[float]) -> None:
        """Insert or replace ``chunk_id``'s embedding."""
        ...

    async def search(
        self, query_vector: Sequence[float], *, top_k: int
    ) -> Sequence[tuple[str, float]]:
        """Return up to ``top_k`` nearest ``(chunk_id, score)`` pairs."""
        ...


@runtime_checkable
class LexicalIndex(Protocol):
    """BM25 keyword search with Turkish + code analyzers (doc 13 §6)."""

    async def upsert(self, chunk_id: str, text: str) -> None:
        """Insert or replace ``chunk_id``'s indexed text."""
        ...

    async def search(
        self, query_text: str, *, top_k: int
    ) -> Sequence[tuple[str, float]]:
        """Return up to ``top_k`` matching ``(chunk_id, score)`` pairs."""
        ...
