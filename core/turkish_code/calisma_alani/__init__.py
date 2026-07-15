"""Çalışma Alanı — the Workspace Runtime (doc 25).

A thin, DIP-compliant management layer that owns workspace lifecycle and binds a
workspace to the other runtimes — Conversation, Agent, Skill, Tool, Plugin,
Storage, Provider — through their facades. It never opens SQLite, calls a
provider, runs a tool, or loads a plugin directly; everything flows through the
runtimes (PR-9). A workspace is not a UI, desktop shell, Rust/Tauri surface, or
planner: this phase manages only the workspace lifecycle and its bound services.
The value models come first; the registry, context, manager, and lifecycle build
on them across later increments.
"""

from turkish_code.calisma_alani.baglam import WorkspaceContext
from turkish_code.calisma_alani.hata import (
    WORKSPACE_DUPLICATE_CODE,
    WORKSPACE_INVALID_TRANSITION_CODE,
    WORKSPACE_NOT_FOUND_CODE,
    duplicate_workspace,
    workspace_not_found,
)
from turkish_code.calisma_alani.kayit import WorkspaceRegistry
from turkish_code.calisma_alani.kompozisyon import (
    WorkspaceRuntime,
    build_workspace_runtime,
)
from turkish_code.calisma_alani.modeller import (
    DEFAULT_CONFIG_VERSION,
    WorkspaceConfig,
    WorkspaceId,
    WorkspaceMetadata,
    WorkspaceState,
    migrate_config,
)
from turkish_code.calisma_alani.oturum import WorkspaceSession
from turkish_code.calisma_alani.protocol import Workspace
from turkish_code.calisma_alani.yasam import WorkspaceLifecycle
from turkish_code.calisma_alani.yonetici import (
    WorkspaceContextFactory,
    WorkspaceManager,
)

__all__ = [
    "Workspace",
    "WorkspaceId",
    "WorkspaceMetadata",
    "WorkspaceState",
    "WorkspaceConfig",
    "DEFAULT_CONFIG_VERSION",
    "migrate_config",
    "WorkspaceSession",
    "WorkspaceContext",
    "WorkspaceRegistry",
    "WorkspaceManager",
    "WorkspaceContextFactory",
    "WorkspaceLifecycle",
    "WorkspaceRuntime",
    "build_workspace_runtime",
    "WORKSPACE_NOT_FOUND_CODE",
    "WORKSPACE_DUPLICATE_CODE",
    "WORKSPACE_INVALID_TRANSITION_CODE",
    "workspace_not_found",
    "duplicate_workspace",
]
