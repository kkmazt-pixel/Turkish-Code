"""Memory system (doc 11) — Bellek.

The layered, durable memory that lets turkish.code remember across turns and
sessions (P4). Built on Getirim (doc 13)/Bilgi Grafı (doc 12)/Gömme (doc 14),
never reimplementing them (doc 11 §6). This increment is the schema +
repository/indexer contract layer only — no consolidation, decay, or recall
ranking logic yet (those need Storage, doc 29, and a real embedder).
"""

from turkish_code.bellek.depo import MemoryRepository
from turkish_code.bellek.durum import MemoryState
from turkish_code.bellek.indeks import MemoryIndexer
from turkish_code.bellek.katman import MemoryKind, MemoryLayer, MemoryScope
from turkish_code.bellek.kayit import MemoryItem
from turkish_code.bellek.kimlik import MemoryId

__all__ = [
    "MemoryId",
    "MemoryLayer",
    "MemoryScope",
    "MemoryKind",
    "MemoryState",
    "MemoryItem",
    "MemoryRepository",
    "MemoryIndexer",
]
