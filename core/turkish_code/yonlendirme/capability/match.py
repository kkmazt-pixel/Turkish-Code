"""Hard-filter + soft-fit inputs for the scorer (doc 46 §6).

The router filters candidates by **hard** requirements (must satisfy) via
:func:`matches_hard`; the scorer (doc 47) computes capability-fit over
**soft** requirements via :func:`soft_fit`. Ordinal dimensions are "at least
this level"; exact-match dimensions (``role``, ``vision``, ``streaming``)
must equal; numeric dimensions (``context_window``, ``max_output``) are
"at least this many."
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from turkish_code.yonlendirme.capability.need import CapabilityNeed, Requirement
from turkish_code.yonlendirme.capability.taxonomy import CapabilitySet


def matches_hard(capset: CapabilitySet, need: CapabilityNeed) -> bool:
    """True if ``capset`` satisfies every **hard** requirement in ``need``."""
    checks: tuple[tuple[Requirement[Any] | None, Any], ...] = (
        (need.role, capset.role),
        (need.reasoning, capset.reasoning),
        (need.code_aptitude, capset.code_aptitude),
        (need.context_window, capset.context_window),
        (need.tool_use, capset.tool_use),
        (need.vision, capset.vision),
        (need.multilingual_tr, capset.multilingual_tr),
        (need.latency_class, capset.latency_class),
        (need.max_output, capset.max_output),
        (need.streaming, capset.streaming),
    )
    return all(
        _satisfies(req.value, offered)
        for req, offered in checks
        if req is not None and req.hard
    )


def soft_fit(capset: CapabilitySet, need: CapabilityNeed) -> Mapping[str, float]:
    """Per-dimension fit in ``[0, 1]`` for every **soft** requirement in ``need``.

    Omits dimensions that are hard (already a pass/fail filter, not a fit
    score) or unset (the task doesn't care). Consumed by the scorer's
    ``capabilityFit`` factor (doc 47 §4).
    """
    named: tuple[tuple[str, Requirement[Any] | None, Any], ...] = (
        ("role", need.role, capset.role),
        ("reasoning", need.reasoning, capset.reasoning),
        ("code_aptitude", need.code_aptitude, capset.code_aptitude),
        ("context_window", need.context_window, capset.context_window),
        ("tool_use", need.tool_use, capset.tool_use),
        ("vision", need.vision, capset.vision),
        ("multilingual_tr", need.multilingual_tr, capset.multilingual_tr),
        ("latency_class", need.latency_class, capset.latency_class),
        ("max_output", need.max_output, capset.max_output),
        ("streaming", need.streaming, capset.streaming),
    )
    return {
        name: _fit(req.value, offered)
        for name, req, offered in named
        if req is not None and not req.hard
    }


def _satisfies(required: object, offered: object) -> bool:
    """A single dimension's hard-requirement check."""
    if isinstance(required, bool):
        return offered == required
    if isinstance(required, int):  # covers IntEnum ordinals and plain ints
        return bool(offered >= required)  # type: ignore[operator]
    return offered == required


def _fit(required: object, offered: object) -> float:
    """A single dimension's soft-fit score in ``[0, 1]``."""
    if isinstance(required, bool):
        return 1.0 if offered == required else 0.0
    if isinstance(required, int) and required > 0:
        ratio = offered / required  # type: ignore[operator]
        return min(1.0, float(ratio))
    if isinstance(required, int):  # required == 0: any offered level satisfies
        return 1.0
    return 1.0 if offered == required else 0.0
