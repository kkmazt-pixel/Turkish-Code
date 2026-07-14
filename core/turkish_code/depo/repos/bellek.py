"""SQLite-backed :class:`MemoryRepository` (doc 11 §5/§6, doc 29 §9).

Implements the Protocol declared in :mod:`turkish_code.bellek.depo` over the
connection layer — the one place memory rows are read/written (PR-13). Soft
``forget`` sets a storage-internal tombstone so the row is retained for audit
but excluded from recall; ``purge`` removes it entirely (doc 11 §10/§23).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timedelta

from turkish_code.bellek.durum import MemoryState
from turkish_code.bellek.katman import MemoryKind, MemoryLayer, MemoryScope
from turkish_code.bellek.kayit import MemoryItem
from turkish_code.bellek.kimlik import MemoryId
from turkish_code.depo.baglanti import Row
from turkish_code.depo.db import Database
from turkish_code.gomme.kimlik import VectorId
from turkish_code.graf.kimlik import EntityId
from turkish_code.ortak.kimlik import EventId, ProvenanceRef, RunId

_COLUMNS = (
    "id, layer, scope, kind, state, title, body, links, "
    "embedding_ref, embedder_id, embedding_dim, salience, run_id, event_id, "
    "pinned, created_at, last_used_at, use_count, confidence, ttl_seconds"
)
_PLACEHOLDERS = ", ".join("?" * 20)
_UPDATABLE = (
    "layer",
    "scope",
    "kind",
    "state",
    "title",
    "body",
    "links",
    "embedding_ref",
    "embedder_id",
    "embedding_dim",
    "salience",
    "run_id",
    "event_id",
    "pinned",
    "created_at",
    "last_used_at",
    "use_count",
    "confidence",
    "ttl_seconds",
)


class SqliteMemoryRepository:
    """A :class:`~turkish_code.bellek.depo.MemoryRepository` over one DB."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def get(self, memory_id: MemoryId) -> MemoryItem | None:
        row = await self._db.fetchone(
            f"SELECT {_COLUMNS} FROM memory WHERE id = ?", (memory_id.value,)
        )
        return _row_to_item(row) if row is not None else None

    async def save(self, item: MemoryItem) -> None:
        assignments = ", ".join(f"{col} = excluded.{col}" for col in _UPDATABLE)
        async with self._db.transaction() as tx:
            await tx.execute(
                f"INSERT INTO memory ({_COLUMNS}) VALUES ({_PLACEHOLDERS}) "
                f"ON CONFLICT(id) DO UPDATE SET {assignments}",
                _item_params(item),
            )

    async def recall(
        self,
        *,
        scope: MemoryScope,
        layers: Sequence[MemoryLayer] | None = None,
        limit: int,
    ) -> Sequence[MemoryItem]:
        # Candidates only (doc 11 §8): exclude forgotten tombstones and
        # superseded items (hidden from recall, doc 11 §9). The caller ranks.
        sql = [
            f"SELECT {_COLUMNS} FROM memory WHERE scope = ? "
            "AND forgotten = 0 AND state != ?"
        ]
        params: list[object] = [scope.value, MemoryState.SUPERSEDED.value]
        if layers is not None:
            placeholders = ", ".join("?" * len(layers))
            sql.append(f"AND layer IN ({placeholders})")
            params.extend(layer.value for layer in layers)
        sql.append("ORDER BY salience DESC, id ASC LIMIT ?")
        params.append(limit)
        rows = await self._db.fetchall(" ".join(sql), params)
        return [_row_to_item(row) for row in rows]

    async def pin(self, memory_id: MemoryId) -> None:
        await self._set_pinned(memory_id, pinned=True)

    async def unpin(self, memory_id: MemoryId) -> None:
        await self._set_pinned(memory_id, pinned=False)

    async def forget(self, memory_id: MemoryId) -> None:
        async with self._db.transaction() as tx:
            await tx.execute(
                "UPDATE memory SET forgotten = 1 WHERE id = ?", (memory_id.value,)
            )

    async def purge(self, memory_id: MemoryId) -> None:
        async with self._db.transaction() as tx:
            await tx.execute("DELETE FROM memory WHERE id = ?", (memory_id.value,))

    async def _set_pinned(self, memory_id: MemoryId, *, pinned: bool) -> None:
        async with self._db.transaction() as tx:
            await tx.execute(
                "UPDATE memory SET pinned = ? WHERE id = ?",
                (1 if pinned else 0, memory_id.value),
            )


def _item_params(item: MemoryItem) -> tuple[object, ...]:
    embedding = item.embedding_ref
    source = item.source
    return (
        item.id.value,
        item.layer.value,
        item.scope.value,
        item.kind.value,
        item.state.value,
        item.title,
        item.body,
        json.dumps([entity.value for entity in item.links]),
        embedding.ref if embedding is not None else None,
        embedding.embedder_id if embedding is not None else None,
        embedding.dim if embedding is not None else None,
        item.salience,
        source.run_id.value if source is not None else None,
        source.event_id.value if source is not None else None,
        1 if item.pinned else 0,
        item.created_at.isoformat(),
        item.last_used_at.isoformat(),
        item.use_count,
        item.confidence,
        item.ttl.total_seconds() if item.ttl is not None else None,
    )


def _row_to_item(row: Row) -> MemoryItem:
    return MemoryItem(
        id=MemoryId(row["id"]),
        layer=MemoryLayer(row["layer"]),
        scope=MemoryScope(row["scope"]),
        kind=MemoryKind(row["kind"]),
        state=MemoryState(row["state"]),
        title=row["title"],
        body=row["body"],
        links=[EntityId(value) for value in json.loads(row["links"])],
        embedding_ref=_vector_id(row),
        salience=row["salience"],
        source=_provenance(row),
        pinned=bool(row["pinned"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        last_used_at=datetime.fromisoformat(row["last_used_at"]),
        use_count=row["use_count"],
        confidence=row["confidence"],
        ttl=(
            timedelta(seconds=row["ttl_seconds"])
            if row["ttl_seconds"] is not None
            else None
        ),
    )


def _vector_id(row: Row) -> VectorId | None:
    if row["embedding_ref"] is None:
        return None
    return VectorId(
        ref=row["embedding_ref"],
        embedder_id=row["embedder_id"],
        dim=row["embedding_dim"],
    )


def _provenance(row: Row) -> ProvenanceRef | None:
    if row["run_id"] is None or row["event_id"] is None:
        return None
    return ProvenanceRef(run_id=RunId(row["run_id"]), event_id=EventId(row["event_id"]))
