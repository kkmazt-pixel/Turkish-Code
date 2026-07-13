"""The capability dimensions (doc 46 §4) — what a model declares it offers.

Ordinal dimensions subclass ``IntEnum`` so "at least X" comparisons (used by
hard/soft matching, doc 46 §6) are plain integer comparisons — no separate
ranking table to keep in sync.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class Role(StrEnum):
    """A model's primary function (doc 46 §4). Not ordinal — a set membership."""

    CHAT = "chat"
    EMBED = "embed"
    RERANK = "rerank"
    VISION = "vision"
    CODE = "code"


class ReasoningDepth(IntEnum):
    """Depth of reasoning quality, ordinal (doc 46 §4)."""

    BASIC = 1
    STRONG = 2
    EXPERT = 3


class CodeAptitude(IntEnum):
    """Code generation/understanding strength, ordinal (doc 46 §4)."""

    NONE = 0
    BASIC = 1
    STRONG = 2
    EXPERT = 3


class ToolUse(IntEnum):
    """Tool/function-calling ability, ordinal (doc 46 §4, doc 15 §6)."""

    NONE = 0
    STRUCTURED = 1
    NATIVE = 2


class MultilingualTr(IntEnum):
    """Turkish-quality dimension, ordinal and first-class (doc 46 §4, P2)."""

    POOR = 0
    OK = 1
    STRONG = 2


class LatencyClass(IntEnum):
    """Seeded latency class, refined by benchmarks (doc 46 §4, doc 50)."""

    SLOW = 0
    NORMAL = 1
    FAST = 2


class CostClass(IntEnum):
    """Seeded cost class from provider pricing (doc 46 §4, doc 22)."""

    PREMIUM = 0
    STANDARD = 1
    CHEAP = 2
    FREE = 3


@dataclass(frozen=True, slots=True)
class CapabilitySet:
    """What a model offers, across the canonical dimensions (doc 46 §4).

    Declared by a provider adapter's ``capabilities(model)`` (doc 21 §5).
    Immutable — capability data is curated/seeded, never mutated in place.
    """

    role: Role
    reasoning: ReasoningDepth
    code_aptitude: CodeAptitude
    context_window: int
    tool_use: ToolUse
    vision: bool
    multilingual_tr: MultilingualTr
    latency_class: LatencyClass
    cost_class: CostClass
    max_output: int
    streaming: bool
