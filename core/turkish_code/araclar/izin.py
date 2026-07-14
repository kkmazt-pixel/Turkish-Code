"""Permission decisions for tool calls (doc 24) — the Çekirdek-side port + policy.

Every sensitive tool call is gated before execution (doc 20 §5, doc 24 §6). The
**authority** lives in the Kabuk broker (doc 24 §10): the Çekirdek cannot
self-authorize. This module models that boundary as a :class:`PermissionGate`
port the dispatcher consults — the real Kabuk bridge implements it for brokered
tools — plus a concrete :class:`PermissionPolicy` that encodes the documented
mode/grant decision table (doc 24 §5/§6) for Çekirdek-local tools and as an
injectable default. A decision is one of :class:`Allow`, :class:`Deny`, or
:class:`PromptRequired` (the "ask" branch). The policy is data the *user*
controls (mode + standing grants); evaluating it is enforcement, never the agent
widening its own scope (doc 24 §21 #3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable

from turkish_code.araclar.modeller import Capability, SideEffect


class PermissionMode(StrEnum):
    """The session's permission mode (doc 24 §5) — chosen by the user."""

    PLAN = "plan"
    """Planla — read-only; no mutating/exec/egress action runs."""
    ASK = "ask"
    """Sor (default) — sensitive actions prompt each time (with remember)."""
    AUTO = "auto"
    """Otomatik — pre-granted within scope; egress still needs standing consent."""


@dataclass(frozen=True, slots=True)
class Grant:
    """A standing permission: ``capability × target`` (doc 24 §8).

    ``target is None`` grants the capability for any target; otherwise the grant
    matches only that exact target. (Glob/predicate targets are a future
    extension, doc 24 §18 — kept exact here.)
    """

    capability: Capability
    target: str | None = None


@dataclass(frozen=True, slots=True)
class PermissionRequest:
    """What is being gated (doc 24 §6): a tool's capability + precise target."""

    tool: str
    capability: Capability | None
    side_effect: SideEffect
    target: str | None = None


@dataclass(frozen=True, slots=True)
class Allow:
    """The action is permitted; proceed (doc 24 §6)."""


@dataclass(frozen=True, slots=True)
class Deny:
    """A typed denial; the model adapts, never bypasses (doc 24 §6)."""

    reason: str


@dataclass(frozen=True, slots=True)
class PromptRequired:
    """User consent is required — the "ask" branch (doc 24 §6).

    Carries the request so the prompt can show exactly what will happen
    (capability, target, why). A non-interactive gate returns this rather than
    guessing; the dispatcher/caller resolves it (fail-safe: never an implicit
    allow, doc 24 §6).
    """

    request: PermissionRequest
    reason: str


Decision = Allow | Deny | PromptRequired
"""The three-way outcome of evaluating a permission request (doc 24 §6)."""

_SENSITIVE = frozenset({SideEffect.MUTATE, SideEffect.EXEC, SideEffect.EGRESS})
"""Side effects that require a permission decision (doc 24 §5)."""


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    """The user's mode + standing grants, evaluated per the doc 24 §6 table.

    Immutable from the caller's perspective — a tool/agent cannot mutate it to
    widen its own scope (doc 24 §21 #3). Only the composition root / user builds
    it from persisted grants (doc 24 §8).
    """

    mode: PermissionMode
    grants: frozenset[Grant] = field(default_factory=frozenset)

    def decide(self, request: PermissionRequest) -> Decision:
        """Resolve ``request`` to a decision (doc 24 §6)."""
        if request.capability is None:
            # Çekirdek-local: no ambient privilege, derived-state only (doc 20 §6).
            return Allow()
        if request.side_effect not in _SENSITIVE:
            # Non-sensitive brokered read, e.g. fs.read default-allow (doc 24 §4).
            return Allow()
        if self.mode is PermissionMode.PLAN:
            # Hard read-only: a standing grant does not override Plan (doc 24 §5).
            return Deny("plan mode is read-only; sensitive actions are blocked")
        if self._granted(request):
            return Allow()
        if self.mode is PermissionMode.ASK:
            return PromptRequired(request=request, reason="user consent required")
        # AUTO: pre-grants mutate/exec within scope, but egress is never
        # auto-grantable — it needs a standing grant (checked above) (doc 24 §5/§9).
        if request.side_effect is SideEffect.EGRESS:
            return Deny("egress requires standing consent, not auto-grantable")
        return Allow()

    def _granted(self, request: PermissionRequest) -> bool:
        return any(
            grant.capability == request.capability
            and (grant.target is None or grant.target == request.target)
            for grant in self.grants
        )


@runtime_checkable
class PermissionGate(Protocol):
    """The port the dispatcher consults before executing (doc 20 §5, doc 24 §6).

    Async because the authoritative implementation bridges to the Kabuk engine
    over the Core Channel (doc 24 §10) and may await a user decision.
    """

    async def evaluate(self, request: PermissionRequest) -> Decision:
        """Decide whether ``request`` may proceed (doc 24 §6)."""
        ...


class PolicyPermissionGate:
    """A :class:`PermissionGate` backed by a local :class:`PermissionPolicy`.

    Used for Çekirdek-local tools (no Kabuk round-trip) and as an injectable
    default/test gate. Brokered enforcement uses a Kabuk-bridge gate instead
    (doc 24 §10).
    """

    def __init__(self, policy: PermissionPolicy) -> None:
        self._policy = policy

    async def evaluate(self, request: PermissionRequest) -> Decision:
        return self._policy.decide(request)
