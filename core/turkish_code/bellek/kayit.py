"""The memory record schema (doc 11 §5) — the persisted shape of one memory.

Every field beyond the write-time content is explicit: ``state`` makes the
lifecycle machine (doc 11 §12) a real, queryable fact rather than an
implicit convention; ``links``/``embedding_ref``/``source`` tie a memory to
the graph, retrieval, and Timeline, respectively.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from turkish_code.bellek.durum import MemoryState
from turkish_code.bellek.katman import MemoryKind, MemoryLayer, MemoryScope
from turkish_code.bellek.kimlik import MemoryId
from turkish_code.gomme.kimlik import VectorId
from turkish_code.graf.kimlik import EntityId
from turkish_code.ortak.kimlik import ProvenanceRef


@dataclass(frozen=True, slots=True)
class MemoryItem:
    """One durable memory record (doc 11 §5)."""

    id: MemoryId
    layer: MemoryLayer
    scope: MemoryScope
    kind: MemoryKind
    state: MemoryState
    title: str
    body: str
    links: Sequence[EntityId]
    embedding_ref: VectorId | None
    salience: float
    source: ProvenanceRef | None
    pinned: bool
    created_at: datetime
    last_used_at: datetime
    use_count: int
    confidence: float
    ttl: timedelta | None = None
