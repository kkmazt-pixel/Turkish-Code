"""Tests for vector identity and embedder metadata (doc 14 §4/§9)."""

from __future__ import annotations

from turkish_code.gomme.kimlik import VectorId
from turkish_code.gomme.meta import EmbeddingMetadata


def test_vector_id_carries_embedder_and_dim() -> None:
    vec = VectorId(ref="blake3:abc", embedder_id="bge-m3-local", dim=1024)
    assert vec.embedder_id == "bge-m3-local"
    assert vec.dim == 1024


def test_embedding_metadata_is_immutable() -> None:
    meta = EmbeddingMetadata(
        id="bge-m3-local", dim=1024, max_tokens=8192, normalize=True
    )
    try:
        meta.dim = 512  # type: ignore[misc]
        assert False, "EmbeddingMetadata must be frozen"
    except AttributeError:
        pass
