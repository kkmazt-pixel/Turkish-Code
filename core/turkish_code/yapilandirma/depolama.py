"""Storage-layer configuration schema (doc 29 §12) — durable-by-default tunables.

The knobs doc 29 §12 calls configurable: the SQLite busy-timeout (§14), the
fsync policy for durable writes (§8), the vector backend choice (§4, ADR-C),
and whether blob refcount GC runs (§6). Durable/safe defaults: fsync on, GC on,
sqlite-vec preferred (falls back to ``none`` at runtime if it can't load).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class VectorBackend(StrEnum):
    """Which vector-index backend the store uses (doc 29 §4, ADR-C)."""

    SQLITE_VEC = "sqlite-vec"
    NONE = "none"
    """No vector backend — vector operations raise ``UnsupportedError`` (ADR-C);
    the rest of storage stays fully functional."""


@dataclass(frozen=True, slots=True)
class StorageConfig:
    """Durable-by-default storage tunables (doc 29 §12).

    Attributes:
        busy_timeout_ms: SQLite busy-timeout for transient lock retry (doc 29 §14).
        fsync_durable: fsync journal/blob/snapshot writes (doc 29 §8); durable by
            default — relaxing it trades crash-safety for speed and is opt-in.
        vector_backend: preferred vector backend (doc 29 §4, ADR-C).
        blob_gc_enabled: run refcount GC to reclaim unreferenced blobs (doc 29 §6).
    """

    busy_timeout_ms: int = 5000
    fsync_durable: bool = True
    vector_backend: VectorBackend = VectorBackend.SQLITE_VEC
    blob_gc_enabled: bool = True

    def __post_init__(self) -> None:
        if self.busy_timeout_ms < 0:
            raise ValueError(
                f"busy_timeout_ms must be non-negative, got {self.busy_timeout_ms}"
            )
