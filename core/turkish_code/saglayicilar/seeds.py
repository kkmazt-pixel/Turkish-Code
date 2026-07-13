"""Curated per-model seed data (doc 46 §5) supplied to provider adapters.

Adapters do their own job (HTTP/wire format) and never invent capability
data themselves (doc 22 §3 "no shared special-casing"); the composition root
supplies curated seeds, and an unseeded model — one the provider returns that
we haven't curated yet — gets this conservative default rather than being
dropped (doc 46 §10).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

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


@dataclass(frozen=True, slots=True)
class ModelSeed:
    """Curated data for one model, keyed by the provider's model id (doc 46 §5)."""

    roles: frozenset[Role]
    capabilities: CapabilitySet
    context_window: int
    pricing: Mapping[str, float] | None = None


def default_seed(role: Role = Role.CHAT, *, context_window: int = 4096) -> ModelSeed:
    """A conservative seed for a model the provider offers but we haven't
    curated yet (doc 46 §10) — never blocks enumeration."""
    capabilities = CapabilitySet(
        role=role,
        reasoning=ReasoningDepth.BASIC,
        code_aptitude=CodeAptitude.BASIC,
        context_window=context_window,
        tool_use=ToolUse.NONE,
        vision=False,
        multilingual_tr=MultilingualTr.OK,
        latency_class=LatencyClass.NORMAL,
        cost_class=CostClass.STANDARD,
        max_output=min(context_window, 2048),
        streaming=True,
    )
    return ModelSeed(
        roles=frozenset({role}),
        capabilities=capabilities,
        context_window=context_window,
    )
