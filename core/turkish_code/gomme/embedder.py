"""The embedding contract (doc 14 §4) — interface only.

Implemented per the provider system (doc 21 §5 `Provider.embed()`); a
concrete `Embedder` wraps a routed provider call. No concrete backend is
built in this increment — only the contract every future implementation
(local ONNX, NIM/NeMo, provider-routed) must satisfy.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from turkish_code.gomme.meta import EmbeddingMetadata
from turkish_code.gomme.tur import EmbeddingKind


@runtime_checkable
class Embedder(Protocol):
    """Turns text into vectors (doc 14 §4).

    ``kind`` is mandatory on every call — asymmetric models use different
    encodings for ``document`` vs. ``query`` text, and mixing them up is a
    classic silent retrieval-quality bug (doc 14 §4/§13).
    """

    @property
    def metadata(self) -> EmbeddingMetadata:
        """This embedder's fixed identity/dimension/limits (doc 14 §4)."""
        ...

    async def embed(
        self, texts: Sequence[str], kind: EmbeddingKind
    ) -> Sequence[Sequence[float]]:
        """Embed ``texts`` as ``kind`` (doc 14 §4). One vector per input text."""
        ...

    def token_count(self, text: str) -> int:
        """Count ``text``'s tokens under this embedder's tokenizer (doc 14 §7)."""
        ...
