"""Workspace storage assembly (doc 29 §5, doc 25 §4) — the storage entry point.

:class:`StorageEngine` is the single object the composition root uses to bring
durable storage online: it owns the global **App DB** and mints an isolated
:class:`WorkspaceStore` per workspace on demand (doc 29 §5). Each store bundles
the scoped repository *implementations* — but exposes them only through the
subsystem Protocols (``MemoryRepository``/``KnowledgeRepository``/``LexicalIndex``),
so callers depend on contracts, never on ``depo`` internals (DIP, doc 29 §9/§21).

Opening a workspace runs its migrations forward (doc 29 §10) and wires the DB,
CAS blob store, and event journal over that workspace's isolated directory
(doc 25 §4). The vector index is *not* built eagerly: its dimension is fixed by
the chosen embedder (doc 14) and only known at retrieval time, so it is opened
lazily via :meth:`WorkspaceStore.open_vector_index` (ADR-C, optional backend).
"""

from __future__ import annotations

from dataclasses import dataclass

from turkish_code.bellek.depo import MemoryRepository
from turkish_code.depo.blobs import BlobStore
from turkish_code.depo.db import Database
from turkish_code.depo.fts import SqliteLexicalIndex
from turkish_code.depo.journal import Journal
from turkish_code.depo.migrate import load_migrations, migrate
from turkish_code.depo.repos.bellek import SqliteMemoryRepository
from turkish_code.depo.repos.graf import SqliteKnowledgeRepository
from turkish_code.depo.vec import SqliteVectorIndex
from turkish_code.depo.yerlesim import StorageLayout
from turkish_code.getirim.depo import LexicalIndex, VectorIndex
from turkish_code.graf.depo import KnowledgeRepository
from turkish_code.yapilandirma.depolama import StorageConfig


@dataclass(frozen=True, slots=True)
class WorkspaceStore:
    """The scoped durable-storage handles for one open workspace (doc 25 §4).

    Repositories are typed as their subsystem Protocols so consumers stay
    decoupled from the ``depo`` implementations behind them (DIP, doc 29 §9).
    """

    workspace_id: str
    db: Database
    memory: MemoryRepository
    knowledge: KnowledgeRepository
    lexical: LexicalIndex
    blobs: BlobStore
    journal: Journal

    async def open_vector_index(self, *, dim: int) -> VectorIndex:
        """Open this workspace's vector index for ``dim``-vectors (ADR-C).

        Raises a typed ``RESOURCE`` ``AppError`` when the optional sqlite-vec
        backend is unavailable; retrieval falls back to lexical-only rather
        than failing the whole workspace.
        """
        return await SqliteVectorIndex.open(self.db, dim=dim)

    async def aclose(self) -> None:
        """Close the workspace DB and stop its writer thread. Idempotent."""
        await self.db.aclose()


class StorageEngine:
    """Owns the App DB and opens per-workspace stores (doc 29 §5)."""

    def __init__(
        self, layout: StorageLayout, config: StorageConfig, app_db: Database
    ) -> None:
        self._layout = layout
        self._config = config
        self._app_db = app_db
        self._app_memory = SqliteMemoryRepository(app_db)

    @classmethod
    async def open(cls, layout: StorageLayout, config: StorageConfig) -> StorageEngine:
        """Open the App DB and migrate it forward (doc 29 §5/§10)."""
        app_db = await Database.open(layout.app_db_path, config=config)
        await migrate(app_db, load_migrations("app"))
        return cls(layout, config, app_db)

    @property
    def app_memory(self) -> MemoryRepository:
        """Global-scope memory living in the App DB (doc 11 §13, doc 29 §5)."""
        return self._app_memory

    async def open_workspace(self, workspace_id: str) -> WorkspaceStore:
        """Open one workspace's isolated store, migrating it forward (doc 25 §4).

        The Workspace DB, CAS blob store, and event journal all live under the
        workspace's own directory (doc 29 §5); the id is validated as a single
        safe path segment by :class:`StorageLayout` (doc 30 §8).
        """
        db = await Database.open(
            self._layout.workspace_db_path(workspace_id), config=self._config
        )
        await migrate(db, load_migrations("workspace"))
        blobs = BlobStore(
            self._layout.blobs_dir(workspace_id), db, fsync=self._config.fsync_durable
        )
        journal = await Journal.open(
            self._layout.journal_dir(workspace_id), fsync=self._config.fsync_durable
        )
        return WorkspaceStore(
            workspace_id=workspace_id,
            db=db,
            memory=SqliteMemoryRepository(db),
            knowledge=SqliteKnowledgeRepository(db),
            lexical=SqliteLexicalIndex(db),
            blobs=blobs,
            journal=journal,
        )

    async def aclose(self) -> None:
        """Close the App DB and stop its writer thread. Idempotent."""
        await self._app_db.aclose()
