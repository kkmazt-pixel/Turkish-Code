"""Tests for cost-mode weighting (doc 47 §6)."""

from __future__ import annotations

from turkish_code.yonlendirme.mod import CostMode
from turkish_code.yonlendirme.scoring.weights import (
    quality_floor_for_mode,
    weights_for_mode,
)


def test_performance_weights_cost_lowest() -> None:
    weights = weights_for_mode(CostMode.PERFORMANCE)
    assert weights.cost < weights.quality
    assert weights.cost < weights.latency


def test_economy_weights_cost_highest_relative_to_quality() -> None:
    weights = weights_for_mode(CostMode.ECONOMY)
    assert weights.cost > weights.quality


def test_balanced_weights_are_even() -> None:
    weights = weights_for_mode(CostMode.BALANCED)
    assert weights.capability_fit == weights.quality == weights.cost


def test_economy_has_the_highest_quality_floor() -> None:
    floors = {mode: quality_floor_for_mode(mode) for mode in CostMode}
    assert (
        floors[CostMode.ECONOMY]
        > floors[CostMode.BALANCED]
        > floors[CostMode.PERFORMANCE]
    )
