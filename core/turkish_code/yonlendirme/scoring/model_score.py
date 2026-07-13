"""Model score: how good a candidate model is for a task (doc 47 §4).

Every score decomposes into named factor contributions — no opaque black-box
scores (doc 47 §7, PR-11); the same :class:`ScoreBreakdown` shape is reused by
:mod:`~turkish_code.yonlendirme.scoring.provider_score`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from turkish_code.yonlendirme.scoring.weights import ModelWeights


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    """A score decomposed into named, weighted factor contributions (doc 47 §7)."""

    factors: Mapping[str, float]
    """Each factor's contribution to ``total`` (weight × raw value)."""

    total: float
    """The weighted sum, normalized to ``[0, 1]`` by the total weight."""


@dataclass(frozen=True, slots=True)
class ModelScoreInputs:
    """The raw, already-computed per-factor signals for one model (doc 47 §4).

    Each value is a fit/quality signal in ``[0, 1]``; callers derive these
    from the capability matcher (doc 46), benchmark evidence (doc 50), and
    the taxonomy's ordinal dimensions (doc 46 §4) before calling
    :func:`model_score`.
    """

    capability_fit: float
    quality: float
    turkish_quality: float
    latency: float
    cost: float
    context_fit: float


def model_score(inputs: ModelScoreInputs, weights: ModelWeights) -> ScoreBreakdown:
    """Weighted, explainable model score (doc 47 §4)."""
    named_weights = (
        ("capabilityFit", weights.capability_fit, inputs.capability_fit),
        ("quality", weights.quality, inputs.quality),
        ("turkishQuality", weights.turkish_quality, inputs.turkish_quality),
        ("latency", weights.latency, inputs.latency),
        ("cost", weights.cost, inputs.cost),
        ("contextFit", weights.context_fit, inputs.context_fit),
    )
    factors = {name: weight * value for name, weight, value in named_weights}
    total_weight = sum(weight for _, weight, _ in named_weights)
    total = sum(factors.values()) / total_weight if total_weight > 0 else 0.0
    return ScoreBreakdown(factors=factors, total=total)
