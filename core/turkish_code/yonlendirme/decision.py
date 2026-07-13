"""The routing decision record (doc 45 §4 step 4, §9).

A pure value type capturing *what* was chosen and *why* — the full ranked
candidate list is the rationale. Recording it to the Timeline/metrics
(doc 26/51) is a future increment; this module only produces the structured
record those subsystems will consume.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from turkish_code.yonlendirme.scoring.combine import ScoredCandidate


@dataclass(frozen=True, slots=True)
class RoutingDecision:
    """The outcome of a routing request (doc 45 §4/§7)."""

    ranked_candidates: Sequence[ScoredCandidate]
    """Every scored candidate, best-first — the rationale (doc 45 §4)."""

    used_offline_fallback: bool
    """True if the primaries were empty/unroutable and Ollama was offered."""

    @property
    def selected(self) -> ScoredCandidate | None:
        """The top-ranked candidate, or ``None`` if nothing was routable."""
        return self.ranked_candidates[0] if self.ranked_candidates else None

    @property
    def is_unroutable(self) -> bool:
        """True if no candidate — not even the offline fallback — exists."""
        return not self.ranked_candidates


def build_decision(
    ranked_primaries: Sequence[ScoredCandidate],
    offline_fallback_scored: ScoredCandidate | None,
) -> RoutingDecision:
    """Assemble the decision: ranked primaries, falling back to Ollama (doc 45 §6)."""
    if ranked_primaries:
        return RoutingDecision(
            ranked_candidates=ranked_primaries, used_offline_fallback=False
        )
    if offline_fallback_scored is not None:
        return RoutingDecision(
            ranked_candidates=[offline_fallback_scored], used_offline_fallback=True
        )
    return RoutingDecision(ranked_candidates=[], used_offline_fallback=False)
