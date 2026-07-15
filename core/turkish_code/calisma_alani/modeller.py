"""Workspace value objects — id, metadata, and lifecycle state (doc 25 §4).

A workspace is a project root plus a stable id (doc 25 §4); these immutable value
objects carry that identity, its descriptive :class:`WorkspaceMetadata`, and its
:class:`WorkspaceState` in the lifecycle. Pure data — the registry, context,
manager, and lifecycle build on them. This runtime manages workspace *lifecycle
and services*; it is not a UI, desktop shell, or planner.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

DEFAULT_CONFIG_VERSION = 1
"""The current workspace-config schema version (migration seam, doc 33)."""


class WorkspaceState(StrEnum):
    """A workspace's lifecycle state (doc 25 §7).

    ``CREATED`` (initialized, not active) → ``ACTIVE`` (open, in use) ⇄
    ``INACTIVE`` (deactivated) → ``ARCHIVED`` (retained, restorable) →
    ``SHUTDOWN`` (terminal). The lifecycle drives the transitions.
    """

    CREATED = "created"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True, slots=True)
class WorkspaceId:
    """The stable id of one workspace (doc 25 §4) — a canonical-path-derived key."""

    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("WorkspaceId.value must be non-empty")


@dataclass(frozen=True, slots=True)
class WorkspaceMetadata:
    """A workspace's descriptive identity (doc 25 §4).

    Attributes:
        name: Human-facing display name (Turkish).
        root: The project root path the workspace is bound to (doc 25 §4);
            the user's files stay there — only derived state lives in DATA_DIR.
        description: Optional free-form description.
    """

    name: str
    root: str
    description: str = ""

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("WorkspaceMetadata.name must be non-empty")
        if not self.root:
            raise ValueError("WorkspaceMetadata.root must be non-empty")


def migrate_config(data: Mapping[str, object]) -> dict[str, object]:
    """Migrate a raw workspace-config dict to the current schema (a seam, doc 33).

    No migrations exist yet: it defaults the version and returns the data
    unchanged. This is the single place where future schema-version bumps apply
    their transforms — the rest of the runtime only sees the current shape.
    """
    migrated = dict(data)
    migrated.setdefault("version", DEFAULT_CONFIG_VERSION)
    return migrated


@dataclass(frozen=True, slots=True)
class WorkspaceConfig:
    """Per-workspace configuration overrides (doc 25 §4, doc 33) — durable-by-default.

    Attributes:
        default_agent_id: The agent new conversations default to (``""`` = none).
        max_history_turns: Conversation context window in turns (doc 11 §6/PR-14).
        memory_enabled: Whether to inject memory into conversation context.
        version: The config schema version (migration seam).
    """

    default_agent_id: str = ""
    max_history_turns: int = 10
    memory_enabled: bool = True
    version: int = DEFAULT_CONFIG_VERSION

    def __post_init__(self) -> None:
        if self.max_history_turns < 0:
            raise ValueError(
                f"WorkspaceConfig.max_history_turns must be >= 0, "
                f"got {self.max_history_turns}"
            )
        if self.version < 1:
            raise ValueError(
                f"WorkspaceConfig.version must be >= 1, got {self.version}"
            )

    def to_dict(self) -> dict[str, object]:
        """Serialise to a plain dict for persistence (config.toml, doc 25 §4)."""
        return {
            "default_agent_id": self.default_agent_id,
            "max_history_turns": self.max_history_turns,
            "memory_enabled": self.memory_enabled,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> WorkspaceConfig:
        """Parse + validate a persisted config, migrating it first (doc 33).

        Raises ``ValueError`` on a missing-typed or out-of-range field.
        """
        migrated = migrate_config(data)
        agent = migrated.get("default_agent_id", "")
        turns = migrated.get("max_history_turns", 10)
        memory = migrated.get("memory_enabled", True)
        version = migrated.get("version", DEFAULT_CONFIG_VERSION)
        if not isinstance(agent, str):
            raise ValueError("WorkspaceConfig.default_agent_id must be a string")
        if not isinstance(turns, int) or isinstance(turns, bool):
            raise ValueError("WorkspaceConfig.max_history_turns must be an int")
        if not isinstance(memory, bool):
            raise ValueError("WorkspaceConfig.memory_enabled must be a bool")
        if not isinstance(version, int) or isinstance(version, bool):
            raise ValueError("WorkspaceConfig.version must be an int")
        return cls(
            default_agent_id=agent,
            max_history_turns=turns,
            memory_enabled=memory,
            version=version,
        )
