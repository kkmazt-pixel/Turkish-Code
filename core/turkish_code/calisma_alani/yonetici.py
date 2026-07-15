"""Workspace manager — the operational API over the registry (doc 25 §7).

:class:`WorkspaceManager` creates, opens, closes, switches, and deletes
workspaces and tracks the **current** one. Opening binds the workspace's runtime
services via an injected context factory (DIP — the composition wires the real
one) and marks it ``ACTIVE``; closing unbinds and marks it ``INACTIVE``. The
manager never builds a context itself; it delegates that to the factory. The
formal state machine (archive/restore/shutdown, validated) is the lifecycle's
job (Increment 5).
"""

from __future__ import annotations

from collections.abc import Callable

from turkish_code.calisma_alani.baglam import WorkspaceContext
from turkish_code.calisma_alani.kayit import WorkspaceRegistry
from turkish_code.calisma_alani.modeller import (
    WorkspaceConfig,
    WorkspaceId,
    WorkspaceMetadata,
    WorkspaceState,
)
from turkish_code.calisma_alani.oturum import WorkspaceSession

WorkspaceContextFactory = Callable[[WorkspaceSession], WorkspaceContext]
"""Builds a workspace's bound runtime services (the composition provides it)."""


class WorkspaceManager:
    """Manages workspace create/open/close/switch/delete + the current one."""

    def __init__(
        self,
        registry: WorkspaceRegistry,
        context_factory: WorkspaceContextFactory,
    ) -> None:
        self._registry = registry
        self._factory = context_factory
        self._current: WorkspaceId | None = None

    def create(
        self,
        workspace_id: WorkspaceId,
        metadata: WorkspaceMetadata,
        *,
        config: WorkspaceConfig | None = None,
    ) -> WorkspaceSession:
        """Create and register a fresh CREATED workspace; reject a duplicate id."""
        session = WorkspaceSession(workspace_id, metadata, config=config)
        self._registry.register(session)
        return session

    def open(self, workspace_id: WorkspaceId) -> WorkspaceSession:
        """Open a workspace: bind its services, mark ACTIVE, make it current."""
        session = self._registry.resolve(workspace_id)
        if session.context is None:
            session.bind(self._factory(session))
        session.set_state(WorkspaceState.ACTIVE)
        self._current = workspace_id
        return session

    def close(self, workspace_id: WorkspaceId) -> None:
        """Close a workspace: unbind its services, mark INACTIVE (doc 25 §7)."""
        session = self._registry.resolve(workspace_id)
        session.unbind()
        session.set_state(WorkspaceState.INACTIVE)
        if self._current == workspace_id:
            self._current = None

    def switch(self, workspace_id: WorkspaceId) -> WorkspaceSession:
        """Make ``workspace_id`` the current workspace, opening it if needed."""
        return self.open(workspace_id)

    def delete(self, workspace_id: WorkspaceId) -> None:
        """Delete a workspace entirely, clearing it as current if it was."""
        if self._current == workspace_id:
            self._current = None
        self._registry.delete(workspace_id)

    def current(self) -> WorkspaceSession | None:
        """The current workspace, or ``None`` if none is open."""
        return self._registry.get(self._current) if self._current is not None else None

    def current_id(self) -> WorkspaceId | None:
        """The current workspace's id, or ``None``."""
        return self._current
