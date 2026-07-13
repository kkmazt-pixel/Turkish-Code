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
