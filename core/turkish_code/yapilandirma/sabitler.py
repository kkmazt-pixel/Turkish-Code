"""Configuration constants: env-var names and shipped defaults (doc 33).

Centralized so nothing elsewhere hardcodes a magic string or default (doc 36
§3). Adding a key here is additive and safe (doc 33 §23).
"""

from __future__ import annotations

from typing import Final

from turkish_code.ortak.seviye import LogLevel

# --- Environment variable names ------------------------------------------------
# The Kabuk passes boot parameters (paths, locale, log config) to the Çekirdek
# via the environment at spawn (doc 09 §5). One shared prefix keeps them namespaced.
ENV_PREFIX: Final = "TURKISH_CODE_"
ENV_CONFIG_DIR: Final = f"{ENV_PREFIX}CONFIG_DIR"
ENV_DATA_DIR: Final = f"{ENV_PREFIX}DATA_DIR"
ENV_CACHE_DIR: Final = f"{ENV_PREFIX}CACHE_DIR"
ENV_LOCALE: Final = f"{ENV_PREFIX}LOCALE"
ENV_LOG_LEVEL: Final = f"{ENV_PREFIX}LOG_LEVEL"
ENV_CORE_SESSION_TOKEN: Final = f"{ENV_PREFIX}CORE_SESSION_TOKEN"
"""Per-session capability token (doc 10 §12), passed at spawn and echoed back
in ``app.handshake`` — defends against a stray process attaching to a leaked
pipe. Not a user secret; never logged, never sent to the Arayüz."""

# --- Provider credentials & endpoints (doc 34 §1/§3 — light key handling:
# outside source code, in env, loaded at startup; never in settings.toml so a
# key can never end up in a config file a user might share/commit). ----------
ENV_GEMINI_API_KEY: Final = f"{ENV_PREFIX}GEMINI_API_KEY"
ENV_GEMINI_BASE_URL: Final = f"{ENV_PREFIX}GEMINI_BASE_URL"
ENV_GROQ_API_KEY: Final = f"{ENV_PREFIX}GROQ_API_KEY"
ENV_GROQ_BASE_URL: Final = f"{ENV_PREFIX}GROQ_BASE_URL"
ENV_OPENROUTER_API_KEY: Final = f"{ENV_PREFIX}OPENROUTER_API_KEY"
ENV_OPENROUTER_BASE_URL: Final = f"{ENV_PREFIX}OPENROUTER_BASE_URL"
ENV_NVIDIA_NIM_API_KEY: Final = f"{ENV_PREFIX}NVIDIA_NIM_API_KEY"
ENV_NVIDIA_NIM_BASE_URL: Final = f"{ENV_PREFIX}NVIDIA_NIM_BASE_URL"
ENV_OLLAMA_BASE_URL: Final = f"{ENV_PREFIX}OLLAMA_BASE_URL"
ENV_COST_MODE: Final = f"{ENV_PREFIX}COST_MODE"

DEFAULT_OLLAMA_BASE_URL: Final = "http://localhost:11434"
"""Ollama's own documented local default (doc 22 §5.5) — safe to default since
it addresses a daemon the user runs on their own machine, unlike the cloud
providers, which have no hardcoded base URL and must be configured."""

# Valid cost/quota mode strings (doc 17 §4b) — kept as raw strings here (not
# the yonlendirme.mod.CostMode enum) so this leaf module never depends on the
# routing layer; the composition root converts/validates at the boundary.
VALID_COST_MODES: Final[frozenset[str]] = frozenset(
    {"performance", "balanced", "economy"}
)
DEFAULT_COST_MODE: Final = "balanced"

# --- On-disk names (doc 33 §7, doc 39 §7) -------------------------------------
SETTINGS_FILE_NAME: Final = "settings.toml"
CORE_LOG_SUBDIR: Final[tuple[str, ...]] = ("logs", "core")
APP_DIR_NAME: Final = "turkish-code"  # standalone-dev fallback dir name

# --- Shipped defaults (doc 33 §8 — privacy-strongest, Turkish-native) ---------
DEFAULT_LOCALE: Final = "tr"
DEFAULT_LOG_LEVEL: Final = LogLevel.INFO

# --- TOML keys read by the loader (doc 33 §6) ---------------------------------
KEY_LOCALE: Final = "locale"
KEY_LOG_LEVEL: Final = "log_level"
