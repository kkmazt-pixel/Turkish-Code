"""Chunk model (doc 13 §5) — Parça, the unit Getirim indexes and retrieves.

``source`` is a tagged union (make illegal states unrepresentable, doc 36
§6): a chunk comes from either a file span or a memory item, never both/
neither. ``content_hash`` is CAS-aligned (doc 13 §5, doc 29) — the hash
algorithm itself is Storage's concern (doc 29 uses BLAKE3); this type just
carries the string.
"""

from __future__ import annotations

from dataclasses import dataclass

from turkish_code.gomme.kimlik import VectorId
from turkish_code.graf.kimlik import EntityId


@dataclass(frozen=True, slots=True)
class FileChunkSource:
    """A chunk sourced from a workspace file span (doc 13 §5)."""

    file_path: str
    start_line: int | None = None
    end_line: int | None = None


@dataclass(frozen=True, slots=True)
class MemoryChunkSource:
    """A chunk sourced from an indexed memory item (doc 13 §5, doc 11)."""

    memory_id: str


ChunkSource = FileChunkSource | MemoryChunkSource


@dataclass(frozen=True, slots=True)
class Chunk:
    """One indexed, retrievable unit (doc 13 §5)."""

    id: str
    source: ChunkSource
    language: str | None
    symbol: EntityId | None
    content_hash: str
    tokens: int
    embedding_ref: VectorId | None
