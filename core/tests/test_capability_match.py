"""Tests for hard-filter + soft-fit capability matching (doc 46 §6)."""

from __future__ import annotations

from turkish_code.yonlendirme.capability import (
    CapabilityNeed,
    CapabilitySet,
    CodeAptitude,
    CostClass,
    LatencyClass,
    MultilingualTr,
    ReasoningDepth,
    Requirement,
    Role,
    ToolUse,
    matches_hard,
    soft_fit,
)


def _capset(**overrides: object) -> CapabilitySet:
    base = dict(
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
    base.update(overrides)
    return CapabilitySet(**base)  # type: ignore[arg-type]


def test_no_requirements_always_matches() -> None:
    assert matches_hard(_capset(), CapabilityNeed()) is True


def test_hard_requirement_met() -> None:
    need = CapabilityNeed(
        reasoning=Requirement(ReasoningDepth.STRONG, hard=True),
        multilingual_tr=Requirement(MultilingualTr.STRONG, hard=True),
    )
    assert matches_hard(_capset(), need) is True


def test_hard_requirement_unmet_fails() -> None:
    need = CapabilityNeed(multilingual_tr=Requirement(MultilingualTr.STRONG, hard=True))
    weak_tr = _capset(multilingual_tr=MultilingualTr.POOR)
    assert matches_hard(weak_tr, need) is False


def test_soft_requirement_never_filters() -> None:
    need = CapabilityNeed(
        multilingual_tr=Requirement(MultilingualTr.STRONG, hard=False)
    )
    weak_tr = _capset(multilingual_tr=MultilingualTr.POOR)
    assert matches_hard(weak_tr, need) is True


def test_exact_match_dimension_hard_bool() -> None:
    need = CapabilityNeed(vision=Requirement(True, hard=True))
    assert matches_hard(_capset(vision=False), need) is False
    assert matches_hard(_capset(vision=True), need) is True


def test_numeric_at_least_semantics() -> None:
    need = CapabilityNeed(context_window=Requirement(16_000, hard=True))
    assert matches_hard(_capset(context_window=32_000), need) is True
    assert matches_hard(_capset(context_window=8_000), need) is False


def test_soft_fit_only_includes_soft_dimensions() -> None:
    need = CapabilityNeed(
        reasoning=Requirement(ReasoningDepth.STRONG, hard=True),
        latency_class=Requirement(LatencyClass.FAST, hard=False),
    )
    fit = soft_fit(_capset(), need)
    assert "latency_class" in fit
    assert "reasoning" not in fit


def test_soft_fit_perfect_match_is_one() -> None:
    need = CapabilityNeed(latency_class=Requirement(LatencyClass.FAST, hard=False))
    assert (
        soft_fit(_capset(latency_class=LatencyClass.FAST), need)["latency_class"] == 1.0
    )


def test_soft_fit_partial_ordinal_credit() -> None:
    need = CapabilityNeed(reasoning=Requirement(ReasoningDepth.EXPERT, hard=False))
    fit = soft_fit(_capset(reasoning=ReasoningDepth.BASIC), need)["reasoning"]
    assert 0.0 < fit < 1.0


def test_soft_fit_numeric_ratio_capped_at_one() -> None:
    need = CapabilityNeed(context_window=Requirement(8_000, hard=False))
    assert soft_fit(_capset(context_window=32_000), need)["context_window"] == 1.0
    fit = soft_fit(_capset(context_window=4_000), need)["context_window"]
    assert fit == 0.5


def test_soft_fit_boolean_mismatch_is_zero() -> None:
    need = CapabilityNeed(streaming=Requirement(True, hard=False))
    assert soft_fit(_capset(streaming=False), need)["streaming"] == 0.0
