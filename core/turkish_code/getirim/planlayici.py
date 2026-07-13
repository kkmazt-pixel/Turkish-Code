"""The retrieval pipeline orchestration contract (doc 13 §4) — interface only.

Ties retrieve → fuse → rerank → assemble into one call. No concrete
implementation here (that requires the vector/lexical indexes, doc 13 §6,
which don't exist yet); this fixes the shape of the pipeline's entrypoint.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from turkish_code.getirim.kurulum import AssembledContext
from turkish_code.getirim.sorgu import RetrievalQuery


@runtime_checkable
class RetrievalPlanner(Protocol):
    """Runs the full retrieve→fuse→rerank→assemble pipeline (doc 13 §4)."""

    async def plan(self, query: RetrievalQuery) -> AssembledContext:
        """Execute the pipeline for ``query`` and return the assembled context."""
        ...
