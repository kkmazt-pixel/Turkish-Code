"""Configuration subsystem (doc 33).

Resolves the effective, typed :class:`~turkish_code.yapilandirma.ayarlar.Settings`
once at boot via :func:`~turkish_code.yapilandirma.yukleyici.load_settings`, and
injects it explicitly into subsystems (doc 33 §9) — no subsystem reads files or
env directly. Stores no secrets (doc 33 §15).
"""

from turkish_code.yapilandirma.ayarlar import Settings
from turkish_code.yapilandirma.yollar import Paths, resolve_paths
from turkish_code.yapilandirma.yukleyici import load_settings

__all__ = ["Settings", "Paths", "resolve_paths", "load_settings"]
