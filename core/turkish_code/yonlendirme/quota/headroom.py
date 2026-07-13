"""Headroom + cooldown signals for the scorer/router (doc 48 §6, doc 47 §5).

Converts raw usage totals and a provider's declared tier limits into the
normalized ``[0, 1]`` headroom fractions and cooldown state that scoring
consumes directly as its ``quotaHeadroom``/``cooldownState`` factors.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from turkish_code.saglayicilar.provider import TierInfo
from turkish_code.yonlendirme.quota.tracker import UsageTotals

REQUESTS_LIMIT_KEY = "requests_per_window"
"""Well-known ``TierInfo.quota_limits`` key for the request-count limit."""

TOKENS_LIMIT_KEY = "tokens_per_window"
"""Well-known ``TierInfo.quota_limits`` key for the token-count limit."""


class CooldownState(StrEnum):
    """Whether a provider is currently skippable-by-cooldown (doc 48 §8)."""

    AVAILABLE = "available"
    COOLING_DOWN = "cooling_down"


@dataclass(frozen=True, slots=True)
class ProviderQuotaState:
    """The quota signal a provider contributes to scoring (doc 48 §6).

    ``headroom_requests``/``headroom_tokens`` are ``None`` when the provider
    declares no limit for that dimension (unbounded — never a limiting
    factor); otherwise a fraction in ``[0, 1]`` (0 = exhausted).
    """

    headroom_requests: float | None
    headroom_tokens: float | None
    cooldown: CooldownState


def compute_quota_state(
    tier_info: TierInfo, usage: UsageTotals, *, is_cooling_down: bool
) -> ProviderQuotaState:
    """Derive the scoring-facing quota state (doc 48 §6)."""
    return ProviderQuotaState(
        headroom_requests=_headroom(
            tier_info.quota_limits.get(REQUESTS_LIMIT_KEY), usage.requests
        ),
        headroom_tokens=_headroom(
            tier_info.quota_limits.get(TOKENS_LIMIT_KEY), usage.tokens
        ),
        cooldown=(
            CooldownState.COOLING_DOWN if is_cooling_down else CooldownState.AVAILABLE
        ),
    )


def _headroom(limit: int | None, used: int) -> float | None:
    if limit is None or limit <= 0:
        return None
    return max(0.0, (limit - used) / limit)
