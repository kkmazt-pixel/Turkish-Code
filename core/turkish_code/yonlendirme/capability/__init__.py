"""Capability taxonomy (doc 46) — the shared vocabulary of what a model can do
and what a task needs. The common language between tasks and models that
makes model-first, capability-aware routing possible (doc 45).
"""

from turkish_code.yonlendirme.capability.match import matches_hard, soft_fit
from turkish_code.yonlendirme.capability.need import CapabilityNeed, Requirement
from turkish_code.yonlendirme.capability.taxonomy import (
    CapabilitySet,
    CodeAptitude,
    CostClass,
    LatencyClass,
    MultilingualTr,
    ReasoningDepth,
    Role,
    ToolUse,
)

__all__ = [
    "CapabilitySet",
    "Role",
    "ReasoningDepth",
    "CodeAptitude",
    "ToolUse",
    "MultilingualTr",
    "LatencyClass",
    "CostClass",
    "CapabilityNeed",
    "Requirement",
    "matches_hard",
    "soft_fit",
]
