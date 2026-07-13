"""Tests for the light quality seed heuristic (doc 50 §4)."""

from __future__ import annotations

from turkish_code.yonlendirme.benchmark.quality import seed_quality
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


def _capset(**overrides: object) -> CapabilitySet:
    base = dict(
        role=Role.CHAT,
        reasoning=ReasoningDepth.EXPERT,
        code_aptitude=CodeAptitude.EXPERT,
        context_window=32_000,
        tool_use=ToolUse.NATIVE,
        vision=False,
        multilingual_tr=MultilingualTr.STRONG,
        latency_class=LatencyClass.FAST,
        cost_class=CostClass.CHEAP,
        max_output=8_000,
        streaming=True,
    )
    base.update(overrides)
    return CapabilitySet(**base)  # type: ignore[arg-type]


def test_top_tier_capabilities_score_near_one() -> None:
    signal = seed_quality(_capset())
    assert signal.score == 1.0


def test_weakest_capabilities_score_near_zero() -> None:
    weak = _capset(
        reasoning=ReasoningDepth.BASIC,
        code_aptitude=CodeAptitude.NONE,
        multilingual_tr=MultilingualTr.POOR,
    )
    signal = seed_quality(weak)
    assert signal.score < 0.2


def test_quality_seed_is_always_low_confidence() -> None:
    assert seed_quality(_capset()).confidence == "low"
