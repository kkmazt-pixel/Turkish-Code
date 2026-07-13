"""Tests for headroom/cooldown signal computation (doc 48 §6)."""

from __future__ import annotations

from turkish_code.saglayicilar.provider import TierInfo
from turkish_code.yonlendirme.quota.headroom import (
    REQUESTS_LIMIT_KEY,
    TOKENS_LIMIT_KEY,
    CooldownState,
    compute_quota_state,
)
from turkish_code.yonlendirme.quota.tracker import UsageTotals


def test_headroom_computed_from_declared_limits() -> None:
    tier = TierInfo(
        tier="free", quota_limits={REQUESTS_LIMIT_KEY: 100, TOKENS_LIMIT_KEY: 1000}
    )
    usage = UsageTotals(requests=25, tokens=250)

    state = compute_quota_state(tier, usage, is_cooling_down=False)

    assert state.headroom_requests == 0.75
    assert state.headroom_tokens == 0.75


def test_no_declared_limit_means_unbounded_headroom() -> None:
    tier = TierInfo(tier="enterprise", quota_limits={})
    usage = UsageTotals(requests=1_000_000, tokens=1_000_000)

    state = compute_quota_state(tier, usage, is_cooling_down=False)

    assert state.headroom_requests is None
    assert state.headroom_tokens is None


def test_headroom_floors_at_zero_when_over_limit() -> None:
    tier = TierInfo(tier="free", quota_limits={REQUESTS_LIMIT_KEY: 10})
    usage = UsageTotals(requests=50, tokens=0)

    state = compute_quota_state(tier, usage, is_cooling_down=False)

    assert state.headroom_requests == 0.0


def test_cooldown_flag_maps_to_cooldown_state() -> None:
    tier = TierInfo(tier="free", quota_limits={})
    usage = UsageTotals(requests=0, tokens=0)

    cooling = compute_quota_state(tier, usage, is_cooling_down=True)
    available = compute_quota_state(tier, usage, is_cooling_down=False)

    assert cooling.cooldown is CooldownState.COOLING_DOWN
    assert available.cooldown is CooldownState.AVAILABLE
