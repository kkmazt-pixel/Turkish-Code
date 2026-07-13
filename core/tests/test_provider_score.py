"""Tests for provider scoring (doc 47 §5)."""

from __future__ import annotations

from turkish_code.saglayicilar.provider import HealthStatus
from turkish_code.yonlendirme.quota.headroom import CooldownState, ProviderQuotaState
from turkish_code.yonlendirme.scoring.provider_score import (
    ProviderScoreInputs,
    provider_score,
)


def _quota(
    headroom: float = 1.0, cooldown: CooldownState = CooldownState.AVAILABLE
) -> ProviderQuotaState:
    return ProviderQuotaState(
        headroom_requests=headroom, headroom_tokens=headroom, cooldown=cooldown
    )


def test_healthy_high_headroom_high_reliability_scores_high() -> None:
    inputs = ProviderScoreInputs(
        health=HealthStatus.UP, quota=_quota(1.0), reliability=1.0
    )
    assert provider_score(inputs).total == 1.0


def test_down_provider_scores_zero_regardless_of_quota() -> None:
    inputs = ProviderScoreInputs(
        health=HealthStatus.DOWN, quota=_quota(1.0), reliability=1.0
    )
    assert provider_score(inputs).total == 0.0


def test_cooling_down_provider_scores_zero() -> None:
    inputs = ProviderScoreInputs(
        health=HealthStatus.UP,
        quota=_quota(1.0, cooldown=CooldownState.COOLING_DOWN),
        reliability=1.0,
    )
    assert provider_score(inputs).total == 0.0


def test_degraded_health_scores_lower_than_up() -> None:
    up = provider_score(
        ProviderScoreInputs(health=HealthStatus.UP, quota=_quota(1.0), reliability=1.0)
    )
    degraded = provider_score(
        ProviderScoreInputs(
            health=HealthStatus.DEGRADED, quota=_quota(1.0), reliability=1.0
        )
    )
    assert degraded.total < up.total


def test_unbounded_quota_defaults_to_full_headroom() -> None:
    inputs = ProviderScoreInputs(
        health=HealthStatus.UP,
        quota=ProviderQuotaState(
            headroom_requests=None,
            headroom_tokens=None,
            cooldown=CooldownState.AVAILABLE,
        ),
        reliability=1.0,
    )
    assert provider_score(inputs).total == 1.0


def test_breakdown_includes_all_named_factors() -> None:
    inputs = ProviderScoreInputs(
        health=HealthStatus.UP, quota=_quota(0.5), reliability=0.8
    )
    factors = provider_score(inputs).factors
    assert set(factors) == {"health", "quotaHeadroom", "cooldownState", "reliability"}
