"""Tests for candidate generation + filtering (doc 45 §4 steps 1-2)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest
from turkish_code.ortak.saat import Clock
from turkish_code.saglayicilar.cache import InMemoryModelCache
from turkish_code.saglayicilar.manager import ProviderManager
from turkish_code.saglayicilar.provider import ProviderKind
from turkish_code.yonlendirme.candidates import generate_candidates
from turkish_code.yonlendirme.capability import CapabilityNeed, Requirement, Role
from turkish_code.yonlendirme.quota.store import InMemoryQuotaStore
from turkish_code.yonlendirme.quota.tracker import QuotaTracker

from tests.fakes import DEFAULT_CAPSET, StubProvider


@pytest.mark.asyncio
async def test_cloud_models_become_primaries(fixed_clock: Clock) -> None:
    manager = ProviderManager(
        [StubProvider("groq")], cache=InMemoryModelCache(), clock=fixed_clock
    )
    await manager.refresh_stale()
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    result = generate_candidates(manager, CapabilityNeed(), quota_tracker=tracker)

    assert len(result.primaries) == 1
    assert result.offline_fallback is None


@pytest.mark.asyncio
async def test_local_models_become_offline_fallback_not_primary(
    fixed_clock: Clock,
) -> None:
    manager = ProviderManager(
        [StubProvider("ollama", kind=ProviderKind.LOCAL, is_offline_fallback=True)],
        cache=InMemoryModelCache(),
        clock=fixed_clock,
    )
    await manager.refresh_stale()
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    result = generate_candidates(manager, CapabilityNeed(), quota_tracker=tracker)

    assert result.primaries == []
    assert result.offline_fallback is not None
    assert result.offline_fallback.provider.id == "ollama"


@pytest.mark.asyncio
async def test_self_hosted_local_provider_is_still_a_primary(
    fixed_clock: Clock,
) -> None:
    """A self-hosted NVIDIA NIM is local but NOT the offline fallback (doc 22 §5.4)."""
    manager = ProviderManager(
        [
            StubProvider(
                "nvidia-nim", kind=ProviderKind.LOCAL, is_offline_fallback=False
            )
        ],
        cache=InMemoryModelCache(),
        clock=fixed_clock,
    )
    await manager.refresh_stale()
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    result = generate_candidates(manager, CapabilityNeed(), quota_tracker=tracker)

    assert len(result.primaries) == 1
    assert result.offline_fallback is None


@pytest.mark.asyncio
async def test_hard_capability_mismatch_is_excluded(fixed_clock: Clock) -> None:
    embed_capset = replace(DEFAULT_CAPSET, role=Role.EMBED)
    manager = ProviderManager(
        [
            StubProvider(
                "embedder", roles=frozenset({Role.EMBED}), capabilities=embed_capset
            )
        ],
        cache=InMemoryModelCache(),
        clock=fixed_clock,
    )
    await manager.refresh_stale()
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)
    need = CapabilityNeed(role=Requirement(Role.CHAT, hard=True))

    result = generate_candidates(manager, need, quota_tracker=tracker)

    assert result.primaries == []


@pytest.mark.asyncio
async def test_cooling_down_provider_is_excluded_from_primaries(
    fixed_clock: Clock,
) -> None:
    manager = ProviderManager(
        [StubProvider("groq")], cache=InMemoryModelCache(), clock=fixed_clock
    )
    await manager.refresh_stale()
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)
    tracker.enter_cooldown("groq", until=fixed_clock.now() + timedelta(minutes=1))

    result = generate_candidates(manager, CapabilityNeed(), quota_tracker=tracker)

    assert result.primaries == []
