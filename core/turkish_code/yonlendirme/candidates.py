"""Candidate generation + capability/health/quota filtering (doc 45 §4 steps 1-2).

Splits the registry into **primary** candidates (the cloud/self-host
primaries, doc 21 §4) and a single **offline fallback** candidate (Ollama) —
kept structurally separate so Ollama is never blended into normal scoring and
is only reached once every primary is exhausted (doc 21 §9, doc 45 §6).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from turkish_code.saglayicilar.manager import ProviderManager
from turkish_code.saglayicilar.provider import ModelInfo, Provider
from turkish_code.yonlendirme.capability import CapabilityNeed, matches_hard
from turkish_code.yonlendirme.quota.tracker import QuotaTracker


@dataclass(frozen=True, slots=True)
class Candidate:
    """A model paired with the provider that serves it (doc 45 §4)."""

    model: ModelInfo
    provider: Provider


@dataclass(frozen=True, slots=True)
class CandidateSet:
    """The filtered candidates for one routing request (doc 45 §4)."""

    primaries: Sequence[Candidate]
    offline_fallback: Candidate | None


def generate_candidates(
    manager: ProviderManager, need: CapabilityNeed, *, quota_tracker: QuotaTracker
) -> CandidateSet:
    """Filter the registry to hard-capable, non-cooling-down candidates (doc 45 §4).

    The provider marked ``is_offline_fallback`` (Ollama, doc 21 §4) is set
    aside rather than joined into ``primaries`` — this is a distinct role
    from ``kind`` (a self-hosted NVIDIA NIM is ``kind=local`` but still a
    primary, doc 22 §5.4).
    """
    primaries: list[Candidate] = []
    offline_fallback: Candidate | None = None

    for model in manager.all_models():
        if not matches_hard(model.capabilities, need):
            continue
        provider = manager.provider(model.provider_id)
        candidate = Candidate(model=model, provider=provider)

        if provider.is_offline_fallback:
            if offline_fallback is None:
                offline_fallback = candidate
            continue
        if quota_tracker.is_cooling_down(provider.id):
            continue
        primaries.append(candidate)

    return CandidateSet(primaries=primaries, offline_fallback=offline_fallback)
