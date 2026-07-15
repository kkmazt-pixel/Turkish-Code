"""Workspace-runtime composition (doc 09 §7) — wire the runtime graph.

Assembles the Workspace Runtime and connects it to the other runtimes through a
**context factory**: for each opened workspace it builds an isolated
:class:`ConversationRuntime` and binds the shared Agent/Skill/Plugin facades
(doc 25 §7). :class:`WorkspaceRuntime` bundles the registry, manager, and
lifecycle. Pure construction by explicit injection — no import-time side effects,
no singletons (PR-9). No workspaces are created here. Per-workspace Storage is
opened asynchronously (a seam); the factory binds ``None`` for now.
"""

from __future__ import annotations

from turkish_code.ajanlar.kompozisyon import AgentRuntime
from turkish_code.calisma_alani.baglam import WorkspaceContext
from turkish_code.calisma_alani.kayit import WorkspaceRegistry
from turkish_code.calisma_alani.oturum import WorkspaceSession
from turkish_code.calisma_alani.yasam import WorkspaceLifecycle
from turkish_code.calisma_alani.yonetici import WorkspaceManager
from turkish_code.eklentiler.kompozisyon import PluginRuntime
from turkish_code.sohbet.kompozisyon import build_conversation_runtime
from turkish_code.yetenekler.kompozisyon import SkillRuntime


class WorkspaceRuntime:
    """The wired Workspace Runtime — registry, manager, lifecycle (doc 25 §7)."""

    def __init__(
        self,
        *,
        registry: WorkspaceRegistry,
        manager: WorkspaceManager,
        lifecycle: WorkspaceLifecycle,
    ) -> None:
        self._registry = registry
        self._manager = manager
        self._lifecycle = lifecycle

    @property
    def registry(self) -> WorkspaceRegistry:
        return self._registry

    @property
    def manager(self) -> WorkspaceManager:
        return self._manager

    @property
    def lifecycle(self) -> WorkspaceLifecycle:
        return self._lifecycle


def build_workspace_runtime(
    *,
    agents: AgentRuntime,
    skills: SkillRuntime,
    plugins: PluginRuntime,
) -> WorkspaceRuntime:
    """Assemble the Workspace Runtime wired to the shared runtimes (doc 25 §7).

    Each opened workspace gets an isolated Conversation Runtime (conversation
    isolation) plus the shared Agent/Skill/Plugin facades. Per-workspace Storage
    is opened asynchronously and bound later — the factory binds ``None`` here.
    """
    registry = WorkspaceRegistry()

    def context_factory(session: WorkspaceSession) -> WorkspaceContext:
        return WorkspaceContext(
            conversation=build_conversation_runtime(agents),
            agents=agents,
            skills=skills,
            plugins=plugins,
        )

    return WorkspaceRuntime(
        registry=registry,
        manager=WorkspaceManager(registry, context_factory),
        lifecycle=WorkspaceLifecycle(registry),
    )
