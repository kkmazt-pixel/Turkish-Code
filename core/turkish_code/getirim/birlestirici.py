"""The fusion contract (doc 13 §7) — interface only.

Combines the vector/lexical/graph-seed candidate lists into one ranked set
(RRF or weighted fusion, doc 13 §7) — robust to score-scale differences
across retrievers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from turkish_code.getirim.getirici import RetrievedCandidate


@runtime_checkable
class Fuser(Protocol):
    """Merges multiple retrievers' candidate lists into one (doc 13 §7)."""

    def fuse(
        self, candidate_lists: Sequence[Sequence[RetrievedCandidate]]
    ) -> Sequence[RetrievedCandidate]:
        """Fuse ``candidate_lists`` (one per retriever) into a single ranked list."""
        ...
