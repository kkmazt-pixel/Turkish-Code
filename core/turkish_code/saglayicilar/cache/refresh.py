"""The model-cache contract (doc 49 §5/§7).

Separates the cache **store** (this Protocol) from the **refresh
orchestration** (calling a provider's ``list_models()`` and writing the
result) — the latter belongs to the future provider manager, which decides
*when* to refresh (background/on-demand/manual) using :meth:`ModelCache.is_stale`
as its signal. This subsystem only owns the store + freshness contract.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from turkish_code.saglayicilar.cache.model_cache import CacheEntry
from turkish_code.saglayicilar.provider import ModelInfo

DEFAULT_TTL = timedelta(hours=24)
"""The recovered default cache TTL (ADR-0013, doc 49 §5)."""


@runtime_checkable
class ModelCache(Protocol):
    """Stores each provider's last-known model list with a fetch timestamp."""

    def get(self, provider_id: str) -> CacheEntry | None:
        """Return the cached entry for ``provider_id``, or ``None`` if absent."""
        ...

    def put(
        self, provider_id: str, models: Sequence[ModelInfo], *, fetched_at: datetime
    ) -> None:
        """Store (overwrite) the model list for ``provider_id`` (doc 49 §4)."""
        ...

    def is_stale(
        self, provider_id: str, *, now: datetime, ttl: timedelta = DEFAULT_TTL
    ) -> bool:
        """True if the entry is absent or older than ``ttl`` (doc 49 §5).

        A missing entry counts as stale — the caller distinguishes "missing"
        (via :meth:`get` returning ``None``) from "stale-but-present" itself.
        """
        ...
