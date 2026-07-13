"""Cost/quota mode aggressiveness (doc 48 §6, doc 17 §4b).

How strongly the scorer should weigh headroom/cost versus quality is a
function of the user's cost/quota mode: *Performance* spends premium quota
freely; *Economy* strongly prefers high-headroom/cheap providers (but never
below the task's quality floor — that floor is enforced by scoring, doc 47
§6, not here; this module only supplies the aggressiveness input).
"""

from __future__ import annotations

from turkish_code.yonlendirme.mod import CostMode

_AGGRESSIVENESS: dict[CostMode, float] = {
    CostMode.PERFORMANCE: 0.1,
    CostMode.BALANCED: 0.5,
    CostMode.ECONOMY: 1.0,
}


def quota_aggressiveness(mode: CostMode) -> float:
    """How strongly ``mode`` should weight quota headroom, in ``[0, 1]`` (doc 48 §6)."""
    return _AGGRESSIVENESS[mode]
