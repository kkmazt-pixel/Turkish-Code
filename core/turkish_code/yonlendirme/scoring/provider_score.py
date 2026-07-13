"""Provider score: how healthy/available/quota-rich a provider is right now
(doc 47 §5). Live and dynamic (ADR-0004) — recomputed on every routing
decision, never a static per-provider preference.
"""

from __future__ import annotations

from dataclasses import dataclass

from turkish_code.saglayicilar.provider import HealthStatus
from turkish_code.yonlendirme.quota.headroom import CooldownState, ProviderQuotaState
from turkish_code.yonlendirme.scoring.model_score import ScoreBreakdown

_HEALTH_FACTOR: dict[HealthStatus, float] = {
    HealthStatus.UP: 1.0,
    HealthStatus.DEGRADED: 0.5,
    HealthStatus.COOLING_DOWN: 0.0,
    HealthStatus.DOWN: 0.0,
}


@dataclass(frozen=True, slots=True)
class ProviderScoreInputs:
    """The raw per-factor signals for one provider, right now (doc 47 §5)."""

    health: HealthStatus
    quota: ProviderQuotaState
    reliability: float
    """Rolling success rate in ``[0, 1]`` (doc 51 §4 `provider.reliability`)."""


def provider_score(inputs: ProviderScoreInputs) -> ScoreBreakdown:
    """Weighted, explainable provider score (doc 47 §5)."""
    declared = (inputs.quota.headroom_requests, inputs.quota.headroom_tokens)
    headroom_values = [h for h in declared if h is not None]
    quota_headroom = (
        sum(headroom_values) / len(headroom_values) if headroom_values else 1.0
    )
    is_cooling = inputs.quota.cooldown is CooldownState.COOLING_DOWN
    cooldown_factor = 0.0 if is_cooling else 1.0

    factors = {
        "health": _HEALTH_FACTOR[inputs.health],
        "quotaHeadroom": quota_headroom,
        "cooldownState": cooldown_factor,
        "reliability": inputs.reliability,
    }
    total = (
        factors["health"]
        * factors["cooldownState"]
        * ((factors["quotaHeadroom"] + factors["reliability"]) / 2)
    )
    return ScoreBreakdown(factors=factors, total=total)
