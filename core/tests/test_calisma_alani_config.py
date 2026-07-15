"""Tests for workspace configuration — persistence, validation, migration (doc 33)."""

from __future__ import annotations

import pytest
from turkish_code.calisma_alani.modeller import (
    DEFAULT_CONFIG_VERSION,
    WorkspaceConfig,
    WorkspaceId,
    WorkspaceMetadata,
    migrate_config,
)
from turkish_code.calisma_alani.oturum import WorkspaceSession


def test_default_settings() -> None:
    config = WorkspaceConfig()
    assert config.default_agent_id == ""
    assert config.max_history_turns == 10
    assert config.memory_enabled is True
    assert config.version == DEFAULT_CONFIG_VERSION


def test_validation_rejects_negative_history() -> None:
    with pytest.raises(ValueError, match="max_history_turns must be >= 0"):
        WorkspaceConfig(max_history_turns=-1)


def test_validation_rejects_bad_version() -> None:
    with pytest.raises(ValueError, match="version must be >= 1"):
        WorkspaceConfig(version=0)


def test_to_dict_and_from_dict_round_trip() -> None:
    config = WorkspaceConfig(
        default_agent_id="yonetici", max_history_turns=5, memory_enabled=False
    )
    restored = WorkspaceConfig.from_dict(config.to_dict())
    assert restored == config


def test_from_dict_uses_defaults_for_missing_keys() -> None:
    config = WorkspaceConfig.from_dict({})
    assert config == WorkspaceConfig()


def test_from_dict_rejects_wrong_types() -> None:
    with pytest.raises(ValueError, match="max_history_turns must be an int"):
        WorkspaceConfig.from_dict({"max_history_turns": "ten"})
    with pytest.raises(ValueError, match="memory_enabled must be a bool"):
        WorkspaceConfig.from_dict({"memory_enabled": "yes"})
    with pytest.raises(ValueError, match="default_agent_id must be a string"):
        WorkspaceConfig.from_dict({"default_agent_id": 5})


def test_from_dict_rejects_bool_for_int_field() -> None:
    # bool is a subclass of int; it must not sneak into an int field
    with pytest.raises(ValueError, match="max_history_turns must be an int"):
        WorkspaceConfig.from_dict({"max_history_turns": True})


def test_from_dict_validates_ranges() -> None:
    with pytest.raises(ValueError, match="max_history_turns must be >= 0"):
        WorkspaceConfig.from_dict({"max_history_turns": -3})


def test_migrate_config_defaults_version() -> None:
    migrated = migrate_config({"default_agent_id": "x"})
    assert migrated["version"] == DEFAULT_CONFIG_VERSION
    assert migrated["default_agent_id"] == "x"


def test_migrate_config_preserves_existing_version() -> None:
    migrated = migrate_config({"version": 1})
    assert migrated["version"] == 1


# --- config on the session ----------------------------------------------------


def test_session_defaults_to_default_config() -> None:
    session = WorkspaceSession(
        WorkspaceId("w1"), WorkspaceMetadata(name="P", root="/p")
    )
    assert session.config == WorkspaceConfig()


def test_session_holds_a_custom_config() -> None:
    config = WorkspaceConfig(default_agent_id="bot", max_history_turns=3)
    session = WorkspaceSession(
        WorkspaceId("w1"), WorkspaceMetadata(name="P", root="/p"), config=config
    )
    assert session.config is config
