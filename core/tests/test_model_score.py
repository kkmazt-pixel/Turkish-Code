"""Tests for model scoring (doc 47 §4/§7)."""

from __future__ import annotations

from turkish_code.yonlendirme.mod import CostMode
from turkish_code.yonlendirme.scoring.model_score import ModelScoreInputs, model_score
from turkish_code.yonlendirme.scoring.weights import weights_for_mode


def test_perfect_inputs_score_near_one() -> None:
    inputs = ModelScoreInputs(
        capability_fit=1.0,
        quality=1.0,
        turkish_quality=1.0,
        latency=1.0,
        cost=1.0,
        context_fit=1.0,
    )
    breakdown = model_score(inputs, weights_for_mode(CostMode.BALANCED))
    assert breakdown.total == 1.0


def test_worst_inputs_score_zero() -> None:
    inputs = ModelScoreInputs(
        capability_fit=0.0,
        quality=0.0,
        turkish_quality=0.0,
        latency=0.0,
        cost=0.0,
        context_fit=0.0,
    )
    breakdown = model_score(inputs, weights_for_mode(CostMode.BALANCED))
    assert breakdown.total == 0.0


def test_score_decomposes_into_named_factors() -> None:
    inputs = ModelScoreInputs(
        capability_fit=0.8,
        quality=0.5,
        turkish_quality=0.9,
        latency=0.3,
        cost=0.6,
        context_fit=1.0,
    )
    breakdown = model_score(inputs, weights_for_mode(CostMode.BALANCED))
    assert set(breakdown.factors) == {
        "capabilityFit",
        "quality",
        "turkishQuality",
        "latency",
        "cost",
        "contextFit",
    }


def test_performance_and_economy_rank_differently() -> None:
    """A cheap-but-mediocre model should score higher under Economy than Performance."""
    cheap_mediocre = ModelScoreInputs(
        capability_fit=0.6,
        quality=0.4,
        turkish_quality=0.4,
        latency=0.4,
        cost=1.0,
        context_fit=0.6,
    )
    performance_score = model_score(
        cheap_mediocre, weights_for_mode(CostMode.PERFORMANCE)
    )
    economy_score = model_score(cheap_mediocre, weights_for_mode(CostMode.ECONOMY))
    assert economy_score.total > performance_score.total
