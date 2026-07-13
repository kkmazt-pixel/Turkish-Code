"""Embedder metadata (doc 14 §4/§6/§11) — the model contract's fixed facts.

``dim``/``normalize`` are what make the cosine==dot invariant hold (doc 14
§6); they never change for a given ``id`` — a model change is a new
:class:`EmbeddingMetadata`, never a mutation of an existing one (doc 14 §9).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmbeddingMetadata:
    """Fixed facts about one embedding model (doc 14 §4)."""

    id: str
    dim: int
    max_tokens: int
    normalize: bool
