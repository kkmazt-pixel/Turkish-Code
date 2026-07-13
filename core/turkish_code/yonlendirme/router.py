"""The router (doc 45) — decides which model, on which provider, right now.

Ties together candidate generation (doc 45 §4 steps 1-2), scoring (doc 47),
and quota (doc 48) into a :class:`~turkish_code.yonlendirme.decision.RoutingDecision`
(step 4). Execution with failover (steps 5-6) is
:mod:`~turkish_code.yonlendirme.resilience`, kept separate so a decision can
be inspected/tested without making any provider call.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import timedelta

from turkish_code.saglayicilar.manager import ProviderManager
from turkish_code.saglayicilar.provider import ModelInfo
from turkish_code.yonlendirme.benchmark.profile import PerformanceProfile
from turkish_code.yonlendirme.benchmark.quality import seed_quality
from turkish_code.yonlendirme.benchmark.store import BenchmarkStore
from turkish_code.yonlendirme.candidates import Candidate, generate_candidates
from turkish_code.yonlendirme.capability import CapabilityNeed, soft_fit
from turkish_code.yonlendirme.capability.taxonomy import CostClass, LatencyClass
from turkish_code.yonlendirme.decision import RoutingDecision, build_decision
from turkish_code.yonlendirme.mod import CostMode
from turkish_code.yonlendirme.quota.headroom import compute_quota_state
from turkish_code.yonlendirme.quota.tracker import QuotaTracker
from turkish_code.yonlendirme.scoring.combine import (
    ScoredCandidate,
    rank_candidates,
    score_candidate,
)
from turkish_code.yonlendirme.scoring.model_score import ModelScoreInputs, model_score
from turkish_code.yonlendirme.scoring.provider_score import (
    ProviderScoreInputs,
    provider_score,
)
from turkish_code.yonlendirme.scoring.weights import ModelWeights, weights_for_mode

ReliabilityLookup = Callable[[str], float]
"""``provider_id -> [0, 1]`` rolling success rate (doc 51 §4); defaults to 1.0
(no live metrics yet — a documented, honest gap until ``gozlem/`` lands)."""

DEFAULT_QUOTA_WINDOW = timedelta(hours=1)

_MULTILINGUAL_MAX = 2  # MultilingualTr.STRONG
_LATENCY_MAX = LatencyClass.FAST  # 2
_COST_MAX = CostClass.FREE  # 3


async def select(
    manager: ProviderManager,
    need: CapabilityNeed,
    cost_mode: CostMode,
    *,
    quota_tracker: QuotaTracker,
    benchmark_store: BenchmarkStore,
    quota_window: timedelta = DEFAULT_QUOTA_WINDOW,
    reliability: ReliabilityLookup = lambda _provider_id: 1.0,
) -> tuple[RoutingDecision, Mapping[tuple[str, str], Candidate]]:
    """Select the best model for ``need`` under ``cost_mode`` (doc 45 §4).

    Returns the decision plus a ``(provider_id, model_id) -> Candidate`` map so
    a caller can hand the ranked list straight to
    :func:`~turkish_code.yonlendirme.resilience.execute_with_failover`.
    """
    candidate_set = generate_candidates(manager, need, quota_tracker=quota_tracker)
    weights = weights_for_mode(cost_mode)

    scored_primaries = [
        await _score(
            c,
            need,
            weights,
            quota_tracker,
            benchmark_store,
            quota_window,
            reliability,
        )
        for c in candidate_set.primaries
    ]
    healthy_primaries = [
        s for s in scored_primaries if s.provider_breakdown.factors["health"] > 0.0
    ]
    ranked_primaries = rank_candidates(healthy_primaries)

    scored_fallback = (
        await _score(
            candidate_set.offline_fallback,
            need,
            weights,
            quota_tracker,
            benchmark_store,
            quota_window,
            reliability,
        )
        if candidate_set.offline_fallback is not None
        else None
    )

    decision = build_decision(ranked_primaries, scored_fallback)

    lookup: dict[tuple[str, str], Candidate] = {
        (c.provider.id, c.model.id): c for c in candidate_set.primaries
    }
    if candidate_set.offline_fallback is not None:
        fb = candidate_set.offline_fallback
        lookup[(fb.provider.id, fb.model.id)] = fb
    return decision, lookup


async def _score(
    candidate: Candidate,
    need: CapabilityNeed,
    weights: ModelWeights,
    quota_tracker: QuotaTracker,
    benchmark_store: BenchmarkStore,
    quota_window: timedelta,
    reliability: ReliabilityLookup,
) -> ScoredCandidate:
    model = candidate.model
    profile = benchmark_store.get(candidate.provider.id, model.id)

    model_breakdown = model_score(_model_inputs(model, need, profile), weights)

    health = await candidate.provider.health()
    usage = quota_tracker.usage_in_window(candidate.provider.id, window=quota_window)
    quota_state = compute_quota_state(
        candidate.provider.tier_info,
        usage,
        is_cooling_down=quota_tracker.is_cooling_down(candidate.provider.id),
    )
    provider_breakdown = provider_score(
        ProviderScoreInputs(
            health=health,
            quota=quota_state,
            reliability=reliability(candidate.provider.id),
        )
    )
    return score_candidate(
        model.id, candidate.provider.id, model_breakdown, provider_breakdown
    )


def _model_inputs(
    model: ModelInfo, need: CapabilityNeed, profile: PerformanceProfile | None
) -> ModelScoreInputs:
    fit_values = soft_fit(model.capabilities, need).values()
    capability_fit = sum(fit_values) / len(fit_values) if fit_values else 1.0

    quality = (
        profile.quality.score if profile else seed_quality(model.capabilities).score
    )
    latency_class = (
        profile.latency_class if profile else model.capabilities.latency_class
    )

    context_fit = 1.0
    if need.context_window is not None and need.context_window.value > 0:
        context_fit = min(1.0, model.context_window / need.context_window.value)

    return ModelScoreInputs(
        capability_fit=capability_fit,
        quality=quality,
        turkish_quality=model.capabilities.multilingual_tr / _MULTILINGUAL_MAX,
        latency=latency_class / _LATENCY_MAX,
        cost=model.capabilities.cost_class / _COST_MAX,
        context_fit=context_fit,
    )
