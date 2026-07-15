"""Tests for the workspace manager — create/open/close/switch/delete (doc 25 §7)."""

from __future__ import annotations

import pytest
from turkish_code.calisma_alani.baglam import WorkspaceContext
from turkish_code.calisma_alani.hata import (
    WORKSPACE_DUPLICATE_CODE,
    WORKSPACE_NOT_FOUND_CODE,
)
from turkish_code.calisma_alani.kayit import WorkspaceRegistry
from turkish_code.calisma_alani.modeller import (
    WorkspaceId,
    WorkspaceMetadata,
    WorkspaceState,
)
from turkish_code.calisma_alani.oturum import WorkspaceSession
from turkish_code.calisma_alani.yonetici import WorkspaceManager
from turkish_code.hata import AppError
from turkish_code.kompozisyon import Container, build_container
from turkish_code.sohbet.kompozisyon import build_conversation_runtime
from turkish_code.yapilandirma.yukleyici import load_settings


def _manager() -> tuple[Container, WorkspaceRegistry, WorkspaceManager]:
    container = build_container(load_settings(environ={}))

    def factory(session: WorkspaceSession) -> WorkspaceContext:
        return WorkspaceContext(
            conversation=build_conversation_runtime(container.agent_runtime),
            agents=container.agent_runtime,
            skills=container.skill_runtime,
            plugins=container.plugin_runtime,
        )

    registry = WorkspaceRegistry()
    return container, registry, WorkspaceManager(registry, factory)


def _wid(value: str) -> WorkspaceId:
    return WorkspaceId(value)


def _meta(name: str = "P") -> WorkspaceMetadata:
    return WorkspaceMetadata(name=name, root="/p")


def test_create_registers_a_created_workspace() -> None:
    _, registry, manager = _manager()
    session = manager.create(_wid("w1"), _meta())
    assert session.state is WorkspaceState.CREATED
    assert _wid("w1") in registry


def test_create_duplicate_is_rejected() -> None:
    _, _, manager = _manager()
    manager.create(_wid("w1"), _meta())
    with pytest.raises(AppError) as exc_info:
        manager.create(_wid("w1"), _meta())
    assert exc_info.value.code == WORKSPACE_DUPLICATE_CODE


def test_open_binds_context_and_activates() -> None:
    _, _, manager = _manager()
    manager.create(_wid("w1"), _meta())
    session = manager.open(_wid("w1"))
    assert session.state is WorkspaceState.ACTIVE
    assert session.context is not None
    assert manager.current_id() == _wid("w1")
    assert manager.current() is session


def test_open_unknown_raises_not_found() -> None:
    _, _, manager = _manager()
    with pytest.raises(AppError) as exc_info:
        manager.open(_wid("absent"))
    assert exc_info.value.code == WORKSPACE_NOT_FOUND_CODE


def test_close_unbinds_and_clears_current() -> None:
    _, registry, manager = _manager()
    manager.create(_wid("w1"), _meta())
    manager.open(_wid("w1"))
    manager.close(_wid("w1"))
    assert manager.current_id() is None
    closed = registry.resolve(_wid("w1"))
    assert closed.state is WorkspaceState.INACTIVE
    assert closed.context is None


def test_switch_changes_current() -> None:
    _, _, manager = _manager()
    manager.create(_wid("a"), _meta())
    manager.create(_wid("b"), _meta())
    manager.open(_wid("a"))
    assert manager.current_id() == _wid("a")
    manager.switch(_wid("b"))
    assert manager.current_id() == _wid("b")
    manager.switch(_wid("a"))  # switch back
    assert manager.current_id() == _wid("a")


def test_delete_removes_and_clears_current() -> None:
    _, registry, manager = _manager()
    manager.create(_wid("w1"), _meta())
    manager.open(_wid("w1"))
    manager.delete(_wid("w1"))
    assert manager.current_id() is None
    assert _wid("w1") not in registry


def test_current_is_none_before_open() -> None:
    _, _, manager = _manager()
    manager.create(_wid("w1"), _meta())
    assert manager.current() is None
    assert manager.current_id() is None


def test_two_workspaces_have_isolated_conversation_runtimes() -> None:
    _, _, manager = _manager()
    manager.create(_wid("a"), _meta())
    manager.create(_wid("b"), _meta())
    a = manager.open(_wid("a"))
    b = manager.open(_wid("b"))
    ctx_a = a.context
    ctx_b = b.context
    assert ctx_a is not None and ctx_b is not None
    assert ctx_a.conversation is not ctx_b.conversation  # isolated per workspace
    assert ctx_a.agents is ctx_b.agents  # shared
