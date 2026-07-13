"""Tests for combining + ranking scored candidates (doc 47 §6/§9)."""

from __future__ import annotations

from turkish_code.yonlendirme.scoring.combine import rank_candidates, score_candidate
from turkish_code.yonlendirme.scoring.model_score import ScoreBreakdown


def _breakdown(total: float, **factors: float) -> ScoreBreakdown:
    return ScoreBreakdown(factors=factors, total=total)


def test_final_score_is_the_product() -> None:
    candidate = score_candidate("m1", "p1", _breakdown(0.8), _breakdown(0.5))
    assert candidate.final_score == 0.4


def test_zero_provider_score_zeroes_the_final_score() -> None:
    candidate = score_candidate("m1", "p1", _breakdown(0.9), _breakdown(0.0))
    assert candidate.final_score == 0.0


def test_rank_orders_by_final_score_descending() -> None:
    low = score_candidate("low", "p", _breakdown(0.2), _breakdown(1.0))
    high = score_candidate("high", "p", _breakdown(0.9), _breakdown(1.0))
    ranked = rank_candidates([low, high])
    assert [c.model_id for c in ranked] == ["high", "low"]


def test_tie_breaks_by_reliability_then_cost_then_id() -> None:
    a = score_candidate(
        "model-a",
        "provider-a",
        _breakdown(0.5, cost=0.5),
        _breakdown(0.5, reliability=0.9),
    )
    b = score_candidate(
        "model-b",
        "provider-b",
        _breakdown(0.5, cost=0.5),
        _breakdown(0.5, reliability=0.5),
    )
    ranked = rank_candidates([b, a])
    assert [c.model_id for c in ranked] == ["model-a", "model-b"]


def test_tie_break_falls_back_to_stable_id() -> None:
    a = score_candidate("model-a", "provider-a", _breakdown(0.5), _breakdown(0.5))
    b = score_candidate("model-b", "provider-a", _breakdown(0.5), _breakdown(0.5))
    ranked = rank_candidates([b, a])
    assert [c.model_id for c in ranked] == ["model-a", "model-b"]
