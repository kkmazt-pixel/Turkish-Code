"""The effective configuration value object (doc 33).

An immutable snapshot resolved once at boot and injected into subsystems
(doc 33 §9). Only the keys the current foundation actually uses are modelled;
adding fields later is additive with safe defaults (doc 33 §23 — YAGNI).
"""

from __future__ import annotations

from dataclasses import dataclass

from turkish_code.ortak.seviye import LogLevel
from turkish_code.yapilandirma.saglayicilar import ProvidersConfig
from turkish_code.yapilandirma.yollar import Paths
from turkish_code.yapilandirma.zeka import (
    EmbeddingConfig,
    GraphConfig,
    MemoryConfig,
    RetrievalConfig,
)


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved, validated runtime configuration (doc 33).

    Attributes:
        locale: UI/text locale, ``"tr"`` by default (doc 33 §8).
        log_level: Minimum severity the logger emits (doc 39 §5).
        paths: Resolved on-disk directories (doc 33 §7).
        providers: Provider credentials/endpoints + default cost mode (doc 33 §12).
        memory: Recall/consolidation tunables (doc 11 §13) — schema only, unused.
        graph: Extraction tunables (doc 12 §11) — schema only, unused.
        retrieval: Chunking/fusion tunables (doc 13 §12) — schema only, unused.
        embedding: Batching/cache tunables (doc 14 §11) — schema only, unused.
    """

    locale: str
    log_level: LogLevel
    paths: Paths
    providers: ProvidersConfig
    memory: MemoryConfig
    graph: GraphConfig
    retrieval: RetrievalConfig
    embedding: EmbeddingConfig
