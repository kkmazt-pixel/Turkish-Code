"""Tests for the in-memory benchmark store (doc 50 §7)."""

from __future__ import annotations

from datetime import UTC, datetime

from turkish_code.yonlendirme.benchmark.profile import PerformanceProfile
from turkish_code.yonlendirme.benchmark.quality import QualitySignal
from turkish_code.yonlendirme.benchmark.store import InMemoryBenchmarkStore
from turkish_code.yonlendirme.capability import LatencyClass


def _profile() -> PerformanceProfile:
    return PerformanceProfile(
        latency_class=LatencyClass.FAST,
        typical_tps=42.0,
        quality=QualitySignal(score=0.8, confidence="low"),
        measured_at=datetime(2026, 7, 13, tzinfo=UTC),
    )


def test_missing_profile_returns_none() -> None:
    store = InMemoryBenchmarkStore()
    assert store.get("groq", "m1") is None


def test_put_then_get_round_trips() -> None:
    store = InMemoryBenchmarkStore()
    profile = _profile()
    store.put("groq", "m1", profile)
    assert store.get("groq", "m1") == profile


def test_entries_are_isolated_per_provider_and_model() -> None:
    store = InMemoryBenchmarkStore()
    store.put("groq", "m1", _profile())
    assert store.get("gemini", "m1") is None
    assert store.get("groq", "m2") is None
