"""Tests for the knowledge graph query contract (doc 12 §8)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from turkish_code.graf.depo import Direction, KnowledgeRepository
from turkish_code.graf.dugum import Node, NodeKind
from turkish_code.graf.kenar import Edge, EdgeKind
from turkish_code.graf.kimlik import EntityId, compute_entity_id

_NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _node(entity_id: EntityId, name: str) -> Node:
    return Node(
        id=entity_id,
        name=name,
        kind=NodeKind.FUNCTION,
        location=None,
        language="python",
        signature=None,
        summary=None,
        embedding_ref=None,
        salience=0.5,
        source=None,
        created_at=_NOW,
        updated_at=_NOW,
    )


class _FakeKnowledgeRepository:
    """An in-memory conformance fixture — real logic, no persistence engine."""

    def __init__(self, nodes: dict[EntityId, Node], edges: list[Edge]) -> None:
        self._nodes = nodes
        self._edges = edges

    async def get_node(self, entity_id: EntityId) -> Node | None:
        return self._nodes.get(entity_id)

    async def neighbors(
        self,
        entity_id: EntityId,
        *,
        edge_kinds: Sequence[EdgeKind] | None = None,
        depth: int = 1,
        direction: Direction = Direction.BOTH,
    ) -> Sequence[Node]:
        targets = {e.target for e in self._edges if e.source == entity_id}
        return [self._nodes[t] for t in targets if t in self._nodes]

    async def path(
        self, source: EntityId, target: EntityId, *, max_hops: int
    ) -> Sequence[Edge] | None:
        for edge in self._edges:
            if edge.source == source and edge.target == target:
                return [edge]
        return None

    async def subgraph(
        self, seed_ids: Sequence[EntityId], *, hops: int
    ) -> tuple[Sequence[Node], Sequence[Edge]]:
        return list(self._nodes.values()), self._edges

    async def search(self, text: str, *, limit: int) -> Sequence[Node]:
        return [n for n in self._nodes.values() if text in n.name][:limit]

    async def impact(self, entity_id: EntityId, *, max_depth: int) -> Sequence[Node]:
        sources = {e.source for e in self._edges if e.target == entity_id}
        return [self._nodes[s] for s in sources if s in self._nodes]


def test_fake_repository_satisfies_protocol() -> None:
    repo = _FakeKnowledgeRepository({}, [])
    assert isinstance(repo, KnowledgeRepository)


@pytest.mark.asyncio
async def test_get_node_returns_none_when_absent() -> None:
    repo = _FakeKnowledgeRepository({}, [])
    assert await repo.get_node(compute_entity_id("python", "x", 0)) is None


@pytest.mark.asyncio
async def test_neighbors_follows_outgoing_edges() -> None:
    a_id, b_id = compute_entity_id("python", "a", 0), compute_entity_id(
        "python", "b", 0
    )
    repo = _FakeKnowledgeRepository(
        {a_id: _node(a_id, "a"), b_id: _node(b_id, "b")},
        [
            Edge(
                source=a_id,
                target=b_id,
                kind=EdgeKind.CALLS,
                provenance=None,
                created_at=_NOW,
            )
        ],
    )
    neighbors = await repo.neighbors(a_id)
    assert [n.name for n in neighbors] == ["b"]


@pytest.mark.asyncio
async def test_path_finds_direct_edge() -> None:
    a_id, b_id = compute_entity_id("python", "a", 0), compute_entity_id(
        "python", "b", 0
    )
    edge = Edge(
        source=a_id, target=b_id, kind=EdgeKind.CALLS, provenance=None, created_at=_NOW
    )
    repo = _FakeKnowledgeRepository({}, [edge])
    path = await repo.path(a_id, b_id, max_hops=1)
    assert path == [edge]


@pytest.mark.asyncio
async def test_impact_is_reverse_dependency_closure() -> None:
    caller_id = compute_entity_id("python", "caller", 0)
    callee_id = compute_entity_id("python", "callee", 0)
    repo = _FakeKnowledgeRepository(
        {caller_id: _node(caller_id, "caller"), callee_id: _node(callee_id, "callee")},
        [
            Edge(
                source=caller_id,
                target=callee_id,
                kind=EdgeKind.CALLS,
                provenance=None,
                created_at=_NOW,
            )
        ],
    )
    impacted = await repo.impact(callee_id, max_depth=2)
    assert [n.name for n in impacted] == ["caller"]


@pytest.mark.asyncio
async def test_search_matches_by_substring() -> None:
    node_id = compute_entity_id("python", "verifyToken", 0)
    repo = _FakeKnowledgeRepository({node_id: _node(node_id, "verifyToken")}, [])
    results = await repo.search("verify", limit=10)
    assert [n.name for n in results] == ["verifyToken"]
