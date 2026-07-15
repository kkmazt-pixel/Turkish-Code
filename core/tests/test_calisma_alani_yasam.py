"""Tests for the workspace lifecycle — validated state machine (doc 25 §7)."""

from __future__ import annotations

import pytest
from turkish_code.calisma_alani.hata import (
    WORKSPACE_INVALID_TRANSITION_CODE,
    WORKSPACE_NOT_FOUND_CODE,
)
from turkish_code.calisma_alani.kayit import WorkspaceRegistry
from turkish_code.calisma_alani.modeller import (
    WorkspaceId,
    WorkspaceMetadata,
    WorkspaceState,
)
from turkish_code.calisma_alani.oturum import WorkspaceSession
from turkish_code.calisma_alani.yasam import WorkspaceLifecycle
from turkish_code.hata import AppError, ErrorKind


def _setup() -> tuple[WorkspaceRegistry, WorkspaceLifecycle]:
    registry = WorkspaceRegistry()
    registry.register(
        WorkspaceSession(WorkspaceId("w1"), WorkspaceMetadata(name="P", root="/p"))
    )
    return registry, WorkspaceLifecycle(registry)


def _wid() -> WorkspaceId:
    return WorkspaceId("w1")


def _state(registry: WorkspaceRegistry) -> WorkspaceState:
    return registry.resolve(_wid()).state


def test_initialize_confirms_created() -> None:
    registry, lifecycle = _setup()
    lifecycle.initialize(_wid())  # already CREATED → idempotent
    assert _state(registry) is WorkspaceState.CREATED


def test_activate_and_deactivate() -> None:
    registry, lifecycle = _setup()
    lifecycle.activate(_wid())
    assert _state(registry) is WorkspaceState.ACTIVE
    lifecycle.deactivate(_wid())
    assert _state(registry) is WorkspaceState.INACTIVE
    lifecycle.activate(_wid())  # INACTIVE → ACTIVE again
    assert _state(registry) is WorkspaceState.ACTIVE


def test_archive_from_inactive_then_restore() -> None:
    registry, lifecycle = _setup()
    lifecycle.activate(_wid())
    lifecycle.deactivate(_wid())
    lifecycle.archive(_wid())
    assert _state(registry) is WorkspaceState.ARCHIVED
    lifecycle.restore(_wid())
    assert _state(registry) is WorkspaceState.INACTIVE


def test_archive_directly_from_created() -> None:
    registry, lifecycle = _setup()
    lifecycle.archive(_wid())
    assert _state(registry) is WorkspaceState.ARCHIVED


def test_cannot_archive_active_workspace() -> None:
    registry, lifecycle = _setup()
    lifecycle.activate(_wid())
    with pytest.raises(AppError) as exc_info:
        lifecycle.archive(_wid())  # must deactivate first
    assert exc_info.value.code == WORKSPACE_INVALID_TRANSITION_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_illegal_transitions_are_rejected() -> None:
    registry, lifecycle = _setup()  # CREATED
    with pytest.raises(AppError) as exc_info:
        lifecycle.deactivate(_wid())  # only ACTIVE can deactivate
    assert exc_info.value.code == WORKSPACE_INVALID_TRANSITION_CODE
    with pytest.raises(AppError):
        lifecycle.restore(_wid())  # only ARCHIVED can restore


def test_initialize_illegal_after_activation() -> None:
    _, lifecycle = _setup()
    lifecycle.activate(_wid())
    with pytest.raises(AppError) as exc_info:
        lifecycle.initialize(_wid())  # only CREATED can initialize
    assert exc_info.value.code == WORKSPACE_INVALID_TRANSITION_CODE


def test_shutdown_is_terminal_and_idempotent() -> None:
    registry, lifecycle = _setup()
    lifecycle.activate(_wid())
    lifecycle.shutdown(_wid())
    assert _state(registry) is WorkspaceState.SHUTDOWN
    lifecycle.shutdown(_wid())  # idempotent
    assert _state(registry) is WorkspaceState.SHUTDOWN
    for op in (
        lifecycle.activate,
        lifecycle.deactivate,
        lifecycle.archive,
        lifecycle.restore,
    ):
        with pytest.raises(AppError):
            op(_wid())


def test_unknown_workspace_raises_not_found() -> None:
    _, lifecycle = _setup()
    with pytest.raises(AppError) as exc_info:
        lifecycle.activate(WorkspaceId("absent"))
    assert exc_info.value.code == WORKSPACE_NOT_FOUND_CODE


def test_full_lifecycle_flow() -> None:
    registry, lifecycle = _setup()
    lifecycle.initialize(_wid())
    lifecycle.activate(_wid())
    lifecycle.deactivate(_wid())
    lifecycle.archive(_wid())
    lifecycle.restore(_wid())
    lifecycle.shutdown(_wid())
    assert _state(registry) is WorkspaceState.SHUTDOWN
