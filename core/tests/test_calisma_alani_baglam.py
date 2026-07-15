"""Tests for the workspace context — bound runtime services (doc 25 §7)."""

from __future__ import annotations

from turkish_code.ajanlar.kompozisyon import AgentRuntime
from turkish_code.calisma_alani.baglam import WorkspaceContext
from turkish_code.calisma_alani.modeller import WorkspaceId, WorkspaceMetadata
from turkish_code.calisma_alani.oturum import WorkspaceSession
from turkish_code.eklentiler.kompozisyon import PluginRuntime
from turkish_code.kompozisyon import Container, build_container
from turkish_code.sohbet.kompozisyon import (
    ConversationRuntime,
    build_conversation_runtime,
)
from turkish_code.sohbet.modeller import ConversationId
from turkish_code.yapilandirma.yukleyici import load_settings
from turkish_code.yetenekler.kompozisyon import SkillRuntime


def _container() -> Container:
    return build_container(load_settings(environ={}))


def _context(container: Container) -> WorkspaceContext:
    # Each workspace gets its own Conversation Runtime (isolation); the agent /
    # skill / plugin runtimes are the shared, container-level facades.
    return WorkspaceContext(
        conversation=build_conversation_runtime(container.agent_runtime),
        agents=container.agent_runtime,
        skills=container.skill_runtime,
        plugins=container.plugin_runtime,
    )


def _session() -> WorkspaceSession:
    return WorkspaceSession(WorkspaceId("w1"), WorkspaceMetadata(name="P", root="/p"))


def test_context_holds_the_bindings() -> None:
    ctx = _context(_container())
    assert isinstance(ctx.conversation, ConversationRuntime)
    assert isinstance(ctx.agents, AgentRuntime)
    assert isinstance(ctx.skills, SkillRuntime)
    assert isinstance(ctx.plugins, PluginRuntime)
    assert ctx.storage is None  # opened async, unbound here


def test_shared_runtimes_are_the_container_facades() -> None:
    container = _container()
    ctx = _context(container)
    assert ctx.agents is container.agent_runtime
    assert ctx.skills is container.skill_runtime
    assert ctx.plugins is container.plugin_runtime


def test_conversation_runtimes_are_isolated_per_workspace() -> None:
    container = _container()
    a = _context(container)
    b = _context(container)
    # different Conversation Runtimes → separate conversation registries
    assert a.conversation is not b.conversation
    assert a.conversation.registry is not b.conversation.registry
    a.conversation.lifecycle.open(ConversationId("c1"), agent_id="x")
    assert "c1" in a.conversation.registry.ids()
    assert "c1" not in b.conversation.registry.ids()  # not leaked across workspaces


def test_session_binds_and_unbinds_context() -> None:
    ctx = _context(_container())
    assert _session().context is None  # a fresh session is not activated

    session = _session()
    session.bind(ctx)
    bound = session.context
    assert bound is ctx
    session.unbind()
    assert session.context is None
