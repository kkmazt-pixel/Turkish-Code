"""Graph node model (doc 12 §4) — Varlık (entity) types.

Node properties beyond ``id``/``name``/``kind`` are all optional: a node is
usable the moment it's extracted, and gains ``summary``/``embedding_ref`` as
later, budgeted enrichment passes run (doc 12 §6).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from turkish_code.gomme.kimlik import VectorId
from turkish_code.graf.kimlik import EntityId
from turkish_code.ortak.kimlik import ProvenanceRef


class NodeKind(StrEnum):
    """Entity types the graph tracks (doc 12 §4)."""

    FILE = "file"
    MODULE = "module"
    FUNCTION = "function"
    CLASS_ = "class"
    VARIABLE = "variable"
    INTERFACE = "interface"
    TEST = "test"
    CONCEPT = "concept"
    DECISION = "decision"
    REQUIREMENT = "requirement"
    PERSON = "person"
    EXTERNAL_DEP = "external_dep"
    CONFIG = "config"
    ENDPOINT = "endpoint"
    DOC = "doc"


@dataclass(frozen=True, slots=True)
class Location:
    """Where a node lives in the workspace (doc 12 §4) — file + optional span."""

    file_path: str
    start_line: int | None = None
    end_line: int | None = None


@dataclass(frozen=True, slots=True)
class Node:
    """One graph entity (doc 12 §4)."""

    id: EntityId
    name: str
    kind: NodeKind
    location: Location | None
    language: str | None
    signature: str | None
    summary: str | None
    embedding_ref: VectorId | None
    salience: float
    source: ProvenanceRef | None
    created_at: datetime
    updated_at: datetime
