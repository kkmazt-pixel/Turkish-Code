"""Quota persistence contract (doc 48 §5/§9).

Separates raw usage/cooldown **storage** from the accounting logic
(:mod:`~turkish_code.yonlendirme.quota.tracker`). Storage (doc 29) doesn't
exist yet, so :class:`InMemoryQuotaStore` is process-lifetime only — usage
resets on restart (a known, approved gap; see doc 48 §11 "accounting is
best-effort"). A disk-backed store can replace it without touching callers
(PR-8).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """One provider call's usage, timestamped for windowed accounting."""

    at: datetime
    requests: int
    tokens: int


@runtime_checkable
class QuotaStore(Protocol):
    """Persists usage records and cooldown state per provider (doc 48 §5)."""

    def record_usage(self, provider_id: str, record: UsageRecord) -> None:
        """Append a usage record for ``provider_id``."""
        ...

    def usage_since(
        self, provider_id: str, *, since: datetime
    ) -> Sequence[UsageRecord]:
        """All usage records for ``provider_id`` at or after ``since``."""
        ...

    def set_cooldown_until(self, provider_id: str, until: datetime | None) -> None:
        """Set (or clear, with ``None``) the cooldown expiry for ``provider_id``."""
        ...

    def cooldown_until(self, provider_id: str) -> datetime | None:
        """The current cooldown expiry for ``provider_id``, or ``None`` if available."""
        ...


class InMemoryQuotaStore:
    """Process-lifetime :class:`QuotaStore` (doc 48 §5/§11)."""

    def __init__(self) -> None:
        self._usage: dict[str, list[UsageRecord]] = defaultdict(list)
        self._cooldowns: dict[str, datetime] = {}

    def record_usage(self, provider_id: str, record: UsageRecord) -> None:
        self._usage[provider_id].append(record)

    def usage_since(
        self, provider_id: str, *, since: datetime
    ) -> Sequence[UsageRecord]:
        return [r for r in self._usage.get(provider_id, []) if r.at >= since]

    def set_cooldown_until(self, provider_id: str, until: datetime | None) -> None:
        if until is None:
            self._cooldowns.pop(provider_id, None)
        else:
            self._cooldowns[provider_id] = until

    def cooldown_until(self, provider_id: str) -> datetime | None:
        return self._cooldowns.get(provider_id)
