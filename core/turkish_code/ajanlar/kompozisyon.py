"""Agent-runtime composition (doc 18 §10, doc 09 §7) — wire the runtime graph.

Assembles the Agent Runtime from its parts and connects it to the other
runtimes: a :class:`AgentRegistry`, an :class:`AgentDispatcher`, a
:class:`SessionLifecycle`, and the handles an agent works *through* — the Tool
Runtime dispatcher (also carrying plugin tools, doc 23 §8), plus the optional
Storage and Provider facades. :meth:`AgentRuntime.execution_for` builds each
agent a scoped :class:`ExecutionContext` from its ``tool_grants`` (least
privilege, doc 18 §7). Pure construction by explicit injection — no import-time
side effects, no singletons (PR-9). No agent runs here.
"""

from __future__ import annotations

from collections.abc import Iterable

from turkish_code.ajanlar.baglam import ExecutionContext
from turkish_code.ajanlar.dagitici import AgentDispatcher
from turkish_code.ajanlar.kayit import AgentRegistry
from turkish_code.ajanlar.protocol import Agent
from turkish_code.ajanlar.yasam import SessionLifecycle
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.depo.alan import StorageEngine
from turkish_code.saglayicilar.manager import ProviderManager


class AgentRuntime:
    """The wired Agent Runtime (doc 18 §10) — registry, dispatcher, lifecycle."""

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        dispatcher: AgentDispatcher,
        lifecycle: SessionLifecycle,
        tool_dispatcher: ToolDispatcher,
        storage: StorageEngine | None = None,
        provider: ProviderManager | None = None,
    ) -> None:
        self._registry = registry
        self._dispatcher = dispatcher
        self._lifecycle = lifecycle
        self._tool_dispatcher = tool_dispatcher
        self._storage = storage
        self._provider = provider

    @property
    def registry(self) -> AgentRegistry:
        return self._registry

    @property
    def dispatcher(self) -> AgentDispatcher:
        return self._dispatcher

    @property
    def lifecycle(self) -> SessionLifecycle:
        return self._lifecycle

    @property
    def storage(self) -> StorageEngine | None:
        return self._storage

    @property
    def provider(self) -> ProviderManager | None:
        return self._provider

    def execution_for(self, agent: Agent) -> ExecutionContext:
        """A scoped :class:`ExecutionContext` for ``agent`` (doc 18 §7).

        Wires the shared Tool Runtime (with plugin tools) + Storage/Provider
        facades, scoped to the agent's ``tool_grants`` — the agent cannot invoke
        an ungranted tool (doc 18 §16).
        """
        return ExecutionContext(
            tool_grants=agent.metadata.tool_grants,
            dispatcher=self._tool_dispatcher,
            storage=self._storage,
            provider=self._provider,
        )


def build_agent_runtime(
    tool_dispatcher: ToolDispatcher,
    *,
    agents: Iterable[Agent] = (),
    default_agent_id: str | None = None,
    storage: StorageEngine | None = None,
    provider: ProviderManager | None = None,
) -> AgentRuntime:
    """Assemble the Agent Runtime wired to the other runtimes (doc 18 §10, §7).

    ``agents`` are registered fail-safe (duplicate ids rejected);
    ``default_agent_id`` marks the routing fallback (doc 18 §10). ``tool_dispatcher``
    is the Tool Runtime seam every agent acts through; ``storage``/``provider`` are
    the optional Storage/Provider facades exposed on each execution context.
    """
    registry = AgentRegistry()
    for agent in agents:
        registry.register(
            agent,
            default=default_agent_id is not None
            and agent.metadata.id == default_agent_id,
        )
    return AgentRuntime(
        registry=registry,
        dispatcher=AgentDispatcher(registry),
        lifecycle=SessionLifecycle(),
        tool_dispatcher=tool_dispatcher,
        storage=storage,
        provider=provider,
    )
