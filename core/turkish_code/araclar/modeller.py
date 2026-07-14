"""Tool contract value objects (doc 20 §4) — the declarative tool schema.

A tool is a declarative :class:`ToolMetadata` contract plus an implementation
(:mod:`turkish_code.araclar.protocol`). These are immutable value objects: the
metadata is the source of truth for what the model may call and what the runtime
gates (doc 20 §4/§8), and a :class:`ToolRequest`/:class:`ToolResult` pair frames
one invocation. No behavior here — validation, permission, and dispatch live in
their own modules (doc 20 §5).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from turkish_code.ortak.kimlik import RunId


class SideEffect(StrEnum):
    """How far a tool's effect reaches — drives snapshot/consent (doc 20 §4)."""

    NONE = "none"
    """Pure computation; touches nothing outside the call."""
    READ = "read"
    """Reads state (files, index) but changes nothing."""
    MUTATE = "mutate"
    """Changes durable state; MUST be reversible/snapshot-backed (doc 20 §5.5)."""
    EXEC = "exec"
    """Runs a command/process in the user's world (doc 20 §7)."""
    EGRESS = "egress"
    """Sends data over the network; consent-gated (doc 24 §9)."""


class Capability(StrEnum):
    """The single permission class a tool requires (doc 24 §4).

    Çekirdek-local tools that only touch derived state carry no capability
    (``None`` in :class:`ToolMetadata`): they have no ambient privilege and no
    user-world effect (doc 20 §6).
    """

    FS_READ = "fs.read"
    FS_WRITE = "fs.write"
    SHELL_EXEC = "shell.exec"
    NET_EGRESS = "net.egress"
    OPEN_EXTERNAL = "open.external"
    SECRET_USE = "secret.use"
    WORKSPACE_SWITCH = "workspace.switch"


@dataclass(frozen=True, slots=True)
class ToolMetadata:
    """A tool's declarative contract — the ``ToolDef`` schema (doc 20 §4).

    Attributes:
        name: Stable dotted id the model calls, e.g. ``"fs.write"`` (doc 20 §4).
        summary: Turkish, model-facing "when/why to use" description (doc 20 §4).
        capability: The one permission class required, or ``None`` for a
            Çekirdek-local tool with no ambient privilege (doc 20 §6, doc 24 §4).
        side_effect: How far the effect reaches (doc 20 §4).
        brokered: ``True`` = executed by the Kabuk broker (privileged,
            user-world); ``False`` = Çekirdek-local, in-process (doc 20 §6).
        reversible: Mutating tools are snapshot-backed and reversible (doc 20 §5.5).
        idempotent: Whether repeating the call is safe (doc 20 §4).
        timeout_ms: Upper bound on one execution (doc 20 §9), must be positive.
        version: Additive schema version of this tool (doc 20 §24).
    """

    name: str
    summary: str
    capability: Capability | None
    side_effect: SideEffect
    brokered: bool
    reversible: bool
    idempotent: bool
    timeout_ms: int
    version: int = 1

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ToolMetadata.name must be a non-empty dotted id")
        if self.timeout_ms <= 0:
            raise ValueError(
                f"ToolMetadata.timeout_ms must be positive, got {self.timeout_ms}"
            )
        if self.version < 1:
            raise ValueError(f"ToolMetadata.version must be >= 1, got {self.version}")
        # A mutating tool that isn't reversible would violate the reversibility
        # guarantee (doc 20 §5.5/§22 #2) — reject it at construction.
        if self.side_effect is SideEffect.MUTATE and not self.reversible:
            raise ValueError(f"mutating tool {self.name!r} must be reversible")


@dataclass(frozen=True, slots=True)
class ToolRequest:
    """One invocation's inputs (doc 20 §5) — the name, args, and correlation id.

    Attributes:
        name: The tool to invoke; resolved against the registry (doc 20 §11).
        arguments: Raw, not-yet-validated call arguments as the model produced
            them; validated against the tool's contract before execution (doc 20 §8).
        call_id: Unique id for this invocation — correlates cancellation, results,
            and audit (doc 20 §11).
        run_id: The reasoning run this call belongs to, for provenance (doc 26);
            ``None`` when invoked outside a run.
    """

    name: str
    arguments: Mapping[str, object]
    call_id: str
    run_id: RunId | None = None


@dataclass(frozen=True, slots=True)
class ToolResult:
    """A tool's typed success result (doc 20 §5) — the final event of a call.

    Failure is expressed as a raised :class:`~turkish_code.hata.AppError`
    (doc 38 §7, :mod:`turkish_code.araclar.hata`), never as a result value, so a
    ``ToolResult`` always denotes success.

    Attributes:
        call_id: Echoes the originating :attr:`ToolRequest.call_id` for
            correlation (doc 20 §11).
        output: The tool-specific, JSON-serialisable result payload (doc 20 §4).
    """

    call_id: str
    output: object


@dataclass(frozen=True, slots=True)
class ToolProgress:
    """An incremental progress event emitted during a call (doc 20 §7/§17).

    A long-running tool emits zero or more of these before its final
    :class:`ToolResult`; they map to ``$/progress`` notifications on the wire
    (doc 10 §11) and never carry the terminal result.

    Attributes:
        call_id: Correlates the event with its invocation (doc 20 §11).
        message: A short, human-facing status line (Turkish).
        fraction: Optional completion estimate in ``[0.0, 1.0]``, or ``None``
            when the tool cannot estimate progress.
        payload: Optional structured incremental data (e.g. a chunk of output).
    """

    call_id: str
    message: str
    fraction: float | None = None
    payload: object = None

    def __post_init__(self) -> None:
        if self.fraction is not None and not 0.0 <= self.fraction <= 1.0:
            raise ValueError(
                f"ToolProgress.fraction must be in [0.0, 1.0], got {self.fraction}"
            )
