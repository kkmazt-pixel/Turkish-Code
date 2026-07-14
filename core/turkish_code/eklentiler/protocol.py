"""The plugin contract (doc 23 §4/§6) — interface only.

:class:`Plugin` is the in-process Runtime API a plugin exposes to the host: its
declarative :class:`~turkish_code.eklentiler.manifest.PluginManifest` and the
:class:`~turkish_code.araclar.protocol.Tool` instances it contributes (doc 23 §5,
this phase supports Tools only). A plugin reaches the rest of the app *only*
through this surface — never Storage, Routing, or any subsystem directly
(doc 23 §6): the host mediates everything. The host depends on this Protocol, not
on concrete plugins (DIP).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from turkish_code.araclar.protocol import Tool
from turkish_code.eklentiler.manifest import PluginManifest


@runtime_checkable
class Plugin(Protocol):
    """A loaded plugin: its manifest plus the Tools it contributes (doc 23 §4/§5)."""

    @property
    def manifest(self) -> PluginManifest:
        """The plugin's declarative manifest (doc 23 §4)."""
        ...

    def tools(self) -> Sequence[Tool]:
        """The Tool contributions this plugin provides (doc 23 §5).

        Plain ``ToolDef``-backed tools (doc 20); the host namespaces and gates
        them — the plugin gets no ambient capability from providing them
        (doc 23 §6).
        """
        ...
