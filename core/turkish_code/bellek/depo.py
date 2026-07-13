"""The memory repository contract (doc 11 §6/§10) — interface only.

Write path (capture/filter/embed/store, doc 11 §7) and recall path
(retrieve/rank/budget, doc 11 §8) both go through this boundary; user
control (doc 11 §10: inspect/pin/forget/purge) is part of the same contract.
No concrete implementation — Storage (doc 29) doesn't exist yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from turkish_code.bellek.katman import MemoryLayer, MemoryScope
from turkish_code.bellek.kayit import MemoryItem
from turkish_code.bellek.kimlik import MemoryId


@runtime_checkable
class MemoryRepository(Protocol):
    """Read/write/control access to memory (doc 11 §6/§7/§8/§10)."""

    async def get(self, memory_id: MemoryId) -> MemoryItem | None:
        """Fetch one memory item by id, or ``None`` if it doesn't exist."""
        ...

    async def save(self, item: MemoryItem) -> None:
        """Insert or replace a memory item (doc 11 §7)."""
        ...

    async def recall(
        self,
        *,
        scope: MemoryScope,
        layers: Sequence[MemoryLayer] | None = None,
        limit: int,
    ) -> Sequence[MemoryItem]:
        """Candidate items for the given scope/layers, bounded by ``limit``
        (doc 11 §8) — ranking/dedup/budget is applied by the caller (Bellek's
        recall orchestration, not this storage boundary)."""
        ...

    async def pin(self, memory_id: MemoryId) -> None:
        """Force ``memory_id`` always-relevant (doc 11 §10)."""
        ...

    async def unpin(self, memory_id: MemoryId) -> None:
        """Remove the pin from ``memory_id`` (doc 11 §10)."""
        ...

    async def forget(self, memory_id: MemoryId) -> None:
        """Soft-delete: hide from recall, retained for audit (doc 11 §10)."""
        ...

    async def purge(self, memory_id: MemoryId) -> None:
        """Hard-delete: permanently remove, no recallable residue (doc 11 §10/§23)."""
        ...
