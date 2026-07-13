"""Tests for provider config resolution (doc 33 §12, doc 34 §1)."""

from __future__ import annotations

from pathlib import Path

from turkish_code.yapilandirma import sabitler
from turkish_code.yapilandirma.yukleyici import load_settings


def _env(config_dir: Path, **extra: str) -> dict[str, str]:
    env = {sabitler.ENV_CONFIG_DIR: str(config_dir)}
    env.update(extra)
    return env


def test_unconfigured_provider_is_not_configured(tmp_path: Path) -> None:
    settings = load_settings(_env(tmp_path))
    assert settings.providers.gemini.is_configured is False
    assert settings.providers.gemini.api_key is None


def test_provider_becomes_configured_when_both_set(tmp_path: Path) -> None:
    env = _env(
        tmp_path,
        **{
            sabitler.ENV_GEMINI_API_KEY: "secret",
            sabitler.ENV_GEMINI_BASE_URL: "https://example.test",
        },
    )
    settings = load_settings(env)
    assert settings.providers.gemini.is_configured is True
    assert settings.providers.gemini.api_key == "secret"


def test_key_without_base_url_is_not_configured(tmp_path: Path) -> None:
    env = _env(tmp_path, **{sabitler.ENV_GROQ_API_KEY: "secret"})
    settings = load_settings(env)
    assert settings.providers.groq.is_configured is False


def test_ollama_has_a_default_base_url(tmp_path: Path) -> None:
    settings = load_settings(_env(tmp_path))
    assert settings.providers.ollama_base_url == sabitler.DEFAULT_OLLAMA_BASE_URL


def test_ollama_base_url_is_overridable(tmp_path: Path) -> None:
    env = _env(tmp_path, **{sabitler.ENV_OLLAMA_BASE_URL: "http://192.168.1.5:11434"})
    settings = load_settings(env)
    assert settings.providers.ollama_base_url == "http://192.168.1.5:11434"


def test_default_cost_mode_is_balanced(tmp_path: Path) -> None:
    settings = load_settings(_env(tmp_path))
    assert settings.providers.default_cost_mode == "balanced"


def test_cost_mode_is_case_insensitive(tmp_path: Path) -> None:
    env = _env(tmp_path, **{sabitler.ENV_COST_MODE: "ECONOMY"})
    settings = load_settings(env)
    assert settings.providers.default_cost_mode == "economy"


def test_invalid_cost_mode_falls_back_with_warning(tmp_path: Path) -> None:
    env = _env(tmp_path, **{sabitler.ENV_COST_MODE: "ultra-mode"})
    warnings: list[str] = []
    settings = load_settings(env, on_warning=warnings.append)
    assert settings.providers.default_cost_mode == "balanced"
    assert warnings
