"""Tests for workspace-runtime composition + container wiring (doc 25 §7)."""

from __future__ import annotations

from turkish_code.calisma_alani.kompozisyon import (
    WorkspaceRuntime,
    build_workspace_runtime,
)
from turkish_code.calisma_alani.modeller import (
    WorkspaceId,
    WorkspaceMetadata,
    WorkspaceState,
)
from turkish_code.kompozisyon import Container, build_container
from turkish_code.yapilandirma.yukleyici import load_settings


def _container() -> Container:
    return build_container(load_settings(environ={}))


def _runtime(container: Container) -> WorkspaceRuntime:
    return build_workspace_runtime(
        agents=container.agent_runtime,
        skills=container.skill_runtime,
        plugins=container.plugin_runtime,
    )


def _wid(value: str) -> WorkspaceId:
    return WorkspaceId(value)


def _meta() -> WorkspaceMetadata:
    return WorkspaceMetadata(name="P", root="/p")


def test_build_returns_wired_graph() -> None:
    runtime = _runtime(_container())
    assert isinstance(runtime, WorkspaceRuntime)
    assert len(runtime.registry) == 0


def test_create_open_binds_shared_and_isolated_runtimes() -> None:
    container = _container()
    runtime = _runtime(container)
    runtime.manager.create(_wid("w1"), _meta())
    session = runtime.manager.open(_wid("w1"))
    assert session.state is WorkspaceState.ACTIVE
    ctx = session.context
    assert ctx is not None
    # shared runtimes come from the container; conversation is per-workspace
    assert ctx.agents is container.agent_runtime
    assert ctx.skills is container.skill_runtime
    assert ctx.plugins is container.plugin_runtime
    assert ctx.storage is None


def test_two_workspaces_have_isolated_conversations() -> None:
    runtime = _runtime(_container())
    runtime.manager.create(_wid("a"), _meta())
    runtime.manager.create(_wid("b"), _meta())
    a = runtime.manager.open(_wid("a"))
    b = runtime.manager.open(_wid("b"))
    ctx_a = a.context
    ctx_b = b.context
    assert ctx_a is not None and ctx_b is not None
    assert ctx_a.conversation is not ctx_b.conversation


def test_manager_and_lifecycle_share_the_registry() -> None:
    runtime = _runtime(_container())
    runtime.manager.create(_wid("w1"), _meta())
    # the lifecycle sees the manager-created workspace (same registry)
    runtime.lifecycle.activate(_wid("w1"))
    assert runtime.registry.resolve(_wid("w1")).state is WorkspaceState.ACTIVE


def test_container_exposes_workspace_runtime() -> None:
    container = _container()
    assert isinstance(container.workspace_runtime, WorkspaceRuntime)
    assert len(container.workspace_runtime.registry) == 0
