"""Conversation-runtime composition (doc 09 §7) — wire the runtime graph.

Assembles the Conversation Runtime from its parts and connects it to the other
runtimes: a :class:`ConversationRegistry`, a :class:`ConversationEngine` bound to
the **Agent Runtime** (with optional memory injection), a
:class:`ConversationDispatcher`, and a :class:`ConversationLifecycle`.
:class:`RepositoryMemorySource` adapts a ``MemoryRepository`` (doc 11) to the
:class:`MemorySource` port so the engine injects memory without importing Storage.
Pure construction by explicit injection — no import-time side effects, no
singletons (PR-9). No conversations are opened here.
"""

from __future__ import annotations

from collections.abc import Sequence

from turkish_code.ajanlar.kompozisyon import AgentRuntime
from turkish_code.bellek.depo import MemoryRepository
from turkish_code.bellek.katman import MemoryScope
from turkish_code.sohbet.dagitici import ConversationDispatcher
from turkish_code.sohbet.gecmis import HistoryBuilder
from turkish_code.sohbet.motor import ConversationEngine
from turkish_code.sohbet.oturum import ConversationRegistry
from turkish_code.sohbet.protocol import MemorySource
from turkish_code.sohbet.yasam import ConversationLifecycle


class ConversationRuntime:
    """The wired Conversation Runtime — registry, engine, dispatcher, lifecycle."""

    def __init__(
        self,
        *,
        registry: ConversationRegistry,
        engine: ConversationEngine,
        dispatcher: ConversationDispatcher,
        lifecycle: ConversationLifecycle,
    ) -> None:
        self._registry = registry
        self._engine = engine
        self._dispatcher = dispatcher
        self._lifecycle = lifecycle

    @property
    def registry(self) -> ConversationRegistry:
        return self._registry

    @property
    def engine(self) -> ConversationEngine:
        return self._engine

    @property
    def dispatcher(self) -> ConversationDispatcher:
        return self._dispatcher

    @property
    def lifecycle(self) -> ConversationLifecycle:
        return self._lifecycle


class RepositoryMemorySource:
    """A :class:`MemorySource` over a ``MemoryRepository`` (doc 11 §6/§8).

    Recalls candidate memory for the conversation's scope and returns each item's
    body as a snippet. Semantic query matching is a RAG concern (doc 13); this
    substrate recalls by scope/limit — the query is accepted for the port but not
    embedded here.
    """

    def __init__(
        self,
        repository: MemoryRepository,
        *,
        scope: MemoryScope = MemoryScope.WORKSPACE,
    ) -> None:
        self._repository = repository
        self._scope = scope

    async def recall(self, query: str, *, limit: int) -> Sequence[str]:
        items = await self._repository.recall(scope=self._scope, limit=limit)
        return [item.body for item in items]


def build_conversation_runtime(
    agents: AgentRuntime,
    *,
    memory: MemorySource | None = None,
    max_turns: int = 10,
    memory_limit: int = 5,
    system: str | None = None,
) -> ConversationRuntime:
    """Assemble the Conversation Runtime wired to the Agent Runtime (doc 09 §7).

    ``agents`` is the Agent Runtime every turn dispatches through; ``memory`` (a
    :class:`MemorySource`) is injected into each turn's context when provided.
    ``max_turns``/``memory_limit``/``system`` configure the context assembly.
    """
    registry = ConversationRegistry()
    builder = HistoryBuilder(
        max_turns=max_turns, memory_limit=memory_limit, system=system
    )
    engine = ConversationEngine(agents, history_builder=builder, memory=memory)
    return ConversationRuntime(
        registry=registry,
        engine=engine,
        dispatcher=ConversationDispatcher(registry, engine),
        lifecycle=ConversationLifecycle(registry),
    )
