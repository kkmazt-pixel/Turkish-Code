"""A task's capability need (doc 46 §4) — what a task requires, independent
of any model/provider (provider-agnostic, ADR-0012).

Each dimension a task cares about is a :class:`Requirement`: a threshold value
plus whether it is **hard** (must satisfy, else the model is filtered out) or
**soft** (preferred; feeds the scorer's capability-fit, doc 47 §4).
"""

from __future__ import annotations

from dataclasses import dataclass

from turkish_code.yonlendirme.capability.taxonomy import (
    CodeAptitude,
    LatencyClass,
    MultilingualTr,
    ReasoningDepth,
    Role,
    ToolUse,
)


@dataclass(frozen=True, slots=True)
class Requirement[T]:
    """A single dimension's threshold and its hard/soft strength (doc 46 §4)."""

    value: T
    hard: bool


@dataclass(frozen=True, slots=True)
class CapabilityNeed:
    """What a task needs, per dimension (doc 46 §4/§6).

    A ``None`` field means the task doesn't care about that dimension. Ordinal
    requirements (``reasoning``, ``code_aptitude``, ``tool_use``,
    ``multilingual_tr``, ``latency_class``) are "at least this level"
    thresholds; ``context_window``/``max_output`` are "at least this many
    tokens"; ``role``/``vision``/``streaming`` are exact-match requirements.
    """

    role: Requirement[Role] | None = None
    reasoning: Requirement[ReasoningDepth] | None = None
    code_aptitude: Requirement[CodeAptitude] | None = None
    context_window: Requirement[int] | None = None
    tool_use: Requirement[ToolUse] | None = None
    vision: Requirement[bool] | None = None
    multilingual_tr: Requirement[MultilingualTr] | None = None
    latency_class: Requirement[LatencyClass] | None = None
    max_output: Requirement[int] | None = None
    streaming: Requirement[bool] | None = None
