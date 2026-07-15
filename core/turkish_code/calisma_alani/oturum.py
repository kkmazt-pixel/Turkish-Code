"""The concrete workspace instance (doc 25 §4/§7).

:class:`WorkspaceSession` is a live workspace: its id, descriptive metadata, and
mutable lifecycle :class:`WorkspaceState` (starting ``CREATED``). It satisfies the
:class:`Workspace` Protocol. State transitions are raw here (``set_state``); the
lifecycle validates them (Increment 5). The bound runtime services join it via
its context (Increment 3).
"""

from __future__ import annotations

from turkish_code.calisma_alani.baglam import WorkspaceContext
from turkish_code.calisma_alani.modeller import (
    WorkspaceConfig,
    WorkspaceId,
    WorkspaceMetadata,
    WorkspaceState,
)


class WorkspaceSession:
    """A live workspace — id, metadata, config, state, and bound services (doc 25)."""

    def __init__(
        self,
        workspace_id: WorkspaceId,
        metadata: WorkspaceMetadata,
        *,
        config: WorkspaceConfig | None = None,
    ) -> None:
        self._id = workspace_id
        self._metadata = metadata
        self._config = config if config is not None else WorkspaceConfig()
        self._state = WorkspaceState.CREATED
        self._context: WorkspaceContext | None = None

    @property
    def id(self) -> WorkspaceId:
        return self._id

    @property
    def metadata(self) -> WorkspaceMetadata:
        return self._metadata

    @property
    def config(self) -> WorkspaceConfig:
        """The workspace's configuration (doc 25 §4)."""
        return self._config

    @property
    def state(self) -> WorkspaceState:
        return self._state

    @property
    def is_archived(self) -> bool:
        return self._state is WorkspaceState.ARCHIVED

    @property
    def context(self) -> WorkspaceContext | None:
        """The bound runtime services, or ``None`` when not activated (doc 25 §7)."""
        return self._context

    def set_state(self, target: WorkspaceState) -> None:
        """Set the lifecycle state (raw). The lifecycle validates transitions."""
        self._state = target

    def bind(self, context: WorkspaceContext) -> None:
        """Bind the workspace's runtime services (on activation, doc 25 §7)."""
        self._context = context

    def unbind(self) -> None:
        """Release the workspace's runtime services (on deactivation)."""
        self._context = None
