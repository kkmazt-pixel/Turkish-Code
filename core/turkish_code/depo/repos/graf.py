"""SQLite-backed :class:`KnowledgeRepository` (doc 12 §4/§8, doc 29 §9).

Implements the query Protocol declared in :mod:`turkish_code.graf.depo` over
relational ``graph_node``/``graph_edge`` tables with recursive-CTE traversal
(doc 12 §4). Also exposes ``upsert_node``/``upsert_edge`` — the write substrate
the extraction pipeline (doc 12 §6) will use; identity-preserving upserts keep
memory/timeline links stable across edits (doc 12 §5).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from turkish_code.depo.baglanti import Row
from turkish_code.depo.db import Database
from turkish_code.depo.repos.graf_gezinme import reachable_ids_query
from turkish_code.gomme.kimlik import VectorId
from turkish_code.graf.depo import Direction
from turkish_code.graf.dugum import Location, Node, NodeKind
from turkish_code.graf.kenar import Edge, EdgeKind
from turkish_code.graf.kimlik import EntityId
from turkish_code.ortak.kimlik import EventId, ProvenanceRef, RunId

_NODE_FIELDS = (
    "id, name, kind, file_path, start_line, end_line, language, signature, "
    "summary, embedding_ref, embedder_id, embedding_dim, salience, run_id, "
    "event_id, created_at, updated_at"
)
# Every node column except the identity (id) and the immutable created_at is
# refreshed on upsert — identity is preserved, content updated (doc 12 §5/§6).
_NODE_UPDATABLE = tuple(
    col.strip()
    for col in _NODE_FIELDS.split(",")
    if col.strip() not in ("id", "created_at")
)
_NODE_UPSERT_SET = ", ".join(f"{col}=excluded.{col}" for col in _NODE_UPDATABLE)
_EDGE_COLUMNS = "source, target, kind, run_id, event_id, created_at"


class SqliteKnowledgeRepository:
    """A :class:`~turkish_code.graf.depo.KnowledgeRepository` over one DB."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def upsert_node(self, node: Node) -> None:
        """Insert or identity-preservingly update a node (doc 12 §5/§6)."""
        async with self._db.transaction() as tx:
            await tx.execute(
                f"INSERT INTO graph_node ({_NODE_FIELDS}) "
                f"VALUES ({', '.join('?' * 17)}) "
                f"ON CONFLICT(id) DO UPDATE SET {_NODE_UPSERT_SET}",
                _node_params(node),
            )

    async def upsert_edge(self, edge: Edge) -> None:
        """Insert an edge (idempotent on source+target+kind, doc 12 §6)."""
        async with self._db.transaction() as tx:
            await tx.execute(
                f"INSERT INTO graph_edge ({_EDGE_COLUMNS}) VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(source, target, kind) DO NOTHING",
                _edge_params(edge),
            )

    async def get_node(self, entity_id: EntityId) -> Node | None:
        row = await self._db.fetchone(
            f"SELECT {_NODE_FIELDS} FROM graph_node WHERE id = ?", (entity_id.value,)
        )
        return _row_to_node(row) if row is not None else None

    async def neighbors(
        self,
        entity_id: EntityId,
        *,
        edge_kinds: Sequence[EdgeKind] | None = None,
        depth: int = 1,
        direction: Direction = Direction.BOTH,
    ) -> Sequence[Node]:
        reachable = await self._reachable(
            [entity_id.value], depth=depth, direction=direction, edge_kinds=edge_kinds
        )
        reachable.discard(entity_id.value)  # strict neighbors exclude the seed
        return await self._nodes_by_ids(reachable)

    async def impact(self, entity_id: EntityId, *, max_depth: int) -> Sequence[Node]:
        # Reverse-dependency closure: who points at this node (doc 12 §7).
        reachable = await self._reachable(
            [entity_id.value], depth=max_depth, direction=Direction.INCOMING
        )
        reachable.discard(entity_id.value)
        return await self._nodes_by_ids(reachable)

    async def subgraph(
        self, seed_ids: Sequence[EntityId], *, hops: int
    ) -> tuple[Sequence[Node], Sequence[Edge]]:
        seeds = [entity.value for entity in seed_ids]
        reachable = await self._reachable(seeds, depth=hops, direction=Direction.BOTH)
        nodes = await self._nodes_by_ids(reachable)
        edges = await self._edges_within(reachable)
        return nodes, edges

    async def search(self, text: str, *, limit: int) -> Sequence[Node]:
        rows = await self._db.fetchall(
            f"SELECT {_NODE_FIELDS} FROM graph_node WHERE name LIKE ? "
            "ORDER BY salience DESC, name ASC LIMIT ?",
            (f"%{text}%", limit),
        )
        return [_row_to_node(row) for row in rows]

    async def path(
        self, source: EntityId, target: EntityId, *, max_hops: int
    ) -> Sequence[Edge] | None:
        if source == target:
            return []
        visited = {source.value}
        predecessor: dict[str, Edge] = {}
        frontier = [source.value]
        for _ in range(max_hops):
            next_frontier: list[str] = []
            for node in frontier:
                for edge in await self._outgoing(node):
                    tv = edge.target.value
                    if tv in visited:
                        continue
                    visited.add(tv)
                    predecessor[tv] = edge
                    if tv == target.value:
                        return _reconstruct(predecessor, target.value, source.value)
                    next_frontier.append(tv)
            frontier = next_frontier
        return None

    async def _reachable(
        self,
        seed_ids: list[str],
        *,
        depth: int,
        direction: Direction,
        edge_kinds: Sequence[EdgeKind] | None = None,
    ) -> set[str]:
        kinds = [kind.value for kind in edge_kinds] if edge_kinds else None
        sql, params = reachable_ids_query(
            seed_ids, depth=depth, direction=direction, edge_kinds=kinds
        )
        rows = await self._db.fetchall(sql, params)
        return {row["id"] for row in rows}

    async def _nodes_by_ids(self, ids: set[str]) -> list[Node]:
        if not ids:
            return []
        placeholders = ", ".join("?" * len(ids))
        rows = await self._db.fetchall(
            f"SELECT {_NODE_FIELDS} FROM graph_node WHERE id IN ({placeholders}) "
            "ORDER BY name ASC",
            list(ids),
        )
        return [_row_to_node(row) for row in rows]

    async def _edges_within(self, ids: set[str]) -> list[Edge]:
        if not ids:
            return []
        placeholders = ", ".join("?" * len(ids))
        params = list(ids) + list(ids)
        rows = await self._db.fetchall(
            f"SELECT {_EDGE_COLUMNS} FROM graph_edge "
            f"WHERE source IN ({placeholders}) AND target IN ({placeholders})",
            params,
        )
        return [_row_to_edge(row) for row in rows]

    async def _outgoing(self, node_value: str) -> list[Edge]:
        rows = await self._db.fetchall(
            f"SELECT {_EDGE_COLUMNS} FROM graph_edge WHERE source = ?", (node_value,)
        )
        return [_row_to_edge(row) for row in rows]


