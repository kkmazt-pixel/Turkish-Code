"""Tests for the capability dimensions (doc 46 §4)."""

from __future__ import annotations

from turkish_code.yonlendirme.capability import (
    CapabilitySet,
    CodeAptitude,
    CostClass,
    LatencyClass,
    MultilingualTr,
    ReasoningDepth,
    Role,
    ToolUse,
)


def test_ordinal_dimensions_are_orderable() -> None:
    assert ReasoningDepth.BASIC < ReasoningDepth.STRONG < ReasoningDepth.EXPERT
    assert CodeAptitude.NONE < CodeAptitude.BASIC < CodeAptitude.STRONG
    assert CodeAptitude.STRONG < CodeAptitude.EXPERT
    assert ToolUse.NONE < ToolUse.STRUCTURED < ToolUse.NATIVE
    assert MultilingualTr.POOR < MultilingualTr.OK < MultilingualTr.STRONG
    assert LatencyClass.SLOW < LatencyClass.NORMAL < LatencyClass.FAST
    assert CostClass.PREMIUM < CostClass.STANDARD < CostClass.CHEAP < CostClass.FREE


def test_capability_set_is_immutable() -> None:
    capset = CapabilitySet(
        role=Role.CHAT,
        reasoning=ReasoningDepth.STRONG,
        code_aptitude=CodeAptitude.STRONG,
        context_window=32_000,
        tool_use=ToolUse.NATIVE,
        vision=False,
        multilingual_tr=MultilingualTr.STRONG,
        latency_class=LatencyClass.FAST,
        cost_class=CostClass.CHEAP,
        max_output=8_000,
        streaming=True,
    )
    assert capset.role is Role.CHAT
    try:
        capset.role = Role.EMBED  # type: ignore[misc]
        assert False, "CapabilitySet must be frozen"
    except AttributeError:
        pass
