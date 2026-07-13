"""Memory item lifecycle state machine (doc 11 §12).

::

    [Candidate] -> [Active] <-> [Pinned]
         |            |  decay/disuse
         |            v
         |        [Dormant] -> prune -> [Purged]
         +--rejected--> (dropped, never persisted)
       [Active] --superseded by newer fact--> [Superseded] (retained, hidden)
"""

from __future__ import annotations

from enum import StrEnum


class MemoryState(StrEnum):
    """Where a memory item is in its lifecycle (doc 11 §12)."""

    CANDIDATE = "candidate"
    ACTIVE = "active"
    PINNED = "pinned"
    DORMANT = "dormant"
    SUPERSEDED = "superseded"
    PURGED = "purged"
