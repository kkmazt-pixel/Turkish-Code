"""Combine model + provider scores into a final, rankable candidate (doc 47 §6).

``finalScore(model) = modelScore(model) × providerScore(providerOf(model))``
— a live gate: a candidate on a down/cooling provider scores near zero
regardless of how good the model itself is.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from turkish_code.yonlendirme.scoring.model_score import ScoreBreakdown


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """A fully-scored (model, provider) candidate, ready to rank (doc 47 §6)."""

    model_id: str
    provider_id: str
    model_breakdown: ScoreBreakdown
    provider_breakdown: ScoreBreakdown
    final_score: float


def score_candidate(
    model_id: str,
    provider_id: str,
    model_breakdown: ScoreBreakdown,
    provider_breakdown: ScoreBreakdown,
) -> ScoredCandidate:
    """Combine a model's and its provider's breakdowns into one candidate."""
    return ScoredCandidate(
        model_id=model_id,
        provider_id=provider_id,
        model_breakdown=model_breakdown,
        provider_breakdown=provider_breakdown,
        final_score=model_breakdown.total * provider_breakdown.total,
    )


def rank_candidates(candidates: Sequence[ScoredCandidate]) -> Sequence[ScoredCandidate]:
    """Sort candidates best-first, deterministically (doc 47 §9).

    Tie-break order: higher ``final_score``, then higher provider
    ``reliability``, then higher (cheaper) model ``cost`` factor, then a
    stable ``(provider_id, model_id)`` sort — reproducible for identical
    inputs (PR-15).
    """

    def sort_key(candidate: ScoredCandidate) -> tuple[float, float, float, str, str]:
        reliability = candidate.provider_breakdown.factors.get("reliability", 0.0)
        cost = candidate.model_breakdown.factors.get("cost", 0.0)
        return (
            -candidate.final_score,
            -reliability,
            -cost,
            candidate.provider_id,
            candidate.model_id,
        )

    return sorted(candidates, key=sort_key)
