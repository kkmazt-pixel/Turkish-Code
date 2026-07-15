"""Workspace context — a workspace's bound runtime services (doc 25 §7).

:class:`WorkspaceContext` binds one workspace to the runtimes it works through
(PR-9, never touching subsystems directly):

- ``conversation`` — a **per-workspace** :class:`ConversationRuntime`, so
  conversations are isolated between workspaces (doc 25 §7).
- ``storage`` — the workspace's **per-workspace** ``WorkspaceStore`` (isolated
  DB/blobs/journal, doc 25 §4); ``None`` until the async store is opened.
- ``agents`` / ``skills`` / ``plugins`` — the **shared** runtime facades every
  workspace draws from.

The session binds a context on activation and unbinds it on deactivation.
"""

from __future__ import annotations

from dataclasses import dataclass

from turkish_code.ajanlar.kompozisyon import AgentRuntime
from turkish_code.depo.alan import WorkspaceStore
from turkish_code.eklentiler.kompozisyon import PluginRuntime
from turkish_code.sohbet.kompozisyon import ConversationRuntime
from turkish_code.yetenekler.kompozisyon import SkillRuntime


@dataclass(frozen=True, slots=True)
class WorkspaceContext:
    """The bound runtime services for one workspace (doc 25 §7).

    Attributes:
        conversation: The workspace's isolated Conversation Runtime.
        agents: The shared Agent Runtime.
        skills: The shared Skill Runtime.
        plugins: The shared Plugin Runtime.
        storage: The workspace's isolated Storage store, or ``None`` if unopened.
    """

    conversation: ConversationRuntime
    agents: AgentRuntime
    skills: SkillRuntime
    plugins: PluginRuntime
    storage: WorkspaceStore | None = None
