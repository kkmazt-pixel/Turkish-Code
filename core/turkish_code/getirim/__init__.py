"""Retrieval-augmented pipeline (doc 13) — Getirim.

Hybrid retrieval (vector + lexical + graph) fused, reranked, and assembled
into budgeted context. This increment is the contract layer only: chunk
model, query, retriever/fuser/ranking/planner/assembler Protocols, and the
index storage contracts — no ingestion, indexing, or execution yet.
"""

from turkish_code.getirim.birlestirici import Fuser
from turkish_code.getirim.depo import LexicalIndex, VectorIndex
from turkish_code.getirim.getirici import RetrievedCandidate, Retriever
from turkish_code.getirim.kurulum import AssembledContext, ContextAssembler
from turkish_code.getirim.parca import (
    Chunk,
    ChunkSource,
    FileChunkSource,
    MemoryChunkSource,
)
from turkish_code.getirim.planlayici import RetrievalPlanner
from turkish_code.getirim.siralama import RankingStage
from turkish_code.getirim.sorgu import RetrievalQuery

__all__ = [
    "Chunk",
    "ChunkSource",
    "FileChunkSource",
    "MemoryChunkSource",
    "RetrievalQuery",
    "RetrievedCandidate",
    "Retriever",
    "Fuser",
    "RankingStage",
    "RetrievalPlanner",
    "AssembledContext",
    "ContextAssembler",
    "VectorIndex",
    "LexicalIndex",
]
