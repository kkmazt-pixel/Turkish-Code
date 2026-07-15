"""Tests for workspace models + the Workspace Protocol (doc 25 §4/§7)."""

from __future__ import annotations

import pytest
from turkish_code.calisma_alani.modeller import (
    WorkspaceId,
    WorkspaceMetadata,
    WorkspaceState,
)
from turkish_code.calisma_alani.protocol import Workspace


def test_state_wire_values() -> None:
    assert WorkspaceState.CREATED.value == "created"
    assert WorkspaceState.ACTIVE.value == "active"
    assert WorkspaceState.ARCHIVED.value == "archived"
    assert WorkspaceState.SHUTDOWN.value == "shutdown"


def test_workspace_id_rejects_empty() -> None:
    with pytest.raises(ValueError, match="value must be non-empty"):
        WorkspaceId("")


def test_workspace_id_is_immutable() -> None:
    wid = WorkspaceId("w1")
    with pytest.raises(AttributeError):
        wid.value = "w2"  # type: ignore[misc]


def test_metadata_holds_identity() -> None:
    meta = WorkspaceMetadata(name="Projem", root="/home/ada/projem", description="not")
    assert meta.name == "Projem"
    assert meta.root == "/home/ada/projem"
    assert meta.description == "not"


def test_metadata_description_defaults_empty() -> None:
    assert WorkspaceMetadata(name="P", root="/p").description == ""


def test_metadata_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="name must be non-empty"):
        WorkspaceMetadata(name="", root="/p")


def test_metadata_rejects_empty_root() -> None:
    with pytest.raises(ValueError, match="root must be non-empty"):
        WorkspaceMetadata(name="P", root="")


class _StubWorkspace:
    """A minimal structural :class:`Workspace` — proves the Protocol works."""

    def __init__(self) -> None:
        self._id = WorkspaceId("w1")
        self._meta = WorkspaceMetadata(name="P", root="/p")
        self._state = WorkspaceState.CREATED

    @property
    def id(self) -> WorkspaceId:
        return self._id

    @property
    def metadata(self) -> WorkspaceMetadata:
        return self._meta

    @property
    def state(self) -> WorkspaceState:
        return self._state


def test_concrete_workspace_satisfies_protocol() -> None:
    assert isinstance(_StubWorkspace(), Workspace)


def test_plain_object_is_not_a_workspace() -> None:
    assert not isinstance(object(), Workspace)
