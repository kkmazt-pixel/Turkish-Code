"""Tests for the Embedder contract (doc 14 §4)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from turkish_code.gomme.embedder import Embedder
from turkish_code.gomme.meta import EmbeddingMetadata
from turkish_code.gomme.tur import EmbeddingKind


class _FakeEmbedder:
    """A minimal, real (non-mocked logic) Embedder conformance fixture."""

    @property
    def metadata(self) -> EmbeddingMetadata:
        return EmbeddingMetadata(id="fake-embed", dim=4, max_tokens=512, normalize=True)

    async def embed(
        self, texts: Sequence[str], kind: EmbeddingKind
    ) -> Sequence[Sequence[float]]:
        # Distinguishable per kind so a caller can catch a document/query mixup.
        offset = 0.0 if kind is EmbeddingKind.DOCUMENT else 1.0
        return [[offset, 0.0, 0.0, 0.0] for _ in texts]

    def token_count(self, text: str) -> int:
        return len(text.split())


def test_fake_embedder_satisfies_protocol() -> None:
    assert isinstance(_FakeEmbedder(), Embedder)


@pytest.mark.asyncio
async def test_embed_respects_kind() -> None:
    embedder = _FakeEmbedder()
    doc_vecs = await embedder.embed(["a"], EmbeddingKind.DOCUMENT)
    query_vecs = await embedder.embed(["a"], EmbeddingKind.QUERY)
    assert doc_vecs != query_vecs


def test_token_count_is_deterministic() -> None:
    embedder = _FakeEmbedder()
    assert embedder.token_count("bu bir test") == 3


def test_metadata_exposes_dimension() -> None:
    assert _FakeEmbedder().metadata.dim == 4
