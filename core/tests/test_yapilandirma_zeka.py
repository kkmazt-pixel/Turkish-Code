"""Tests for the intelligence-layer config schema (doc 11/12/13/14) and its
wiring into ``Settings`` via ``load_settings`` (schema-only, no consumer yet).
"""

from __future__ import annotations

from pathlib import Path

from turkish_code.yapilandirma import sabitler
from turkish_code.yapilandirma.yukleyici import load_settings
from turkish_code.yapilandirma.zeka import (
    EmbeddingConfig,
    GraphConfig,
    MemoryConfig,
    RetrievalConfig,
)


def test_defaults_are_sane() -> None:
    assert MemoryConfig().recall_k == 8
    assert GraphConfig().traversal_max_depth == 4
    assert RetrievalConfig().index_backend == "sqlite-vec"
    assert EmbeddingConfig().batch_size == 32


def test_configs_are_immutable() -> None:
    try:
        MemoryConfig().recall_k = 99  # type: ignore[misc]
        assert False, "MemoryConfig must be frozen"
    except AttributeError:
        pass


def test_load_settings_populates_intelligence_config_with_defaults(
    tmp_path: Path,
) -> None:
    settings = load_settings({sabitler.ENV_CONFIG_DIR: str(tmp_path)})
    assert settings.memory == MemoryConfig()
    assert settings.graph == GraphConfig()
    assert settings.retrieval == RetrievalConfig()
    assert settings.embedding == EmbeddingConfig()
