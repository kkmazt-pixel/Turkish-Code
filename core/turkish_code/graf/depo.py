"""The knowledge graph query interface (doc 12 §8) — interface only.

No concrete implementation here: storage (doc 29, relational tables +
recursive CTEs) doesn't exist yet. Every traversal is bounded (max
depth/breadth, PR-14) by contract — an implementation must honor that, not
just document it.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from typing import Protocol, runtime_checkable

from turkish_code.graf.dugum import Node
from turkish_code.graf.kenar import Edge, EdgeKind
from turkish_code.graf.kimlik import EntityId


class Direction(StrEnum):
    """Which way to traverse edges relative to a node (doc 12 §8)."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"


@runtime_checkable
class KnowledgeRepository(Protocol):
    """Read/query access to the graph (doc 12 §8)."""

    async def get_node(self, entity_id: EntityId) -> Node | None:
        """Fetch one node by id, or ``None`` if it doesn't exist."""
        ...

    async def neighbors(
        self,
        entity_id: EntityId,
        *,
        edge_kinds: Sequence[EdgeKind] | None = None,
        depth: int = 1,
        direction: Direction = Direction.BOTH,
    ) -> Sequence[Node]:
        """Nodes reachable from ``entity_id`` within ``depth`` hops (doc 12 §8).

        ``depth`` bounds the traversal (PR-14) — never unbounded.
        """
        ...

    async def path(
        self, source: EntityId, target: EntityId, *, max_hops: int
    ) -> Sequence[Edge] | None:
        """The shortest edge path from ``source`` to ``target``, if one exists
        within ``max_hops`` (doc 12 §8)."""
        ...

    async def subgraph(
        self, seed_ids: Sequence[EntityId], *, hops: int
    ) -> tuple[Sequence[Node], Sequence[Edge]]:
        """The nodes/edges within ``hops`` of any of ``seed_ids`` (doc 12 §8)."""
        ...

    async def search(self, text: str, *, limit: int) -> Sequence[Node]:
        """Name/keyword search for seed nodes (doc 12 §8), bounded by ``limit``."""
        ...

    async def impact(self, entity_id: EntityId, *, max_depth: int) -> Sequence[Node]:
        """Reverse-dependency closure: what depends on/calls ``entity_id``
        (doc 12 §7/§8), bounded by ``max_depth``."""
        ...
