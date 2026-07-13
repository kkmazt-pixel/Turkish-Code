"""The cost/quota mode vocabulary (doc 17 §4b, ADR-0011).

Owned by ``caba/`` (doc 17, the full two-dial effort system), pulled forward
as a minimal leaf enum because quota policy (doc 48 §6) and scoring (doc 47
§6) both need it to weight their decisions. The compute-depth dial
(Hızlı/Dengeli/Derin/Maksimum) is a separate, orthogonal concept and is not
part of this module.
"""

from __future__ import annotations

from enum import StrEnum


class CostMode(StrEnum):
    """How aggressively the router trades quality for cost/quota (doc 17 §4b)."""

    PERFORMANCE = "performance"
    BALANCED = "balanced"
    ECONOMY = "economy"
