"""Tests for the top-level router (doc 45 §4)."""

from __future__ import annotations

import pytest
from turkish_code.ortak.saat import Clock
from turkish_code.saglayicilar.cache import InMemoryModelCache
from turkish_code.saglayicilar.manager import ProviderManager
from turkish_code.saglayicilar.provider import HealthStatus, ProviderKind
from turkish_code.yonlendirme.benchmark.store import InMemoryBenchmarkStore
from turkish_code.yonlendirme.capability import CapabilityNeed
from turkish_code.yonlendirme.mod import CostMode
from turkish_code.yonlendirme.quota.store import InMemoryQuotaStore
from turkish_code.yonlendirme.quota.tracker import QuotaTracker
from turkish_code.yonlendirme.router import select

from tests.fakes import DEFAULT_CAPSET, StubProvider


async def _manager(providers: list[StubProvider], clock: Clock) -> ProviderManager:
    manager = ProviderManager(providers, cache=InMemoryModelCache(), clock=clock)
    await manager.refresh_stale()
    return manager


@pytest.mark.asyncio
async def test_select_picks_the_only_primary(fixed_clock: Clock) -> None:
    manager = await _manager([StubProvider("groq")], fixed_clock)
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    decision, lookup = await select(
        manager,
        CapabilityNeed(),
        CostMode.BALANCED,
        quota_tracker=tracker,
        benchmark_store=InMemoryBenchmarkStore(),
    )

    assert decision.selected is not None
    assert decision.selected.provider_id == "groq"
    assert decision.used_offline_fallback is False
    assert (decision.selected.provider_id, decision.selected.model_id) in lookup


@pytest.mark.asyncio
async def test_select_falls_back_to_ollama_when_no_primaries(
    fixed_clock: Clock,
) -> None:
    manager = await _manager(
        [StubProvider("ollama", kind=ProviderKind.LOCAL, is_offline_fallback=True)],
        fixed_clock,
    )
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    decision, _lookup = await select(
        manager,
        CapabilityNeed(),
        CostMode.BALANCED,
        quota_tracker=tracker,
        benchmark_store=InMemoryBenchmarkStore(),
    )

    assert decision.used_offline_fallback is True
    assert decision.selected is not None
    assert decision.selected.provider_id == "ollama"


@pytest.mark.asyncio
async def test_select_excludes_down_providers(fixed_clock: Clock) -> None:
    manager = await _manager(
        [StubProvider("dead", health=HealthStatus.DOWN)], fixed_clock
    )
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    decision, _lookup = await select(
        manager,
        CapabilityNeed(),
        CostMode.BALANCED,
        quota_tracker=tracker,
        benchmark_store=InMemoryBenchmarkStore(),
    )

    assert decision.is_unroutable is True


@pytest.mark.asyncio
async def test_select_prefers_healthier_provider(fixed_clock: Clock) -> None:
    manager = await _manager(
        [
            StubProvider("degraded", health=HealthStatus.DEGRADED),
            StubProvider("healthy", health=HealthStatus.UP),
        ],
        fixed_clock,
    )
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    decision, _lookup = await select(
        manager,
        CapabilityNeed(),
        CostMode.BALANCED,
        quota_tracker=tracker,
        benchmark_store=InMemoryBenchmarkStore(),
    )

    assert decision.selected is not None
    assert decision.selected.provider_id == "healthy"


@pytest.mark.asyncio
async def test_select_uses_reliability_lookup(fixed_clock: Clock) -> None:
    manager = await _manager(
        [StubProvider("a", capabilities=DEFAULT_CAPSET), StubProvider("b")], fixed_clock
    )
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    decision, _lookup = await select(
        manager,
        CapabilityNeed(),
        CostMode.BALANCED,
        quota_tracker=tracker,
        benchmark_store=InMemoryBenchmarkStore(),
        reliability=lambda provider_id: 1.0 if provider_id == "b" else 0.1,
    )

    assert decision.selected is not None
    assert decision.selected.provider_id == "b"
