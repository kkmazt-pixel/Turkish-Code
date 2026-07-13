"""Tests for the quota tracker (doc 48 §5/§8)."""

from __future__ import annotations

from datetime import timedelta

from turkish_code.ortak.saat import Clock
from turkish_code.yonlendirme.quota.store import InMemoryQuotaStore
from turkish_code.yonlendirme.quota.tracker import QuotaTracker


def test_usage_in_window_sums_recorded_calls(fixed_clock: Clock) -> None:
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)
    tracker.record_usage("groq", requests=1, tokens=100)
    tracker.record_usage("groq", requests=1, tokens=50)

    totals = tracker.usage_in_window("groq", window=timedelta(hours=1))
    assert totals.requests == 2
    assert totals.tokens == 150


def test_usage_in_window_is_per_provider(fixed_clock: Clock) -> None:
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)
    tracker.record_usage("groq", requests=1, tokens=100)

    totals = tracker.usage_in_window("gemini", window=timedelta(hours=1))
    assert totals.requests == 0
    assert totals.tokens == 0


def test_not_cooling_down_by_default(fixed_clock: Clock) -> None:
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)
    assert tracker.is_cooling_down("groq") is False


def test_enter_cooldown_is_active_before_expiry(fixed_clock: Clock) -> None:
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)
    tracker.enter_cooldown("groq", until=fixed_clock.now() + timedelta(minutes=1))
    assert tracker.is_cooling_down("groq") is True


def test_cooldown_expires(fixed_clock: Clock) -> None:
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)
    tracker.enter_cooldown("groq", until=fixed_clock.now() - timedelta(seconds=1))
    assert tracker.is_cooling_down("groq") is False
