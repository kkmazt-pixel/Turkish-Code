"""Workspace lifecycle — the validated state machine (doc 25 §7).

:class:`WorkspaceLifecycle` drives a workspace's :class:`WorkspaceState` over the
registry with validated transitions: initialize → activate ⇄ deactivate →
archive → restore, and shutdown at any time. Illegal transitions are rejected
(fail-safe); ``SHUTDOWN`` is terminal. This is the formal state authority
(archive/restore/shutdown especially); the manager (Increment 4) is the
operational API that binds context and tracks the current workspace.
"""

from __future__ import annotations

from collections.abc import Iterable

from turkish_code.calisma_alani.hata import invalid_transition
from turkish_code.calisma_alani.kayit import WorkspaceRegistry
from turkish_code.calisma_alani.modeller import WorkspaceId, WorkspaceState


class WorkspaceLifecycle:
    """Drives workspace state with validated transitions (doc 25 §7)."""

    def __init__(self, registry: WorkspaceRegistry) -> None:
        self._registry = registry

    def initialize(self, workspace_id: WorkspaceId) -> None:
        """Confirm a freshly created workspace is initialized: CREATED (idempotent)."""
        self._transition(
            workspace_id, (WorkspaceState.CREATED,), WorkspaceState.CREATED
        )

    def activate(self, workspace_id: WorkspaceId) -> None:
        """Activate a workspace: CREATED/INACTIVE → ACTIVE."""
        self._transition(
            workspace_id,
            (WorkspaceState.CREATED, WorkspaceState.INACTIVE),
            WorkspaceState.ACTIVE,
        )

    def deactivate(self, workspace_id: WorkspaceId) -> None:
        """Deactivate an active workspace: ACTIVE → INACTIVE."""
        self._transition(
            workspace_id, (WorkspaceState.ACTIVE,), WorkspaceState.INACTIVE
        )

    def archive(self, workspace_id: WorkspaceId) -> None:
        """Archive an inactive workspace: CREATED/INACTIVE → ARCHIVED."""
        self._transition(
            workspace_id,
            (WorkspaceState.CREATED, WorkspaceState.INACTIVE),
            WorkspaceState.ARCHIVED,
        )

    def restore(self, workspace_id: WorkspaceId) -> None:
        """Restore an archived workspace: ARCHIVED → INACTIVE."""
        self._transition(
            workspace_id, (WorkspaceState.ARCHIVED,), WorkspaceState.INACTIVE
        )

    def shutdown(self, workspace_id: WorkspaceId) -> None:
        """Terminally shut a workspace down; idempotent (doc 25 §7)."""
        session = self._registry.resolve(workspace_id)
        if session.state is not WorkspaceState.SHUTDOWN:
            session.set_state(WorkspaceState.SHUTDOWN)

    def _transition(
        self,
        workspace_id: WorkspaceId,
        allowed: Iterable[WorkspaceState],
        target: WorkspaceState,
    ) -> None:
        session = self._registry.resolve(workspace_id)
        if session.state not in allowed:
            raise invalid_transition(workspace_id, session.state)
        session.set_state(target)
