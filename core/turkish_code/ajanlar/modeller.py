"""Agent runtime value objects (doc 18 §4/§9) — metadata, request/response, state.

The declarative pieces the Agent Runtime is built from: an :class:`AgentMetadata`
record (the ``AgentDef`` — role, tool grants, memory scope, doc 18 §4), the
:class:`AgentRequest`/:class:`AgentResponse` pair that frames one run, and the
:class:`SessionState` lifecycle enum (doc 18 §9). Pure data — routing, sessions,
and dispatch live in their own modules. This phase models how an agent *runs*,
never how it reasons (doc 15 is out of scope).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MemoryScope(StrEnum):
    """How much shared memory an agent's context may see (doc 18 §4/§7).

    Least privilege by default: ``ISOLATED`` agents touch no shared memory.
    """

    ISOLATED = "isolated"
    SESSION = "session"
    WORKSPACE = "workspace"


class SessionState(StrEnum):
    """The lifecycle state of an agent session (doc 18 §9).

    ``CREATED`` (built, not started) → ``RUNNING`` (started) ⇄ ``SUSPENDED``
    (paused, resumable) → ``STOPPED`` (halted, restartable) → ``SHUTDOWN``
    (terminal). The runtime lifecycle drives these transitions.
    """

    CREATED = "created"
    RUNNING = "running"
    SUSPENDED = "suspended"
    STOPPED = "stopped"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True, slots=True)
class AgentMetadata:
    """An agent's declarative contract — the ``AgentDef`` (doc 18 §4).

    Attributes:
        id: Stable agent id the registry keys on, e.g. ``"yonetici"``.
        name: Human-facing Turkish display name.
        role: Open role label, e.g. ``"orchestrator"``/``"kodlayici"`` (doc 18 §4).
        summary: Turkish description of what the agent is for.
        tool_grants: The tool names this agent may invoke — a subset, least
            privilege (doc 18 §7); empty means no tools.
        memory_scope: How much shared memory its context receives (doc 18 §7).
        timeout_ms: Upper bound on one run (doc 18 §8), must be positive.
        version: Additive schema version of this agent (doc 18 §24).
    """

    id: str
    name: str
    role: str
    summary: str
    tool_grants: frozenset[str] = field(default_factory=frozenset)
    memory_scope: MemoryScope = MemoryScope.ISOLATED
    timeout_ms: int = 60_000
    version: int = 1

    def __post_init__(self) -> None:
        for label, value in (("id", self.id), ("name", self.name), ("role", self.role)):
            if not value:
                raise ValueError(f"AgentMetadata.{label} must be non-empty")
        if self.timeout_ms <= 0:
            raise ValueError(
                f"AgentMetadata.timeout_ms must be positive, got {self.timeout_ms}"
            )
        if self.version < 1:
            raise ValueError(f"AgentMetadata.version must be >= 1, got {self.version}")

    def grants_tool(self, tool_name: str) -> bool:
        """Whether this agent is granted use of ``tool_name`` (doc 18 §7)."""
        return tool_name in self.tool_grants


@dataclass(frozen=True, slots=True)
class AgentRequest:
    """One agent run's inputs (doc 18 §6) — the target agent, message, and ids.

    Attributes:
        agent_id: The agent to run; resolved against the registry (doc 18 §10).
        message: The user goal/turn text this run acts on (Turkish).
        run_id: Unique id for this run — correlates cancellation, results, audit.
        session_id: The session this run belongs to, or ``None`` for a one-off.
    """

    agent_id: str
    message: str
    run_id: str
    session_id: str | None = None


@dataclass(frozen=True, slots=True)
class AgentResponse:
    """An agent run's typed result (doc 18 §6) — the final turn output.

    Failure is a raised :class:`~turkish_code.hata.AppError`, never a result
    value, so an ``AgentResponse`` always denotes a completed run.

    Attributes:
        run_id: Echoes :attr:`AgentRequest.run_id` for correlation.
        output: The agent's result text for this run (Turkish).
    """

    run_id: str
    output: str


class TurnRole(StrEnum):
    """Who produced a conversation turn (doc 18 §6)."""

    USER = "user"
    AGENT = "agent"


@dataclass(frozen=True, slots=True)
class ConversationTurn:
    """One message in an agent conversation (doc 18 §6) — an immutable value.

    Attributes:
        role: Whether the user or the agent produced this turn.
        content: The turn text (Turkish).
    """

    role: TurnRole
    content: str

    def __post_init__(self) -> None:
        if not self.content:
            raise ValueError("ConversationTurn.content must be non-empty")


@dataclass(frozen=True, slots=True)
class AgentChunk:
    """A streamed fragment of an agent run's output (doc 18 §9, doc 10 §11).

    An agent emits zero or more of these before its final
    :class:`AgentResponse`; they map to ``$/progress`` notifications on the wire.

    Attributes:
        run_id: Correlates the chunk with its run.
        delta: The incremental output text for this fragment (Turkish).
    """

    run_id: str
    delta: str
