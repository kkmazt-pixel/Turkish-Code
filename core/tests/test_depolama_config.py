"""Tests for the storage configuration schema (doc 29 §12)."""

from __future__ import annotations

import pytest
from turkish_code.yapilandirma.depolama import StorageConfig, VectorBackend
from turkish_code.yapilandirma.yukleyici import load_settings


def test_defaults_are_durable_and_safe() -> None:
    cfg = StorageConfig()
    assert cfg.fsync_durable is True
    assert cfg.blob_gc_enabled is True
    assert cfg.vector_backend is VectorBackend.SQLITE_VEC
    assert cfg.busy_timeout_ms == 5000


def test_negative_busy_timeout_is_rejected() -> None:
    with pytest.raises(ValueError):
        StorageConfig(busy_timeout_ms=-1)


def test_vector_backend_can_be_disabled() -> None:
    cfg = StorageConfig(vector_backend=VectorBackend.NONE)
    assert cfg.vector_backend is VectorBackend.NONE


def test_config_is_frozen() -> None:
    cfg = StorageConfig()
    with pytest.raises(AttributeError):
        cfg.fsync_durable = False  # type: ignore[misc]


def test_settings_carries_storage_defaults() -> None:
    settings = load_settings({})
    assert settings.storage == StorageConfig()
