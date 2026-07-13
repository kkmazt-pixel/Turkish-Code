"""Cost-mode weighting (doc 47 §6, doc 17 §4b).

Fixes the *shape* (which factors exist, how modes differ); the concrete
coefficients are an implementation choice authorized by doc 47's own
"OPEN (design)" note (§6) — tunable/versioned here as new benchmark evidence
accrues (doc 47 §16).
"""

from __future__ import annotations

from dataclasses import dataclass

from turkish_code.yonlendirme.mod import CostMode


@dataclass(frozen=True, slots=True)
class ModelWeights:
    """Per-factor weights feeding ``model_score`` (doc 47 §4/§6)."""

    capability_fit: float
    quality: float
    turkish_quality: float
    latency: float
    cost: float
    context_fit: float


_WEIGHTS: dict[CostMode, ModelWeights] = {
    # Performance: quality/latency/Turkish-fidelity high; cost/quota near-ignored.
    CostMode.PERFORMANCE: ModelWeights(
        capability_fit=1.0,
        quality=1.0,
        turkish_quality=1.0,
        latency=1.0,
        cost=0.1,
        context_fit=0.5,
    ),
    # Balanced: even weighting across all factors.
    CostMode.BALANCED: ModelWeights(
        capability_fit=1.0,
        quality=1.0,
        turkish_quality=1.0,
        latency=1.0,
        cost=1.0,
        context_fit=1.0,
    ),
    # Economy: cost favored; quality/Turkish still weighted (the floor, not
    # this weight, is what prevents a terrible model — see quality_floor_for_mode.
    CostMode.ECONOMY: ModelWeights(
        capability_fit=1.0,
        quality=0.5,
        turkish_quality=0.5,
        latency=0.5,
        cost=1.0,
        context_fit=0.5,
    ),
}

_QUALITY_FLOORS: dict[CostMode, float] = {
    CostMode.PERFORMANCE: 0.0,
    CostMode.BALANCED: 0.2,
    CostMode.ECONOMY: 0.35,
}
"""Minimum acceptable ``quality`` factor per mode (doc 47 §6 quality floor)."""


def weights_for_mode(mode: CostMode) -> ModelWeights:
    """The factor weights for ``mode`` (doc 47 §6)."""
    return _WEIGHTS[mode]


def quality_floor_for_mode(mode: CostMode) -> float:
    """The minimum ``quality`` a candidate must have under ``mode`` (doc 47 §6).

    Enforced by the router (doc 45), which filters candidates before scoring
    — this function only supplies the threshold.
    """
    return _QUALITY_FLOORS[mode]