def _reconstruct(predecessor: dict[str, Edge], target: str, source: str) -> list[Edge]:
    chain: list[Edge] = []
    cursor = target
    while cursor != source:
        edge = predecessor[cursor]
        chain.append(edge)
        cursor = edge.source.value
    chain.reverse()
    return chain


def _node_params(node: Node) -> tuple[object, ...]:
    loc = node.location
    emb = node.embedding_ref
    src = node.source
    return (
        node.id.value,
        node.name,
        node.kind.value,
        loc.file_path if loc is not None else None,
        loc.start_line if loc is not None else None,
        loc.end_line if loc is not None else None,
        node.language,
        node.signature,
        node.summary,
        emb.ref if emb is not None else None,
        emb.embedder_id if emb is not None else None,
        emb.dim if emb is not None else None,
        node.salience,
        src.run_id.value if src is not None else None,
        src.event_id.value if src is not None else None,
        node.created_at.isoformat(),
        node.updated_at.isoformat(),
    )


def _edge_params(edge: Edge) -> tuple[object, ...]:
    prov = edge.provenance
    return (
        edge.source.value,
        edge.target.value,
        edge.kind.value,
        prov.run_id.value if prov is not None else None,
        prov.event_id.value if prov is not None else None,
        edge.created_at.isoformat(),
    )


def _row_to_node(row: Row) -> Node:
    return Node(
        id=EntityId(row["id"]),
        name=row["name"],
        kind=NodeKind(row["kind"]),
        location=_location(row),
        language=row["language"],
        signature=row["signature"],
        summary=row["summary"],
        embedding_ref=_vector_id(row),
        salience=row["salience"],
        source=_provenance(row),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _row_to_edge(row: Row) -> Edge:
    return Edge(
        source=EntityId(row["source"]),
        target=EntityId(row["target"]),
        kind=EdgeKind(row["kind"]),
        provenance=_provenance(row),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _location(row: Row) -> Location | None:
    if row["file_path"] is None:
        return None
    return Location(
        file_path=row["file_path"],
        start_line=row["start_line"],
        end_line=row["end_line"],
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
