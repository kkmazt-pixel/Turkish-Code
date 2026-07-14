"""On-disk storage layout (doc 29 §5, doc 25 §4) — pure path derivation.

Maps the app data dir to the App DB and each workspace's isolated files:

    DATA_DIR/app.db                              # global state (doc 29 §5)
    DATA_DIR/alanlar/<workspace-id>/workspace.db # per-project (doc 25 §4)
    DATA_DIR/alanlar/<workspace-id>/blobs/       # CAS (doc 29 §6)
    DATA_DIR/alanlar/<workspace-id>/journal/     # event journal (doc 29 §7)

No I/O here — only :class:`pathlib.Path` composition, so it is trivially
testable and has no side effects. Actually opening/creating these is the
connection layer's job (doc 29 §11 ``db.py``, Increment 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final

APP_DB_NAME: Final = "app.db"
WORKSPACES_DIR: Final = "alanlar"
WORKSPACE_DB_NAME: Final = "workspace.db"
BLOBS_DIR: Final = "blobs"
JOURNAL_DIR: Final = "journal"

_ALLOWED_ID_CHARS: Final = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
)


@dataclass(frozen=True, slots=True)
class StorageLayout:
    """Derives every storage path from one app data dir (doc 29 §5, doc 25 §4)."""

    data_dir: Path

    @property
    def app_db_path(self) -> Path:
        """The global App DB (doc 29 §5)."""
        return self.data_dir / APP_DB_NAME

    def workspace_dir(self, workspace_id: str) -> Path:
        """The isolated data dir for one workspace (doc 25 §4)."""
        return self.data_dir / WORKSPACES_DIR / _safe_id(workspace_id)

    def workspace_db_path(self, workspace_id: str) -> Path:
        """The per-project Workspace DB (doc 25 §4)."""
        return self.workspace_dir(workspace_id) / WORKSPACE_DB_NAME

    def blobs_dir(self, workspace_id: str) -> Path:
        """The content-addressed blob store for one workspace (doc 29 §6)."""
        return self.workspace_dir(workspace_id) / BLOBS_DIR

    def journal_dir(self, workspace_id: str) -> Path:
        """The event journal dir for one workspace (doc 29 §7)."""
        return self.workspace_dir(workspace_id) / JOURNAL_DIR


def _safe_id(workspace_id: str) -> str:
    """Reject any workspace id that isn't a single safe path segment.

    Workspace ids are canonical-path hashes (doc 25 §4) — hex-like tokens.
    Refusing separators/``..``/empty here is defense-in-depth against a
    path-traversal escape from ``DATA_DIR`` (doc 30 §8: paths confined).
    """
    if not workspace_id or not set(workspace_id) <= _ALLOWED_ID_CHARS:
        raise ValueError(f"unsafe workspace id: {workspace_id!r}")
    return workspace_id
