"""Tests for the tool permission policy + gate (doc 24 §5/§6)."""

from __future__ import annotations

import pytest
from turkish_code.araclar.izin import (
    Allow,
    Deny,
    Grant,
    PermissionGate,
    PermissionMode,
    PermissionPolicy,
    PermissionRequest,
    PolicyPermissionGate,
    PromptRequired,
)
from turkish_code.araclar.modeller import Capability, SideEffect


def _req(
    capability: Capability | None,
    side_effect: SideEffect,
    *,
    target: str | None = None,
) -> PermissionRequest:
    return PermissionRequest(
        tool="t", capability=capability, side_effect=side_effect, target=target
    )


def _policy(mode: PermissionMode, *grants: Grant) -> PermissionPolicy:
    return PermissionPolicy(mode=mode, grants=frozenset(grants))


@pytest.mark.parametrize("mode", list(PermissionMode))
def test_local_tool_is_always_allowed(mode: PermissionMode) -> None:
    # capability None = Çekirdek-local; allowed even when it mutates derived state.
    decision = _policy(mode).decide(_req(None, SideEffect.MUTATE))
    assert isinstance(decision, Allow)


@pytest.mark.parametrize("mode", list(PermissionMode))
def test_brokered_read_is_always_allowed(mode: PermissionMode) -> None:
    decision = _policy(mode).decide(_req(Capability.FS_READ, SideEffect.READ))
    assert isinstance(decision, Allow)


def test_plan_mode_denies_mutation_even_with_grant() -> None:
    # Plan is hard read-only: a standing grant must not override it (doc 24 §5).
    policy = _policy(PermissionMode.PLAN, Grant(Capability.FS_WRITE))
    decision = policy.decide(_req(Capability.FS_WRITE, SideEffect.MUTATE))
    assert isinstance(decision, Deny)


def test_ask_mode_prompts_for_ungranted_mutation() -> None:
    decision = _policy(PermissionMode.ASK).decide(
        _req(Capability.FS_WRITE, SideEffect.MUTATE, target="a.txt")
    )
    assert isinstance(decision, PromptRequired)
    assert decision.request.target == "a.txt"


def test_ask_mode_allows_granted_mutation() -> None:
    policy = _policy(PermissionMode.ASK, Grant(Capability.FS_WRITE))
    decision = policy.decide(_req(Capability.FS_WRITE, SideEffect.MUTATE))
    assert isinstance(decision, Allow)


def test_auto_mode_allows_mutation() -> None:
    decision = _policy(PermissionMode.AUTO).decide(
        _req(Capability.FS_WRITE, SideEffect.MUTATE)
    )
    assert isinstance(decision, Allow)


def test_auto_mode_allows_exec() -> None:
    decision = _policy(PermissionMode.AUTO).decide(
        _req(Capability.SHELL_EXEC, SideEffect.EXEC)
    )
    assert isinstance(decision, Allow)


def test_auto_mode_denies_ungranted_egress() -> None:
    # Egress is never auto-grantable — needs standing consent (doc 24 §5/§9).
    decision = _policy(PermissionMode.AUTO).decide(
        _req(Capability.NET_EGRESS, SideEffect.EGRESS)
    )
    assert isinstance(decision, Deny)


def test_auto_mode_allows_granted_egress() -> None:
    policy = _policy(PermissionMode.AUTO, Grant(Capability.NET_EGRESS))
    decision = policy.decide(_req(Capability.NET_EGRESS, SideEffect.EGRESS))
    assert isinstance(decision, Allow)


def test_ask_mode_prompts_for_ungranted_egress() -> None:
    decision = _policy(PermissionMode.ASK).decide(
        _req(Capability.NET_EGRESS, SideEffect.EGRESS)
    )
    assert isinstance(decision, PromptRequired)


def test_grant_target_must_match_exactly() -> None:
    policy = _policy(PermissionMode.ASK, Grant(Capability.FS_WRITE, target="a.txt"))
    allowed = policy.decide(
        _req(Capability.FS_WRITE, SideEffect.MUTATE, target="a.txt")
    )
    prompted = policy.decide(
        _req(Capability.FS_WRITE, SideEffect.MUTATE, target="b.txt")
    )
    assert isinstance(allowed, Allow)
    assert isinstance(prompted, PromptRequired)


def test_grant_with_no_target_matches_any_target() -> None:
    policy = _policy(PermissionMode.ASK, Grant(Capability.FS_WRITE, target=None))
    decision = policy.decide(
        _req(Capability.FS_WRITE, SideEffect.MUTATE, target="anything.txt")
    )
    assert isinstance(decision, Allow)


def test_empty_policy_defaults_to_no_grants() -> None:
    policy = PermissionPolicy(mode=PermissionMode.ASK)
    assert policy.grants == frozenset()


@pytest.mark.asyncio
async def test_policy_gate_returns_policy_decision() -> None:
    gate = PolicyPermissionGate(_policy(PermissionMode.PLAN))
    assert isinstance(gate, PermissionGate)
    decision = await gate.evaluate(_req(Capability.FS_WRITE, SideEffect.MUTATE))
    assert isinstance(decision, Deny)


@pytest.mark.asyncio
async def test_policy_gate_allows_when_policy_allows() -> None:
    gate = PolicyPermissionGate(_policy(PermissionMode.AUTO))
    decision = await gate.evaluate(_req(Capability.FS_WRITE, SideEffect.MUTATE))
    assert isinstance(decision, Allow)


def test_decision_values_are_immutable() -> None:
    deny = Deny(reason="x")
    with pytest.raises(AttributeError):
        deny.reason = "y"  # type: ignore[misc]
