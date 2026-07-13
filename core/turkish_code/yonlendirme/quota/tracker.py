"""Usage accounting per tier window (doc 48 §5).

Wraps a :class:`~turkish_code.yonlendirme.quota.store.QuotaStore` with the
clock-driven logic: recording usage, summing it over a trailing window, and
the cooldown state machine (doc 48 §8) — entered on rate-limit/error, cleared
when the caller's chosen expiry passes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from turkish_code.ortak.saat import Clock
from turkish_code.yonlendirme.quota.store import QuotaStore, UsageRecord


@dataclass(frozen=True, slots=True)
class UsageTotals:
    """Summed usage over a trailing window (doc 48 §5)."""

    requests: int
    tokens: int


class QuotaTracker:
    """Records usage and cooldown transitions for providers (doc 48 §5/§8)."""

    def __init__(self, store: QuotaStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def record_usage(
        self, provider_id: str, *, requests: int = 1, tokens: int = 0
    ) -> None:
        """Record one call's usage against ``provider_id``'s window (doc 48 §5)."""
        self._store.record_usage(
            provider_id,
            UsageRecord(at=self._clock.now(), requests=requests, tokens=tokens),
        )

    def usage_in_window(self, provider_id: str, *, window: timedelta) -> UsageTotals:
        """Sum ``provider_id``'s usage over the trailing ``window`` (doc 48 §5)."""
        since = self._clock.now() - window
        records = self._store.usage_since(provider_id, since=since)
        return UsageTotals(
            requests=sum(r.requests for r in records),
            tokens=sum(r.tokens for r in records),
        )

    def enter_cooldown(self, provider_id: str, *, until: datetime) -> None:
        """Mark ``provider_id`` as cooling down until ``until`` (doc 48 §8).

        The backoff *duration* is the resilience loop's decision (doc 45 §6);
        this only records the resulting expiry.
        """
        self._store.set_cooldown_until(provider_id, until)

    def is_cooling_down(self, provider_id: str) -> bool:
        """True if ``provider_id`` is still within its cooldown window (doc 48 §8)."""
        expiry = self._store.cooldown_until(provider_id)
        return expiry is not None and self._clock.now() < expiry
