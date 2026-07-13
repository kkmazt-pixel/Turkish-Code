"""Knowledge Graph subsystem (doc 12) — Bilgi Grafı.

Structural understanding of a codebase (symbols, deps, decisions) to
complement semantic retrieval (doc 13). Storage is relational tables in the
Workspace DB (doc 29 §4) — sqlite, no external graph DB (doc 12 §4, doc 20
Anti-Pattern: "Requiring an external graph DB"); not built yet, this
increment is the schema + query contract only.
"""

from turkish_code.graf.depo import Direction, KnowledgeRepository
from turkish_code.graf.dugum import Location, Node, NodeKind
from turkish_code.graf.kenar import Edge, EdgeKind
from turkish_code.graf.kimlik import EntityId, compute_entity_id

__all__ = [
    "EntityId",
    "compute_entity_id",
    "Node",
    "NodeKind",
    "Location",
    "Edge",
    "EdgeKind",
    "Direction",
    "KnowledgeRepository",
]
