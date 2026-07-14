"""Tests for the SQLite KnowledgeRepository (doc 12 §4/§7/§8, doc 29 §9)."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest
from turkish_code.depo.db import Database
from turkish_code.depo.migrate import load_migrations, migrate
from turkish_code.depo.repos.graf import SqliteKnowledgeRepository
from turkish_code.gomme.kimlik import VectorId
from turkish_code.graf.depo import Direction, KnowledgeRepository
from turkish_code.graf.dugum import Location, Node, NodeKind
from turkish_code.graf.kenar import Edge, EdgeKind
from turkish_code.graf.kimlik import EntityId
from turkish_code.ortak.kimlik import EventId, ProvenanceRef, RunId
from turkish_code.yapilandirma.depolama import StorageConfig

_TS = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)


async def _repo(tmp_path: Path) -> tuple[Database, SqliteKnowledgeRepository]:
    db = await Database.open(tmp_path / "workspace.db", config=StorageConfig())
    await migrate(db, load_migrations("workspace"))
    return db, SqliteKnowledgeRepository(db)


def _node(nid: str, *, name: str | None = None, rich: bool = False) -> Node:
    return Node(
        id=EntityId(nid),
        name=name or nid,
        kind=NodeKind.FUNCTION,
        location=Location("src/x.py", 1, 9) if rich else None,
        language="python" if rich else None,
        signature="def x()" if rich else None,
        summary="özet" if rich else None,
        embedding_ref=(VectorId(ref="v", embedder_id="bge", dim=8) if rich else None),
        salience=0.5,
        source=(
            ProvenanceRef(run_id=RunId("r"), event_id=EventId("e")) if rich else None
        ),
        created_at=_TS,
        updated_at=_TS,
    )


def _edge(src: str, tgt: str, kind: EdgeKind = EdgeKind.CALLS) -> Edge:
    return Edge(
        source=EntityId(src),
        target=EntityId(tgt),
        kind=kind,
        provenance=None,
        created_at=_TS,
    )


async def _ids(nodes: object) -> list[str]:
    return sorted(n.id.value for n in nodes)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_repo_satisfies_the_protocol(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        assert isinstance(repo, KnowledgeRepository)
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_upsert_and_get_node_full_fidelity(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        node = _node("n1", rich=True)
        await repo.upsert_node(node)
        assert await repo.get_node(EntityId("n1")) == node
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_get_missing_node_returns_none(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        assert await repo.get_node(EntityId("absent")) is None
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_upsert_preserves_identity_and_updates(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.upsert_node(_node("n1", name="old"))
        await repo.upsert_node(_node("n1", name="new"))
        got = await repo.get_node(EntityId("n1"))
        assert got is not None and got.name == "new"
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_neighbors_respect_direction(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        for n in ("a", "b"):
            await repo.upsert_node(_node(n))
        await repo.upsert_edge(_edge("a", "b"))
        out = await repo.neighbors(EntityId("a"), direction=Direction.OUTGOING)
        inc = await repo.neighbors(EntityId("a"), direction=Direction.INCOMING)
        assert await _ids(out) == ["b"]
        assert await _ids(inc) == []
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_neighbors_depth_is_bounded(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        for n in ("a", "b", "c"):
            await repo.upsert_node(_node(n))
        await repo.upsert_edge(_edge("a", "b"))
        await repo.upsert_edge(_edge("b", "c"))
        d1 = await repo.neighbors(EntityId("a"), depth=1, direction=Direction.OUTGOING)
        d2 = await repo.neighbors(EntityId("a"), depth=2, direction=Direction.OUTGOING)
        assert await _ids(d1) == ["b"]
        assert await _ids(d2) == ["b", "c"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_neighbors_filter_by_edge_kind(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        for n in ("a", "b", "c"):
            await repo.upsert_node(_node(n))
        await repo.upsert_edge(_edge("a", "b", EdgeKind.CALLS))
        await repo.upsert_edge(_edge("a", "c", EdgeKind.IMPORTS))
        only_calls = await repo.neighbors(
            EntityId("a"), edge_kinds=[EdgeKind.CALLS], direction=Direction.OUTGOING
        )
        assert await _ids(only_calls) == ["b"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_traversal_is_cycle_safe(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        for n in ("a", "b", "c"):
            await repo.upsert_node(_node(n))
        await repo.upsert_edge(_edge("a", "b"))
        await repo.upsert_edge(_edge("b", "c"))
        await repo.upsert_edge(_edge("c", "a"))  # cycle
        reached = await repo.neighbors(
            EntityId("a"), depth=10, direction=Direction.OUTGOING
        )
        assert await _ids(reached) == ["b", "c"]  # seed excluded, terminates
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_impact_is_reverse_closure(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        for n in ("a", "b", "c"):
            await repo.upsert_node(_node(n))
        await repo.upsert_edge(_edge("a", "c"))
        await repo.upsert_edge(_edge("b", "c"))
        impacted = await repo.impact(EntityId("c"), max_depth=1)
        assert await _ids(impacted) == ["a", "b"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_subgraph_returns_nodes_and_internal_edges(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        for n in ("a", "b", "c"):
            await repo.upsert_node(_node(n))
        await repo.upsert_edge(_edge("a", "b"))
        await repo.upsert_edge(_edge("b", "c"))
        nodes, edges = await repo.subgraph([EntityId("a")], hops=1)
        assert await _ids(nodes) == ["a", "b"]
        assert {(e.source.value, e.target.value) for e in edges} == {("a", "b")}
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_search_matches_name_substring(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.upsert_node(_node("n1", name="verifyToken"))
        await repo.upsert_node(_node("n2", name="parseConfig"))
        found = await repo.search("Token", limit=10)
        assert await _ids(found) == ["n1"]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_path_returns_edge_chain(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        for n in ("a", "b", "c"):
            await repo.upsert_node(_node(n))
        await repo.upsert_edge(_edge("a", "b"))
        await repo.upsert_edge(_edge("b", "c"))
        chain = await repo.path(EntityId("a"), EntityId("c"), max_hops=5)
        assert chain is not None
        assert [(e.source.value, e.target.value) for e in chain] == [
            ("a", "b"),
            ("b", "c"),
        ]
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_path_none_when_unreachable_within_hops(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        for n in ("a", "b", "c"):
            await repo.upsert_node(_node(n))
        await repo.upsert_edge(_edge("a", "b"))
        await repo.upsert_edge(_edge("b", "c"))
        assert await repo.path(EntityId("a"), EntityId("c"), max_hops=1) is None
    finally:
        await db.aclose()


@pytest.mark.asyncio
async def test_path_same_node_is_empty(tmp_path: Path) -> None:
    db, repo = await _repo(tmp_path)
    try:
        await repo.upsert_node(_node("a"))
        assert await repo.path(EntityId("a"), EntityId("a"), max_hops=5) == []
    finally:
        await db.aclose()
