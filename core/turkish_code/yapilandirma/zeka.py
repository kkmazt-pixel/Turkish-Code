"""Intelligence-layer configuration schema (doc 11 §13, doc 12 §11,
doc 13 §12, doc 14 §11) — Memory/Graph/Retrieval/Embedding tunables.

Schema only: these knobs configure behavior (recall, extraction, chunking,
batching) that doesn't exist yet — no consumer reads these fields today. They
exist so the shape is fixed and versioned now, exactly as ``Settings.locale``
was added before anything consumed it in Phase 1.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    """Recall/consolidation tunables (doc 11 §13)."""

    recall_k: int = 8
    decay_rate: float = 0.05
    consolidation_interval_minutes: int = 60
    default_scope: str = "workspace"
    """``"workspace"`` or ``"global"`` (doc 11 §13)."""


@dataclass(frozen=True, slots=True)
class GraphConfig:
    """Extraction tunables (doc 12 §11)."""

    traversal_max_depth: int = 4
    traversal_max_breadth: int = 50
    summary_budget_tokens: int = 200
    extract_decisions_and_concepts: bool = True


@dataclass(frozen=True, slots=True)
class RetrievalConfig:
    """Chunking/fusion/rerank tunables (doc 13 §12)."""

    chunk_size_tokens: int = 400
    chunk_overlap_tokens: int = 50
    top_k_per_retriever: int = 20
    rerank_depth: int = 10
    assembly_budget_tokens: int = 4000
    index_backend: str = "sqlite-vec"
    """``"sqlite-vec"`` or ``"hnsw"`` (doc 13 §6/§12)."""


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    """Batching/cache tunables (doc 14 §11). Normalization is fixed on (doc 14 §6)."""

    default_embedder_id: str | None = None
    default_reranker_id: str | None = None
    batch_size: int = 32
    cache_size: int = 10_000
    cache_ttl_minutes: int = 60
