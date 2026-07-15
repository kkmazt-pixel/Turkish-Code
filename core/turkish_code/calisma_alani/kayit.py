"""Workspace registry (doc 25 §4) — the store of workspaces.

Holds every registered :class:`WorkspaceSession` keyed by its id. Registration is
**fail-safe**: a duplicate id is rejected (doc 25 §4). The registry archives
(excluding a workspace from the active set) and lists; the manager creates/opens
and the lifecycle drives the other transitions (Increments 4/5). It owns storage
and lookup only.
"""

from __future__ import annotations

from turkish_code.calisma_alani.hata import (
    duplicate_workspace,
    workspace_not_found,
)
from turkish_code.calisma_alani.modeller import WorkspaceId, WorkspaceState
from turkish_code.calisma_alani.oturum import WorkspaceSession


class WorkspaceRegistry:
    """An in-memory id→:class:`WorkspaceSession` store (doc 25 §4)."""

    def __init__(self) -> None:
        self._workspaces: dict[str, WorkspaceSession] = {}

    def register(self, workspace: WorkspaceSession) -> None:
        """Add ``workspace``; reject a duplicate id (fail-safe, doc 25 §4)."""
        key = workspace.id.value
        if key in self._workspaces:
            raise duplicate_workspace(workspace.id)
        self._workspaces[key] = workspace

    def get(self, workspace_id: WorkspaceId) -> WorkspaceSession | None:
        """The workspace, or ``None`` if absent."""
        return self._workspaces.get(workspace_id.value)

    def resolve(self, workspace_id: WorkspaceId) -> WorkspaceSession:
        """The workspace, or raise ``workspace.not_found``."""
        workspace = self._workspaces.get(workspace_id.value)
        if workspace is None:
            raise workspace_not_found(workspace_id)
        return workspace

    def delete(self, workspace_id: WorkspaceId) -> None:
        """Remove the workspace entirely, or raise ``workspace.not_found``."""
        if workspace_id.value not in self._workspaces:
            raise workspace_not_found(workspace_id)
        del self._workspaces[workspace_id.value]

    def archive(self, workspace_id: WorkspaceId) -> None:
        """Mark the workspace ARCHIVED (retained, off the active set)."""
        self.resolve(workspace_id).set_state(WorkspaceState.ARCHIVED)

    def __contains__(self, workspace_id: object) -> bool:
        return (
            isinstance(workspace_id, WorkspaceId)
            and workspace_id.value in self._workspaces
        )

    def __len__(self) -> int:
        return len(self._workspaces)

    def ids(self) -> list[str]:
        """All workspace ids, sorted."""
        return sorted(self._workspaces)

    def active_ids(self) -> list[str]:
        """Ids of non-archived workspaces, sorted."""
        return sorted(
            key
            for key, workspace in self._workspaces.items()
            if not workspace.is_archived
        )

    def all(self) -> list[WorkspaceSession]:
        """Every registered workspace, id-sorted."""
        return [self._workspaces[key] for key in sorted(self._workspaces)]
