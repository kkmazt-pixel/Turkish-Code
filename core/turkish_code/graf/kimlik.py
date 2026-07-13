"""Entity identity (doc 12 §5) — the critical invariant that makes the graph
(and memory links, doc 11) durable across edits.

An entity's id is a deterministic hash of a **qualified, location-independent
key** — never a byte offset or file position, which would break on any edit.

Note on hashing: this uses stdlib SHA-256, not BLAKE3 (doc 29's choice for
content-addressed blob storage). BLAKE3's speed advantage matters for hashing
large file contents on every write; entity keys are short strings hashed
once at extraction time, so stdlib hashing avoids a dependency with no
practical benefit here. The two hashes are unrelated identity spaces.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntityId:
    """A stable graph entity identifier (doc 12 §5)."""

    value: str


def compute_entity_id(language: str, qualified_name: str, arity: int) -> EntityId:
    """Derive a deterministic, location-independent id (doc 12 §5).

    Same ``(language, qualified_name, arity)`` always yields the same id
    (PR-15) — this is what lets renames/moves be detected as identity-
    preserving updates rather than delete+add, and what lets memory (doc 11)
    and the Timeline reference entities reliably over time.
    """
    key = f"{language}\0{qualified_name}\0{arity}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return EntityId(value=digest)
