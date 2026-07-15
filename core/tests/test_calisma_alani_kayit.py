"""Tests for the workspace registry (doc 25 §4)."""

from __future__ import annotations

import pytest
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
from turkish_code.hata import AppError, ErrorKind


def _session(value: str, *, name: str = "P") -> WorkspaceSession:
    return WorkspaceSession(WorkspaceId(value), WorkspaceMetadata(name=name, root="/p"))


def _wid(value: str) -> WorkspaceId:
    return WorkspaceId(value)


def test_register_then_resolve() -> None:
    registry = WorkspaceRegistry()
    session = _session("w1")
    registry.register(session)
    assert registry.resolve(_wid("w1")) is session
    assert registry.resolve(_wid("w1")).state is WorkspaceState.CREATED


def test_duplicate_registration_is_rejected() -> None:
    registry = WorkspaceRegistry()
    registry.register(_session("w1"))
    with pytest.raises(AppError) as exc_info:
        registry.register(_session("w1"))
    assert exc_info.value.code == WORKSPACE_DUPLICATE_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_resolve_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        WorkspaceRegistry().resolve(_wid("absent"))
    assert exc_info.value.code == WORKSPACE_NOT_FOUND_CODE
    assert exc_info.value.kind is ErrorKind.NOT_FOUND


def test_get_returns_none_for_missing() -> None:
    assert WorkspaceRegistry().get(_wid("absent")) is None


def test_delete_removes_workspace() -> None:
    registry = WorkspaceRegistry()
    registry.register(_session("w1"))
    registry.delete(_wid("w1"))
    assert _wid("w1") not in registry
    with pytest.raises(AppError):
        registry.resolve(_wid("w1"))


def test_delete_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        WorkspaceRegistry().delete(_wid("absent"))
    assert exc_info.value.code == WORKSPACE_NOT_FOUND_CODE


def test_archive_marks_and_excludes_from_active() -> None:
    registry = WorkspaceRegistry()
    registry.register(_session("w1"))
    registry.register(_session("w2"))
    registry.archive(_wid("w1"))
    assert registry.resolve(_wid("w1")).state is WorkspaceState.ARCHIVED
    assert registry.ids() == ["w1", "w2"]  # still stored
    assert registry.active_ids() == ["w2"]  # off the active set


def test_archive_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        WorkspaceRegistry().archive(_wid("absent"))
    assert exc_info.value.code == WORKSPACE_NOT_FOUND_CODE


def test_contains_and_len() -> None:
    registry = WorkspaceRegistry()
    registry.register(_session("w1"))
    assert _wid("w1") in registry
    assert _wid("absent") not in registry
    assert "w1" not in registry  # a bare str is not a WorkspaceId
    assert len(registry) == 1


def test_ids_and_all_are_sorted() -> None:
    registry = WorkspaceRegistry()
    for value in ("z", "a", "m"):
        registry.register(_session(value))
    assert registry.ids() == ["a", "m", "z"]
    assert [w.id.value for w in registry.all()] == ["a", "m", "z"]
