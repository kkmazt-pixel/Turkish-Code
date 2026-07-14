"""Skill execution context (doc 19 §9) — the ambient "how" of one invocation.

A skill works only through its context, never touching subsystems directly (PR-9,
doc 19 §8/§15):

- :class:`CancellationToken` — the cooperative cancel flag for this invocation.
- :class:`SkillExecutionContext` — **scoped** runtime access: ``invoke_tool`` runs
  a tool through the Tool Runtime only if the skill's ``allowed_tools`` permit it
  (least privilege, doc 19 §4/§15); plus the Storage, Agent, and Provider runtime
  *facades* the skill may use — never raw SQLite or a raw provider (doc 19 §8).

:class:`SkillContext` aggregates them with the invocation's ids. The streaming
sink joins in Increment 4; the composition wires the facades in Increment 6.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from turkish_code.ajanlar.kompozisyon import AgentRuntime
from turkish_code.araclar.akis import ProgressSink
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.modeller import ToolRequest, ToolResult
from turkish_code.depo.alan import StorageEngine
from turkish_code.saglayicilar.manager import ProviderManager
from turkish_code.yetenekler.hata import tool_out_of_scope
from turkish_code.yetenekler.modeller import SkillChunk


@runtime_checkable
class SkillEventSink(Protocol):
    """Receives a skill invocation's streamed output chunks (doc 19 §9)."""

    async def emit(self, chunk: SkillChunk) -> None:
        """Deliver one chunk; ordering follows emission order."""
        ...


class NullEventSink:
    """A :class:`SkillEventSink` that drops every chunk — the default sink."""

    async def emit(self, chunk: SkillChunk) -> None:
        return None


class CollectingEventSink:
    """A :class:`SkillEventSink` that appends chunks in order (tests/simple use)."""

    def __init__(self) -> None:
        self.chunks: list[SkillChunk] = []

    async def emit(self, chunk: SkillChunk) -> None:
        self.chunks.append(chunk)


class CancellationToken:
    """A cooperative cancellation flag for one skill invocation (doc 19 §14)."""

    def __init__(self) -> None:
        self._event = asyncio.Event()

    def cancel(self) -> None:
        """Mark this invocation cancelled. Idempotent."""
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        """Suspend until cancelled — the dispatcher races this against the run."""
        await self._event.wait()


class SkillExecutionContext:
    """Scoped access to the runtimes for one skill invocation (doc 19 §8/§15).

    The skill invokes tools only through :meth:`invoke_tool`, which enforces its
    ``allowed_tools`` before dispatching — a tool outside the set is refused, not
    run (doc 19 §15). The dispatcher is private so this is the only path to the
    Tool Runtime. :attr:`storage`, :attr:`agents`, and :attr:`provider` expose the
    respective runtime facades the skill works through (never raw subsystems);
    each is ``None`` when the invocation isn't wired for it.
    """

    def __init__(
        self,
        *,
        allowed_tools: frozenset[str],
        tool_dispatcher: ToolDispatcher,
        storage: StorageEngine | None = None,
        agents: AgentRuntime | None = None,
        provider: ProviderManager | None = None,
    ) -> None:
        self._allowed_tools = allowed_tools
        self._tool_dispatcher = tool_dispatcher
        self._storage = storage
        self._agents = agents
        self._provider = provider

    @property
    def allowed_tools(self) -> frozenset[str]:
        return self._allowed_tools

    @property
    def storage(self) -> StorageEngine | None:
        """The Storage runtime facade, or ``None`` if unwired (doc 29)."""
        return self._storage

    @property
    def agents(self) -> AgentRuntime | None:
        """The Agent runtime facade, or ``None`` if unwired (doc 18)."""
        return self._agents

    @property
    def provider(self) -> ProviderManager | None:
        """The Provider runtime facade, or ``None`` if unwired (doc 21)."""
        return self._provider

    def allows_tool(self, tool_name: str) -> bool:
        """Whether the skill may invoke ``tool_name`` (doc 19 §15)."""
        return tool_name in self._allowed_tools

    async def invoke_tool(
        self, request: ToolRequest, *, progress: ProgressSink | None = None
    ) -> ToolResult:
        """Run an allowed tool through the Tool Runtime (doc 19 §8/§15).

        Raises a typed ``PERMISSION`` :class:`AppError` if the skill's
        ``allowed_tools`` don't include ``request.name`` — enforced before the
        call ever reaches the dispatcher.
        """
        if request.name not in self._allowed_tools:
            raise tool_out_of_scope(request.name)
        return await self._tool_dispatcher.dispatch(request, progress=progress)


@dataclass(frozen=True, slots=True)
class SkillContext:
    """Ambient context handed to a skill at invocation (doc 19 §9).

    Attributes:
        invocation_id: The invocation id, echoed from the request for correlation.
        run_id: The agent run this invocation belongs to, or ``None``.
        cancellation: The cooperative cancellation token for this invocation;
            skills check :attr:`CancellationToken.is_cancelled` at checkpoints.
        execution: Scoped runtime access, if the invocation may act.
        sink: The sink streamed :class:`SkillChunk` output is reported to
            (doc 19 §9); defaults to a drop-everything sink.
    """

    invocation_id: str
    run_id: str | None = None
    cancellation: CancellationToken | None = None
    execution: SkillExecutionContext | None = None
    sink: SkillEventSink = field(default_factory=NullEventSink)

    async def emit(self, delta: str) -> None:
        """Stream an incremental output fragment for this invocation (doc 19 §9)."""
        await self.sink.emit(SkillChunk(invocation_id=self.invocation_id, delta=delta))
