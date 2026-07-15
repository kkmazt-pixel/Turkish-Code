"""The workspace contract (doc 25 §4) — interface only.

:class:`Workspace` is the read-only view every workspace instance exposes: its
id, descriptive metadata, and lifecycle state. The registry, manager, and
lifecycle depend on this Protocol, never on a concrete workspace — so the
implementation can evolve without the runtime changing (DIP). A workspace binds
the other runtimes (Conversation/Agent/Skill/Tool/Plugin/Storage/Provider); it
never touches subsystems directly (doc 25).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from turkish_code.calisma_alani.modeller import (
    WorkspaceId,
    WorkspaceMetadata,
    WorkspaceState,
)


@runtime_checkable
class Workspace(Protocol):
    """A single workspace's read-only identity + state (doc 25 §4)."""

    @property
    def id(self) -> WorkspaceId:
        """The workspace's stable id (doc 25 §4)."""
        ...

    @property
    def metadata(self) -> WorkspaceMetadata:
        """The workspace's descriptive metadata (doc 25 §4)."""
        ...

    @property
    def state(self) -> WorkspaceState:
        """The workspace's current lifecycle state (doc 25 §7)."""
        ...
