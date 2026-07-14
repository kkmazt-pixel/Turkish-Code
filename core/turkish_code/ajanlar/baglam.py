"""Agent execution context (doc 18 §7) — the ambient "how" of one run.

Three views make up what an agent works through, never touching subsystems
directly (PR-9, doc 18 §16):

- :class:`ConversationContext` — a read-only view of the conversation so far.
- :class:`SessionContext` — read-only session identity + lifecycle state.
- :class:`ExecutionContext` — **scoped** access to the runtimes: ``invoke_tool``
  runs a tool through the Tool Runtime dispatcher only if the agent was granted
  it (least privilege, doc 18 §7/§16). The dispatcher is encapsulated so the
  grant check cannot be bypassed.

:class:`AgentContext` aggregates the three plus the run's correlation ids.
Storage/Provider/Plugin handles join :class:`ExecutionContext` at composition
(Increment 7); cancellation/streaming arrive with the dispatcher (Increment 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from turkish_code.ajanlar.iptal import CancellationToken
from turkish_code.ajanlar.modeller import AgentChunk, ConversationTurn, SessionState
from turkish_code.araclar.akis import ProgressSink
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.modeller import ToolRequest, ToolResult
from turkish_code.depo.alan import StorageEngine
from turkish_code.hata import AppError, ErrorKind
from turkish_code.saglayicilar.manager import ProviderManager

AGENT_TOOL_OUT_OF_SCOPE_CODE = "agent.tool_out_of_scope"


@runtime_checkable
class AgentEventSink(Protocol):
    """Receives an agent run's streamed output chunks (doc 18 §9)."""

    async def emit(self, chunk: AgentChunk) -> None:
        """Deliver one chunk; ordering follows emission order."""
        ...


class NullEventSink:
    """An :class:`AgentEventSink` that drops every chunk — the default sink."""

    async def emit(self, chunk: AgentChunk) -> None:
        return None


class CollectingEventSink:
    """An :class:`AgentEventSink` that appends chunks in order (tests/simple use)."""

    def __init__(self) -> None:
        self.chunks: list[AgentChunk] = []

    async def emit(self, chunk: AgentChunk) -> None:
        self.chunks.append(chunk)


@dataclass(frozen=True, slots=True)
class ConversationContext:
    """A read-only view of the conversation an agent run belongs to (doc 18 §6)."""

    session_id: str | None
    turns: tuple[ConversationTurn, ...] = ()

    @property
    def turn_count(self) -> int:
        return len(self.turns)

    def last_user_message(self) -> str | None:
        """The most recent user turn's text, or ``None`` if there is none."""
        for turn in reversed(self.turns):
            if turn.role.value == "user":
                return turn.content
        return None


@dataclass(frozen=True, slots=True)
class SessionContext:
    """Read-only session identity + lifecycle state for a run (doc 18 §9)."""

    session_id: str
    agent_id: str
    state: SessionState


class ExecutionContext:
    """Scoped access to the runtimes for one agent run (doc 18 §7/§16).

    The agent invokes tools only through :meth:`invoke_tool`, which enforces the
    agent's ``tool_grants`` before dispatching — a tool outside the grant is
    refused, not run (doc 18 §16). The dispatcher is private so this is the only
    path to the Tool Runtime (plugin tools reach it namespaced too, doc 23 §8).
    :attr:`storage` and :attr:`provider` expose the Storage and Provider runtime
    facades the agent works through — never raw SQLite or a raw provider (doc 18
    §16); either is ``None`` when the run isn't wired for it.
    """

    def __init__(
        self,
        *,
        tool_grants: frozenset[str],
        dispatcher: ToolDispatcher,
        storage: StorageEngine | None = None,
        provider: ProviderManager | None = None,
    ) -> None:
        self._tool_grants = tool_grants
        self._dispatcher = dispatcher
        self._storage = storage
        self._provider = provider

    @property
    def tool_grants(self) -> frozenset[str]:
        return self._tool_grants

    @property
    def storage(self) -> StorageEngine | None:
        """The Storage runtime facade, or ``None`` if unwired (doc 29)."""
        return self._storage

    @property
    def provider(self) -> ProviderManager | None:
        """The Provider runtime facade, or ``None`` if unwired (doc 21)."""
        return self._provider

    def grants_tool(self, tool_name: str) -> bool:
        """Whether the agent may invoke ``tool_name`` (doc 18 §7)."""
        return tool_name in self._tool_grants

    async def invoke_tool(
        self, request: ToolRequest, *, progress: ProgressSink | None = None
    ) -> ToolResult:
        """Run a granted tool through the Tool Runtime (doc 18 §7/§16).

        Raises a typed ``PERMISSION`` :class:`AppError` if the agent was not
        granted ``request.name`` — the scoping is enforced before the call ever
        reaches the dispatcher.
        """
        if request.name not in self._tool_grants:
            raise _out_of_scope(request.name)
        return await self._dispatcher.dispatch(request, progress=progress)


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Ambient context handed to an agent at run time (doc 18 §7).

    Attributes:
        run_id: The run id, echoed from the request for correlation.
        session_id: The session this run belongs to, or ``None`` for a one-off.
        conversation: A read-only view of the conversation, if any.
        execution: Scoped runtime access, if the run may act (else read-only).
        session: Read-only session identity + state, if run within a session.
        cancellation: The cooperative cancellation token for this run; agents
            check :attr:`CancellationToken.is_cancelled` at checkpoints (doc 18 §9).
        sink: The sink streamed :class:`AgentChunk` output is reported to
            (doc 18 §9); defaults to a drop-everything sink.
    """

    run_id: str
    session_id: str | None = None
    conversation: ConversationContext | None = None
    execution: ExecutionContext | None = None
    session: SessionContext | None = None
    cancellation: CancellationToken | None = None
    sink: AgentEventSink = field(default_factory=NullEventSink)

    async def emit(self, delta: str) -> None:
        """Stream an incremental output fragment for this run (doc 18 §9)."""
        await self.sink.emit(AgentChunk(run_id=self.run_id, delta=delta))


def _out_of_scope(tool_name: str) -> AppError:
    return AppError(
        kind=ErrorKind.PERMISSION,
        code=AGENT_TOOL_OUT_OF_SCOPE_CODE,
        message_key=f"hata.{AGENT_TOOL_OUT_OF_SCOPE_CODE}",
        retryable=False,
        detail=f"agent not granted tool {tool_name!r}",
        context={"tool": tool_name},
    )
