"""Tool-runtime composition (doc 20, doc 09 §7) — wire the subsystem's graph.

The one place that assembles the Araçlar runtime from its parts: a
:class:`ToolRegistry` of available tools, a :class:`PermissionGate` (the
Kabuk-bridge in production, a local policy gate by default), and the
:class:`ToolDispatcher` that runs the gated pipeline over them. Pure construction
by explicit injection — no import-time side effects, no singletons (PR-9); each
call returns a fresh graph. Real tool implementations and the Kabuk-bridge gate
are injected from outside; none are defined here.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.izin import (
    Grant,
    PermissionGate,
    PermissionMode,
    PermissionPolicy,
    PolicyPermissionGate,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.protocol import Tool


@dataclass(frozen=True, slots=True)
class ToolRuntime:
    """The wired Araçlar runtime (doc 20) — registry, gate, and dispatcher."""

    registry: ToolRegistry
    gate: PermissionGate
    dispatcher: ToolDispatcher


def build_tool_runtime(
    *,
    tools: Iterable[Tool] = (),
    gate: PermissionGate | None = None,
    permission_mode: PermissionMode = PermissionMode.ASK,
    grants: frozenset[Grant] = frozenset(),
) -> ToolRuntime:
    """Assemble the tool runtime (doc 20 §11, doc 09 §7).

    ``tools`` are registered fail-safe (duplicate names rejected). ``gate`` is
    injectable — production passes the Kabuk-bridge gate (doc 24 §10); when
    omitted a local :class:`PolicyPermissionGate` is built from
    ``permission_mode`` + ``grants``, defaulting to Ask mode (doc 24 §5). The
    dispatcher binds the registry and gate.
    """
    registry = ToolRegistry()
    registry.register_all(tools)
    resolved_gate: PermissionGate = (
        gate
        if gate is not None
        else PolicyPermissionGate(PermissionPolicy(mode=permission_mode, grants=grants))
    )
    dispatcher = ToolDispatcher(registry, resolved_gate)
    return ToolRuntime(registry=registry, gate=resolved_gate, dispatcher=dispatcher)
