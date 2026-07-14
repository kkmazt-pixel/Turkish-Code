"""Optional sqlite-vec ``VectorIndex`` (ADR-C, doc 29 §4/§6, doc 13 §6).

ANN vector search over chunk embeddings, implementing the ``VectorIndex``
Protocol declared in :mod:`turkish_code.getirim.depo`. The backend is *optional*:
sqlite-vec is a loadable SQLite extension, and if it (or its Python loader) is
absent the store still opens fully — only vector operations are unavailable, and
they surface a typed ``RESOURCE`` :class:`AppError` rather than crashing storage
(ADR-C). Vectors are serialised with ``sqlite_vec.serialize_float32`` and stored
in a ``vec0`` virtual table keyed by ``chunk_id``; KNN returns ``-distance`` so a
higher score means nearer, matching the ``LexicalIndex`` convention.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from turkish_code.depo.db import Database
from turkish_code.hata import AppError, ErrorKind

VECTOR_UNSUPPORTED_CODE = "storage.vector_unsupported"
_TABLE = "chunk_vec"


def load_vector_extension(raw: sqlite3.Connection) -> bool:
    """Best-effort load of sqlite-vec onto ``raw`` (ADR-C, doc 29 §6).

    Returns ``True`` when vector search is available on this connection. Never
    raises: storage must open even when the optional backend is absent, so an
    unimportable loader or a failed load simply yields ``False``.
    """
    try:
        import sqlite_vec
    except ImportError:
        return False
    try:
        raw.enable_load_extension(True)
        try:
            sqlite_vec.load(raw)
        finally:
            raw.enable_load_extension(False)
    except (sqlite3.Error, AttributeError):
        return False
    return True


class SqliteVectorIndex:
    """A :class:`~turkish_code.getirim.depo.VectorIndex` over one workspace DB."""

    def __init__(self, db: Database, dim: int) -> None:
        self._db = db
        self._dim = dim

    @classmethod
    async def open(cls, db: Database, *, dim: int) -> SqliteVectorIndex:
        """Attach the ``vec0`` table for ``dim``-vectors, or raise if unsupported.

        Raises a typed ``RESOURCE`` :class:`AppError` when sqlite-vec could not
        be loaded (ADR-C): callers may catch it and fall back to lexical-only
        retrieval — the store itself never fails to open for lack of the backend.
        """
        if dim <= 0:
            raise ValueError(f"vector dimension must be positive, got {dim}")
        if not db.vector_ready:
            raise _unsupported()
        # dim is a validated positive int and the table name is a constant, so
        # this interpolation carries no untrusted input.
        await db.executescript(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {_TABLE} "
            f"USING vec0(chunk_id TEXT PRIMARY KEY, embedding float[{dim}])"
        )
        return cls(db, dim)

    async def upsert(self, chunk_id: str, vector: Sequence[float]) -> None:
        """Insert or replace ``chunk_id``'s embedding (doc 13 §6).

        vec0 rejects ``INSERT OR REPLACE`` on its primary key, so we
        delete-then-insert within one transaction to keep the write atomic.
        """
        payload = _serialize(vector, self._dim)
        async with self._db.transaction() as tx:
            await tx.execute(f"DELETE FROM {_TABLE} WHERE chunk_id = ?", (chunk_id,))
            await tx.execute(
                f"INSERT INTO {_TABLE} (chunk_id, embedding) VALUES (?, ?)",
                (chunk_id, payload),
            )

    async def search(
        self, query_vector: Sequence[float], *, top_k: int
    ) -> Sequence[tuple[str, float]]:
        """Return up to ``top_k`` nearest ``(chunk_id, score)`` pairs (doc 13 §6)."""
        payload = _serialize(query_vector, self._dim)
        rows = await self._db.fetchall(
            f"SELECT chunk_id, distance FROM {_TABLE} "
            "WHERE embedding MATCH ? ORDER BY distance LIMIT ?",
            (payload, top_k),
        )
        return [(str(row["chunk_id"]), -float(row["distance"])) for row in rows]


def _serialize(vector: Sequence[float], dim: int) -> bytes:
    if len(vector) != dim:
        raise ValueError(f"expected a {dim}-dim vector, got {len(vector)}")
    import sqlite_vec

    packed: bytes = sqlite_vec.serialize_float32(list(vector))
    return packed


def _unsupported() -> AppError:
    return AppError(
        kind=ErrorKind.RESOURCE,
        code=VECTOR_UNSUPPORTED_CODE,
        message_key=f"hata.{VECTOR_UNSUPPORTED_CODE}",
        retryable=False,
        detail="sqlite-vec vector backend is not available on this connection",
        remedy_key="hata.vector.install_sqlite_vec",
    )
