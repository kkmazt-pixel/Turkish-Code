"""Scoring algorithms (doc 47) — ranks candidate models/providers so the
router (doc 45) can pick the best one. Model score × provider score,
reweighted by the cost/quota mode (doc 17 §4b, ADR-0011).
"""

from turkish_code.yonlendirme.scoring.combine import (
    ScoredCandidate,
    rank_candidates,
    score_candidate,
)
from turkish_code.yonlendirme.scoring.model_score import (
    ModelScoreInputs,
    ScoreBreakdown,
    model_score,
)
from turkish_code.yonlendirme.scoring.provider_score import (
    ProviderScoreInputs,
    provider_score,
)
from turkish_code.yonlendirme.scoring.weights import (
    ModelWeights,
    quality_floor_for_mode,
    weights_for_mode,
)

__all__ = [
    "ScoreBreakdown",
    "ModelScoreInputs",
    "model_score",
    "ProviderScoreInputs",
    "provider_score",
    "ModelWeights",
    "weights_for_mode",
    "quality_floor_for_mode",
    "ScoredCandidate",
    "score_candidate",
    "rank_candidates",
]
