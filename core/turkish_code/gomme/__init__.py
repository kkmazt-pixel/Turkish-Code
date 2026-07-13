"""Embeddings subsystem (doc 14) — Gömme.

Owns the embedding/reranking vocabulary and model contract: the
``Embedder``/``Reranker`` Protocols (implemented per doc 21 §5), the
``EmbeddingKind`` asymmetric-model vocabulary, and ``VectorId``/
``EmbeddingMetadata`` identity types. No concrete backend (local ONNX,
NIM/NeMo, provider-routed) is built yet — batching/caching/re-embedding
(doc 14 §8/§9) land with the first real implementation.
"""

from turkish_code.gomme.embedder import Embedder
from turkish_code.gomme.kimlik import VectorId
from turkish_code.gomme.meta import EmbeddingMetadata
from turkish_code.gomme.reranker import RerankedCandidate, Reranker
from turkish_code.gomme.tur import EmbeddingKind

__all__ = [
    "EmbeddingKind",
    "VectorId",
    "EmbeddingMetadata",
    "Embedder",
    "Reranker",
    "RerankedCandidate",
]
