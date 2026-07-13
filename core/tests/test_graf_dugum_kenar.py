"""Tests for the Node/Edge graph models (doc 12 §4)."""

from __future__ import annotations

from datetime import UTC, datetime

from turkish_code.graf.dugum import Location, Node, NodeKind
from turkish_code.graf.kenar import Edge, EdgeKind
from turkish_code.graf.kimlik import compute_entity_id

_NOW = datetime(2026, 7, 13, tzinfo=UTC)


def test_node_construction_with_minimal_fields() -> None:
    node = Node(
        id=compute_entity_id("python", "pkg.Foo", 0),
        name="Foo",
        kind=NodeKind.CLASS_,
        location=Location(file_path="pkg/foo.py", start_line=10, end_line=20),
        language="python",
        signature=None,
        summary=None,
        embedding_ref=None,
        salience=0.5,
        source=None,
        created_at=_NOW,
        updated_at=_NOW,
    )
    assert node.kind is NodeKind.CLASS_
    assert node.location is not None
    assert node.location.start_line == 10


def test_edge_connects_two_entities_with_a_kind() -> None:
    caller = compute_entity_id("python", "pkg.a", 0)
    callee = compute_entity_id("python", "pkg.b", 0)
    edge = Edge(
        source=caller,
        target=callee,
        kind=EdgeKind.CALLS,
        provenance=None,
        created_at=_NOW,
    )
    assert edge.kind is EdgeKind.CALLS
    assert edge.source != edge.target


def test_all_documented_node_kinds_are_representable() -> None:
    expected = {
        "file",
        "module",
        "function",
        "class",
        "variable",
        "interface",
        "test",
        "concept",
        "decision",
        "requirement",
        "person",
        "external_dep",
        "config",
        "endpoint",
        "doc",
    }
    assert {k.value for k in NodeKind} == expected


def test_all_documented_edge_kinds_are_representable() -> None:
    expected = {
        "defines",
        "calls",
        "imports",
        "depends_on",
        "implements",
        "extends",
        "references",
        "tests",
        "defined_in",
        "member_of",
        "owns",
        "authored",
        "decided",
        "motivates",
        "supersedes",
        "documents",
        "relates_to",
    }
    assert {k.value for k in EdgeKind} == expected
