"""The embed-and-link boundary (doc 11 §7 step 4) — interface only.

Bellek doesn't reimplement embedding (doc 14) or graph extraction (doc 12);
it calls out to them through this seam to enrich a candidate memory item
before persisting (doc 11 §6 "uses Getirim/Bilgi Grafı, doesn't reimplement").
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from turkish_code.bellek.kayit import MemoryItem


@runtime_checkable
class MemoryIndexer(Protocol):
    """Enriches a candidate memory item with an embedding + graph links."""

    async def index(self, item: MemoryItem) -> MemoryItem:
        """Return ``item`` with ``embedding_ref``/``links`` populated (doc 11 §7)."""
        ...
