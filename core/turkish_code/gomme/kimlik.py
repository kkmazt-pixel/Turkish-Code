"""Vector identity (doc 14 §9).

A ``VectorId`` ties a stored embedding back to the exact model that produced
it. Retrieval must refuse to compare vectors from different embedders/dims
(doc 14 §9/§21) — carrying the model id and dimension alongside the vector
reference is what makes that check possible.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VectorId:
    """A reference to one stored embedding (doc 14 §9).

    ``embedder_id``/``dim`` are recorded so a consumer can refuse to compare
    vectors produced by different models — never a silent, wrong comparison.
    """

    ref: str
    embedder_id: str
    dim: int
