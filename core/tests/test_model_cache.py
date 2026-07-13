"""Tests for the in-memory model cache (doc 49 §5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from turkish_code.saglayicilar.cache import InMemoryModelCache
from turkish_code.saglayicilar.provider import ModelInfo
from turkish_code.yonlendirme.capability import (
    CapabilitySet,
    CodeAptitude,
    CostClass,
    LatencyClass,
    MultilingualTr,
    ReasoningDepth,
    Role,
    ToolUse,
)

_NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=UTC)


def _model(model_id: str = "m1") -> ModelInfo:
    return ModelInfo(
        id=model_id,
        provider_id="p1",
        roles=frozenset({Role.CHAT}),
        capabilities=CapabilitySet(
            role=Role.CHAT,
            reasoning=ReasoningDepth.STRONG,
            code_aptitude=CodeAptitude.STRONG,
            context_window=32_000,
            tool_use=ToolUse.NATIVE,
            vision=False,
            multilingual_tr=MultilingualTr.STRONG,
            latency_class=LatencyClass.FAST,
            cost_class=CostClass.CHEAP,
            max_output=8_000,
            streaming=True,
        ),
        context_window=32_000,
        pricing=None,
        tier=None,
        latency_profile=None,
        quality=None,
    )


def test_missing_entry_is_stale() -> None:
    cache = InMemoryModelCache()
    assert cache.get("p1") is None
    assert cache.is_stale("p1", now=_NOW) is True


def test_fresh_entry_is_not_stale() -> None:
    cache = InMemoryModelCache()
    cache.put("p1", [_model()], fetched_at=_NOW)
    assert cache.is_stale("p1", now=_NOW, ttl=timedelta(hours=24)) is False


def test_entry_becomes_stale_after_ttl() -> None:
    cache = InMemoryModelCache()
    cache.put("p1", [_model()], fetched_at=_NOW)
    later = _NOW + timedelta(hours=25)
    assert cache.is_stale("p1", now=later, ttl=timedelta(hours=24)) is True


def test_put_overwrites_previous_entry() -> None:
    cache = InMemoryModelCache()
    cache.put("p1", [_model("old")], fetched_at=_NOW)
    cache.put("p1", [_model("new")], fetched_at=_NOW)
    entry = cache.get("p1")
    assert entry is not None
    assert [m.id for m in entry.models] == ["new"]


def test_entries_are_isolated_per_provider() -> None:
    cache = InMemoryModelCache()
    cache.put("p1", [_model("a")], fetched_at=_NOW)
    assert cache.get("p2") is None
    assert cache.is_stale("p2", now=_NOW) is True
