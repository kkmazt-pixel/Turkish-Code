"""Workspace-runtime failures as typed :class:`AppError` values (doc 25, doc 38).

The Workspace Runtime never lets a raw exception escape: a duplicate id is a
``CONFLICT``, an unknown workspace is ``NOT_FOUND``, and — as later increments add
them — an illegal lifecycle transition or a missing current workspace is a
``CONFLICT``/``NOT_FOUND`` (doc 38 §4/§7). Codes are stable machine strings.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from turkish_code.calisma_alani.modeller import WorkspaceId, WorkspaceState
from turkish_code.hata import AppError, ErrorKind

WORKSPACE_NOT_FOUND_CODE = "workspace.not_found"
WORKSPACE_DUPLICATE_CODE = "workspace.duplicate"
WORKSPACE_INVALID_TRANSITION_CODE = "workspace.invalid_transition"


def invalid_transition(workspace_id: WorkspaceId, state: WorkspaceState) -> AppError:
    """An illegal lifecycle transition for ``workspace_id`` (doc 25 §7)."""
    return workspace_error(
        ErrorKind.CONFLICT,
        WORKSPACE_INVALID_TRANSITION_CODE,
        detail=(
            f"illegal transition for {workspace_id.value!r} "
            f"in state {state.value!r}"
        ),
        context={"workspace": workspace_id.value},
    )


def workspace_not_found(workspace_id: WorkspaceId) -> AppError:
    """No workspace is registered under ``workspace_id`` (doc 25 §4)."""
    return workspace_error(
        ErrorKind.NOT_FOUND,
        WORKSPACE_NOT_FOUND_CODE,
        detail=f"no workspace {workspace_id.value!r}",
        context={"workspace": workspace_id.value},
    )


def duplicate_workspace(workspace_id: WorkspaceId) -> AppError:
    """A workspace is already registered under ``workspace_id`` (doc 25 §4)."""
    return workspace_error(
        ErrorKind.CONFLICT,
        WORKSPACE_DUPLICATE_CODE,
        detail=f"a workspace already exists as {workspace_id.value!r}",
        context={"workspace": workspace_id.value},
    )


def workspace_error(
    kind: ErrorKind,
    code: str,
    *,
    detail: str,
    retryable: bool = False,
    context: Mapping[str, Any] | None = None,
) -> AppError:
    """Build a typed workspace :class:`AppError` (shared by the runtime modules)."""
    return AppError(
        kind=kind,
        code=code,
        message_key=f"hata.{code}",
        retryable=retryable,
        detail=detail,
        context=context,
    )
