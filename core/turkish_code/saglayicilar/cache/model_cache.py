"""In-memory model cache (doc 49).

A real, process-lifetime implementation of the ``ModelCache`` contract
(:mod:`turkish_code.saglayicilar.cache.refresh`). Storage (doc 29) doesn't
exist yet, so persistence across restarts is deferred; the interface is the
stable part (PR-8) — a disk-backed implementation can replace this one
without touching any caller.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from turkish_code.saglayicilar.provider import ModelInfo


@dataclass(frozen=True, slots=True)
class CacheEntry:
    """A provider's last-fetched model list with its fetch timestamp (doc 49 §4)."""

    models: Sequence[ModelInfo]
    fetched_at: datetime


class InMemoryModelCache:
    """Process-lifetime :class:`ModelCache` (doc 49) — no disk persistence yet."""

    def __init__(self) -> None:
        self._entries: dict[str, CacheEntry] = {}

    def get(self, provider_id: str) -> CacheEntry | None:
        return self._entries.get(provider_id)

    def put(
        self, provider_id: str, models: Sequence[ModelInfo], *, fetched_at: datetime
    ) -> None:
        self._entries[provider_id] = CacheEntry(
            models=tuple(models), fetched_at=fetched_at
        )

    def is_stale(
        self,
        provider_id: str,
        *,
        now: datetime,
        ttl: timedelta = timedelta(hours=24),
    ) -> bool:
        entry = self._entries.get(provider_id)
        if entry is None:
            return True
        return (now - entry.fetched_at) >= ttl
