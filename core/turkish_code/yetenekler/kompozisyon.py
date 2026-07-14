"""Skill-runtime composition (doc 19 §7, doc 09 §7) — wire the runtime graph.

Assembles the Skill Runtime from its parts and connects it to the other
runtimes: a :class:`SkillRegistry`, a :class:`SkillDispatcher`, a
:class:`SkillLifecycle`, and the handles a skill works *through* — the Tool
Runtime dispatcher (also carrying plugin tools, doc 23 §8), plus the optional
Storage, Agent, and Provider facades. :meth:`SkillRuntime.execution_for` builds
each skill a scoped :class:`SkillExecutionContext` from its ``allowed_tools``
(least privilege, doc 19 §15). Pure construction by explicit injection — no
import-time side effects, no singletons (PR-9). Provided skills are loaded and
enabled so they are invocable; nothing runs here.
"""

from __future__ import annotations

from collections.abc import Iterable

from turkish_code.ajanlar.kompozisyon import AgentRuntime
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.depo.alan import StorageEngine
from turkish_code.saglayicilar.manager import ProviderManager
from turkish_code.yetenekler.baglam import SkillExecutionContext
from turkish_code.yetenekler.dagitici import SkillDispatcher
from turkish_code.yetenekler.kayit import SkillRegistry
from turkish_code.yetenekler.protocol import Skill
from turkish_code.yetenekler.yasam import SkillLifecycle


class SkillRuntime:
    """The wired Skill Runtime (doc 19 §7) — registry, dispatcher, lifecycle."""

    def __init__(
        self,
        *,
        registry: SkillRegistry,
        dispatcher: SkillDispatcher,
        lifecycle: SkillLifecycle,
        tool_dispatcher: ToolDispatcher,
        storage: StorageEngine | None = None,
        agents: AgentRuntime | None = None,
        provider: ProviderManager | None = None,
    ) -> None:
        self._registry = registry
        self._dispatcher = dispatcher
        self._lifecycle = lifecycle
        self._tool_dispatcher = tool_dispatcher
        self._storage = storage
        self._agents = agents
        self._provider = provider

    @property
    def registry(self) -> SkillRegistry:
        return self._registry

    @property
    def dispatcher(self) -> SkillDispatcher:
        return self._dispatcher

    @property
    def lifecycle(self) -> SkillLifecycle:
        return self._lifecycle

    @property
    def storage(self) -> StorageEngine | None:
        return self._storage

    @property
    def agents(self) -> AgentRuntime | None:
        return self._agents

    @property
    def provider(self) -> ProviderManager | None:
        return self._provider

    def execution_for(self, skill: Skill) -> SkillExecutionContext:
        """A scoped :class:`SkillExecutionContext` for ``skill`` (doc 19 §15).

        Wires the shared Tool Runtime (with plugin tools) + Storage/Agent/Provider
        facades, scoped to the skill's ``allowed_tools`` — the skill cannot invoke
        a tool outside that set (doc 19 §15).
        """
        return SkillExecutionContext(
            allowed_tools=skill.metadata.allowed_tools,
            tool_dispatcher=self._tool_dispatcher,
            storage=self._storage,
            agents=self._agents,
            provider=self._provider,
        )


def build_skill_runtime(
    tool_dispatcher: ToolDispatcher,
    *,
    skills: Iterable[Skill] = (),
    storage: StorageEngine | None = None,
    agents: AgentRuntime | None = None,
    provider: ProviderManager | None = None,
) -> SkillRuntime:
    """Assemble the Skill Runtime wired to the other runtimes (doc 19 §7, §15).

    Provided ``skills`` are loaded and enabled (fail-safe, duplicate ids
    rejected) so they are immediately invocable. ``tool_dispatcher`` is the Tool
    Runtime seam every skill acts through; ``storage``/``agents``/``provider`` are
    the optional facades exposed on each execution context.
    """
    registry = SkillRegistry()
    lifecycle = SkillLifecycle(registry)
    for skill in skills:
        lifecycle.load(skill)
        lifecycle.enable(skill.metadata.id)
    return SkillRuntime(
        registry=registry,
        dispatcher=SkillDispatcher(registry),
        lifecycle=lifecycle,
        tool_dispatcher=tool_dispatcher,
        storage=storage,
        agents=agents,
        provider=provider,
    )
