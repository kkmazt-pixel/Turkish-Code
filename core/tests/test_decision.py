"""Tests for the routing decision record (doc 45 §4/§7)."""

from __future__ import annotations

from turkish_code.yonlendirme.decision import build_decision
from turkish_code.yonlendirme.scoring.combine import ScoredCandidate, score_candidate
from turkish_code.yonlendirme.scoring.model_score import ScoreBreakdown


def _candidate(model_id: str, provider_id: str, score: float) -> ScoredCandidate:
    breakdown = ScoreBreakdown(factors={}, total=score)
    return score_candidate(model_id, provider_id, breakdown, breakdown)


def test_primaries_present_are_used_directly() -> None:
    top = _candidate("m1", "p1", 1.0)
    decision = build_decision([top], None)

    assert decision.selected is top
    assert decision.used_offline_fallback is False
    assert decision.is_unroutable is False


def test_no_primaries_falls_back_to_offline() -> None:
    fallback = _candidate("ollama-model", "ollama", 0.5)
    decision = build_decision([], fallback)

    assert decision.selected is fallback
    assert decision.used_offline_fallback is True
    assert decision.is_unroutable is False


def test_no_primaries_and_no_fallback_is_unroutable() -> None:
    decision = build_decision([], None)

    assert decision.selected is None
    assert decision.is_unroutable is True
    assert decision.used_offline_fallback is False
