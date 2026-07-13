"""Graph edge model (doc 12 §4) — İlişki (relation) types.

Edges are typed and directional: ``source`` relates to ``target`` by
``kind``. Traversal (neighbors/path/subgraph/impact, doc 12 §8) walks these.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from turkish_code.graf.kimlik import EntityId
from turkish_code.ortak.kimlik import ProvenanceRef


class EdgeKind(StrEnum):
    """Relation types (doc 12 §4) — code relations and project relations."""

    # Code
    DEFINES = "defines"
    CALLS = "calls"
    IMPORTS = "imports"
    DEPENDS_ON = "depends_on"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"
    REFERENCES = "references"
    TESTS = "tests"
    DEFINED_IN = "defined_in"
    MEMBER_OF = "member_of"
    # Project
    OWNS = "owns"
    AUTHORED = "authored"
    DECIDED = "decided"
    MOTIVATES = "motivates"
    SUPERSEDES = "supersedes"
    DOCUMENTS = "documents"
    RELATES_TO = "relates_to"


@dataclass(frozen=True, slots=True)
class Edge:
    """One typed, directional relation between two entities (doc 12 §4)."""

    source: EntityId
    target: EntityId
    kind: EdgeKind
    provenance: ProvenanceRef | None
    created_at: datetime
