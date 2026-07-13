"""Tests for configuration loading, precedence, and fail-safe fallback (doc 33)."""

from __future__ import annotations

from pathlib import Path

from turkish_code.ortak.seviye import LogLevel
from turkish_code.yapilandirma import sabitler
from turkish_code.yapilandirma.yollar import resolve_paths
from turkish_code.yapilandirma.yukleyici import load_settings


def _env(config_dir: Path, **extra: str) -> dict[str, str]:
    env = {sabitler.ENV_CONFIG_DIR: str(config_dir)}
    env.update(extra)
    return env


def test_defaults_when_no_file_or_env(tmp_path: Path) -> None:
    settings = load_settings(_env(tmp_path))
    assert settings.locale == sabitler.DEFAULT_LOCALE
    assert settings.log_level is LogLevel.INFO


def test_settings_file_overrides_defaults(tmp_path: Path) -> None:
    (tmp_path / sabitler.SETTINGS_FILE_NAME).write_text(
        'locale = "en"\nlog_level = "DEBUG"\n', encoding="utf-8"
    )
    settings = load_settings(_env(tmp_path))
    assert settings.locale == "en"
    assert settings.log_level is LogLevel.DEBUG


def test_env_overrides_file(tmp_path: Path) -> None:
    (tmp_path / sabitler.SETTINGS_FILE_NAME).write_text(
        'locale = "en"\nlog_level = "DEBUG"\n', encoding="utf-8"
    )
    settings = load_settings(
        _env(tmp_path, **{sabitler.ENV_LOCALE: "de", sabitler.ENV_LOG_LEVEL: "ERROR"})
    )
    assert settings.locale == "de"
    assert settings.log_level is LogLevel.ERROR


def test_invalid_log_level_falls_back_without_crash(tmp_path: Path) -> None:
    (tmp_path / sabitler.SETTINGS_FILE_NAME).write_text(
        'log_level = "verbose"\n', encoding="utf-8"
    )
    settings = load_settings(_env(tmp_path))
    assert settings.log_level is LogLevel.INFO


def test_corrupt_toml_falls_back_to_defaults(tmp_path: Path) -> None:
    (tmp_path / sabitler.SETTINGS_FILE_NAME).write_text(
        "this is = = not toml", encoding="utf-8"
    )
    settings = load_settings(_env(tmp_path))
    assert settings.locale == sabitler.DEFAULT_LOCALE
    assert settings.log_level is LogLevel.INFO


def test_missing_config_dir_does_not_crash(tmp_path: Path) -> None:
    settings = load_settings(_env(tmp_path / "does" / "not" / "exist"))
    assert settings.locale == sabitler.DEFAULT_LOCALE


def test_paths_resolve_from_env_and_derive_log_dir(tmp_path: Path) -> None:
    env = {
        sabitler.ENV_CONFIG_DIR: str(tmp_path / "cfg"),
        sabitler.ENV_DATA_DIR: str(tmp_path / "data"),
        sabitler.ENV_CACHE_DIR: str(tmp_path / "cache"),
    }
    paths = resolve_paths(env)
    assert paths.config_dir == tmp_path / "cfg"
    assert paths.settings_file == tmp_path / "cfg" / sabitler.SETTINGS_FILE_NAME
    assert paths.core_log_dir == tmp_path / "data" / "logs" / "core"


def test_paths_fall_back_when_env_unset() -> None:
    paths = resolve_paths({})
    # Unset vars fall back to XDG-style user dirs, namespaced by the app name.
    assert paths.config_dir.name == sabitler.APP_DIR_NAME
    assert paths.data_dir.name == sabitler.APP_DIR_NAME


def test_corrupt_toml_surfaces_a_warning(tmp_path: Path) -> None:
    """A4: a malformed config file falls back *and* surfaces a warning (doc 33 §13)."""
    (tmp_path / sabitler.SETTINGS_FILE_NAME).write_text(
        "this is = = not toml", encoding="utf-8"
    )
    warnings: list[str] = []
    settings = load_settings(_env(tmp_path), on_warning=warnings.append)
    assert settings.locale == sabitler.DEFAULT_LOCALE
    assert warnings


def test_invalid_log_level_surfaces_a_warning(tmp_path: Path) -> None:
    (tmp_path / sabitler.SETTINGS_FILE_NAME).write_text(
        'log_level = "verbose"\n', encoding="utf-8"
    )
    warnings: list[str] = []
    settings = load_settings(_env(tmp_path), on_warning=warnings.append)
    assert settings.log_level is LogLevel.INFO
    assert any(sabitler.KEY_LOG_LEVEL in w for w in warnings)


def test_wrong_typed_locale_surfaces_a_warning(tmp_path: Path) -> None:
    """A4: a non-string value (e.g. a number) falls back with a warning, no crash."""
    (tmp_path / sabitler.SETTINGS_FILE_NAME).write_text(
        "locale = 5\n", encoding="utf-8"
    )
    warnings: list[str] = []
    settings = load_settings(_env(tmp_path), on_warning=warnings.append)
    assert settings.locale == sabitler.DEFAULT_LOCALE
    assert warnings


def test_clean_config_surfaces_no_warnings(tmp_path: Path) -> None:
    (tmp_path / sabitler.SETTINGS_FILE_NAME).write_text(
        'locale = "en"\nlog_level = "DEBUG"\n', encoding="utf-8"
    )
    warnings: list[str] = []
    load_settings(_env(tmp_path), on_warning=warnings.append)
    assert warnings == []


def test_missing_file_surfaces_no_warnings(tmp_path: Path) -> None:
    """A missing config file is normal (fresh install), not a warnable condition."""
    warnings: list[str] = []
    load_settings(_env(tmp_path), on_warning=warnings.append)
    assert warnings == []
