"""Tests for cost/quota mode aggressiveness (doc 48 §6)."""

from __future__ import annotations

from turkish_code.yonlendirme.mod import CostMode
from turkish_code.yonlendirme.quota.policy import quota_aggressiveness


def test_economy_is_most_aggressive_about_quota() -> None:
    assert quota_aggressiveness(CostMode.ECONOMY) == 1.0


def test_performance_is_least_aggressive_about_quota() -> None:
    assert quota_aggressiveness(CostMode.PERFORMANCE) < quota_aggressiveness(
        CostMode.BALANCED
    )


def test_all_modes_covered() -> None:
    for mode in CostMode:
        assert 0.0 <= quota_aggressiveness(mode) <= 1.0
