"""Settings loader and layered precedence (doc 33 §4).

Effective value = later layers override earlier:

    built-in defaults  <  app config (settings.toml)  <  environment (Kabuk boot)

The environment layer carries the boot parameters the Kabuk resolved and passed
at spawn (doc 09 §5). Loading never crashes on a bad file or value: each key
falls back to its default with the rest intact (doc 33 §13/§14).

Because the loader runs *before* the logger exists (the logger needs the
resolved settings), fallbacks are surfaced through an optional ``on_warning``
callback rather than logged directly — the caller (composition root) can route
these to the logger once it is built (doc 33 §13).
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from turkish_code.ortak.seviye import LogLevel
from turkish_code.yapilandirma import sabitler
from turkish_code.yapilandirma.ayarlar import Settings
from turkish_code.yapilandirma.saglayicilar import ProviderCredentials, ProvidersConfig
from turkish_code.yapilandirma.yollar import resolve_paths
from turkish_code.yapilandirma.zeka import (
    EmbeddingConfig,
    GraphConfig,
    MemoryConfig,
    RetrievalConfig,
)

WarningSink = Callable[[str], None]
"""Receives a human-readable message when config resolution falls back (doc 33 §13)."""


def load_settings(
    environ: Mapping[str, str], *, on_warning: WarningSink | None = None
) -> Settings:
    """Resolve :class:`Settings` from defaults, ``settings.toml`` and ``environ``.

    The environment is passed explicitly (never read from a global) so the whole
    resolution is deterministic and unit-testable (doc 33 §17). ``on_warning``, if
    given, is called for each key that fell back due to a bad file or value
    (doc 33 §13); when omitted, fallbacks are silent as before.
    """
    warn: WarningSink = on_warning if on_warning is not None else _ignore
    paths = resolve_paths(environ)
    file_values = _read_settings_file(paths.settings_file, warn)
    return Settings(
        locale=_resolve_locale(environ, file_values, warn),
        log_level=_resolve_log_level(environ, file_values, warn),
        paths=paths,
        providers=_resolve_providers(environ, warn),
        # Intelligence-layer config is schema-only today (doc 11/12/13/14) — no
        # consumer exists yet, so defaults are used until one needs overrides.
        memory=MemoryConfig(),
        graph=GraphConfig(),
        retrieval=RetrievalConfig(),
        embedding=EmbeddingConfig(),
    )


def _ignore(_message: str) -> None:
    """Default no-op warning sink (preserves the silent-fallback behavior)."""


def _read_settings_file(path: Path, warn: WarningSink) -> Mapping[str, Any]:
    """Parse ``settings.toml`` if present; return ``{}`` on absence or bad TOML.

    A missing file is normal (fresh install → all defaults) and is silent; an
    unreadable or malformed file is a surfaced fallback, never a crash (doc 33 §14).
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {}
    except OSError as exc:
        warn(f"settings file could not be read ({path}): {exc}")
        return {}
    try:
        return tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        warn(f"settings file is not valid TOML ({path}): {exc}")
        return {}


def _resolve_locale(
    environ: Mapping[str, str], file_values: Mapping[str, Any], warn: WarningSink
) -> str:
    """Locale from env > file > default; blank/invalid falls back (doc 33 §13)."""
    env_value = environ.get(sabitler.ENV_LOCALE, "").strip()
    if env_value:
        return env_value
    file_value = file_values.get(sabitler.KEY_LOCALE)
    if isinstance(file_value, str) and file_value.strip():
        return file_value.strip()
    if file_value is not None:
        warn(
            f"invalid {sabitler.KEY_LOCALE} in settings.toml: "
            f"{file_value!r}; using default"
        )
    return sabitler.DEFAULT_LOCALE


def _resolve_log_level(
    environ: Mapping[str, str], file_values: Mapping[str, Any], warn: WarningSink
) -> LogLevel:
    """Log level from env > file > default; unknown value falls back (doc 33 §13)."""
    env_value = environ.get(sabitler.ENV_LOG_LEVEL, "").strip()
    if env_value:
        return _parse_level(env_value, warn, source="environment")
    file_value = file_values.get(sabitler.KEY_LOG_LEVEL)
    if isinstance(file_value, str):
        return _parse_level(file_value, warn, source="settings.toml")
    if file_value is not None:
        warn(
            f"{sabitler.KEY_LOG_LEVEL} in settings.toml must be a string, "
            f"got {type(file_value).__name__}; using default"
        )
    return sabitler.DEFAULT_LOG_LEVEL


def _parse_level(name: str, warn: WarningSink, *, source: str) -> LogLevel:
    try:
        return LogLevel.from_name(name)
    except ValueError:
        warn(f"unknown {sabitler.KEY_LOG_LEVEL} {name!r} from {source}; using default")
        return sabitler.DEFAULT_LOG_LEVEL


def _resolve_providers(
    environ: Mapping[str, str], warn: WarningSink
) -> ProvidersConfig:
    """Provider credentials/endpoints from env only (doc 34 §1), never TOML."""
    return ProvidersConfig(
        gemini=_credentials(
            environ, sabitler.ENV_GEMINI_API_KEY, sabitler.ENV_GEMINI_BASE_URL
        ),
        groq=_credentials(
            environ, sabitler.ENV_GROQ_API_KEY, sabitler.ENV_GROQ_BASE_URL
        ),
        openrouter=_credentials(
            environ, sabitler.ENV_OPENROUTER_API_KEY, sabitler.ENV_OPENROUTER_BASE_URL
        ),
        nvidia_nim=_credentials(
            environ, sabitler.ENV_NVIDIA_NIM_API_KEY, sabitler.ENV_NVIDIA_NIM_BASE_URL
        ),
        ollama_base_url=_non_empty(environ, sabitler.ENV_OLLAMA_BASE_URL)
        or sabitler.DEFAULT_OLLAMA_BASE_URL,
        default_cost_mode=_resolve_cost_mode(environ, warn),
    )


def _credentials(
    environ: Mapping[str, str], key_var: str, base_url_var: str
) -> ProviderCredentials:
    return ProviderCredentials(
        api_key=_non_empty(environ, key_var), base_url=_non_empty(environ, base_url_var)
    )


def _non_empty(environ: Mapping[str, str], key: str) -> str | None:
    value = environ.get(key, "").strip()
    return value or None


def _resolve_cost_mode(environ: Mapping[str, str], warn: WarningSink) -> str:
    value = environ.get(sabitler.ENV_COST_MODE, "").strip().lower()
    if not value:
        return sabitler.DEFAULT_COST_MODE
    if value not in sabitler.VALID_COST_MODES:
        warn(f"unknown {sabitler.ENV_COST_MODE} {value!r}; using default")
        return sabitler.DEFAULT_COST_MODE
    return value
