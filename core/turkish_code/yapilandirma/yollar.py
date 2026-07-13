"""On-disk path resolution (doc 33 §7).

Paths are supplied by the Kabuk via the environment at spawn (doc 09 §5). When a
variable is unset — e.g. the Çekirdek is run standalone in dev/tests before the
Kabuk exists — we fall back to XDG-style user directories. No secrets live here
(doc 33 §15).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from turkish_code.yapilandirma import sabitler


@dataclass(frozen=True, slots=True)
class Paths:
    """Resolved application directories (doc 33 §7)."""

    config_dir: Path
    data_dir: Path
    cache_dir: Path

    @property
    def settings_file(self) -> Path:
        """The app/global ``settings.toml`` (doc 33 §7, layer 2)."""
        return self.config_dir / sabitler.SETTINGS_FILE_NAME

    @property
    def core_log_dir(self) -> Path:
        """Directory for Çekirdek log files: ``DATA_DIR/logs/core`` (doc 39 §7)."""
        return self.data_dir.joinpath(*sabitler.CORE_LOG_SUBDIR)


def resolve_paths(environ: Mapping[str, str]) -> Paths:
    """Resolve :class:`Paths` from the given environment mapping (doc 09 §5).

    Explicit-input (the environment is passed, not read from a global) so path
    resolution is deterministic and unit-testable.
    """
    config_dir = _dir(
        environ, sabitler.ENV_CONFIG_DIR, _xdg(environ, "XDG_CONFIG_HOME", ".config")
    )
    data_dir = _dir(
        environ, sabitler.ENV_DATA_DIR, _xdg(environ, "XDG_DATA_HOME", ".local/share")
    )
    cache_dir = _dir(
        environ, sabitler.ENV_CACHE_DIR, _xdg(environ, "XDG_CACHE_HOME", ".cache")
    )
    return Paths(config_dir=config_dir, data_dir=data_dir, cache_dir=cache_dir)


def _dir(environ: Mapping[str, str], key: str, fallback: Path) -> Path:
    """Return the env-provided dir for ``key`` if set and non-empty, else fallback."""
    value = environ.get(key, "").strip()
    return Path(value) if value else fallback


def _xdg(environ: Mapping[str, str], xdg_key: str, default_rel: str) -> Path:
    """XDG base dir (or ``~/<default_rel>``) joined with the app dir name."""
    base = environ.get(xdg_key, "").strip()
    root = Path(base) if base else Path(os.path.expanduser("~")) / default_rel
    return root / sabitler.APP_DIR_NAME
