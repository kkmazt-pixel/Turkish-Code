"""Tests for the in-memory quota store (doc 48 §5/§8)."""

from __future__ import annotations

from datetime import datetime, timedelta

from turkish_code.ortak.saat import Clock
from turkish_code.yonlendirme.quota.store import InMemoryQuotaStore, UsageRecord


def test_usage_since_filters_by_timestamp(fixed_clock: Clock) -> None:
    store = InMemoryQuotaStore()
    now = fixed_clock.now()
    store.record_usage(
        "groq", UsageRecord(at=now - timedelta(hours=2), requests=1, tokens=10)
    )
    store.record_usage("groq", UsageRecord(at=now, requests=1, tokens=20))

    recent = store.usage_since("groq", since=now - timedelta(minutes=1))
    assert len(recent) == 1
    assert recent[0].tokens == 20


def test_usage_since_empty_for_unknown_provider(fixed_clock: Clock) -> None:
    store = InMemoryQuotaStore()
    assert store.usage_since("unknown", since=fixed_clock.now()) == []


def test_cooldown_until_defaults_to_none() -> None:
    store = InMemoryQuotaStore()
    assert store.cooldown_until("groq") is None


def test_cooldown_can_be_set_and_cleared(fixed_clock: Clock) -> None:
    store = InMemoryQuotaStore()
    expiry: datetime = fixed_clock.now() + timedelta(minutes=5)
    store.set_cooldown_until("groq", expiry)
    assert store.cooldown_until("groq") == expiry

    store.set_cooldown_until("groq", None)
    assert store.cooldown_until("groq") is None
