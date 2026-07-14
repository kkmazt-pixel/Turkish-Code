"""Plugin lifecycle (doc 23 §7/§12) — load → enable → disable → unload → reload.

Drives a plugin through its states over the :class:`PluginRegistry`, invoking the
injected activation/deactivation hooks that (from Increment 6) register a
plugin's Tools into the Tool Runtime under its grants. Enable is **atomic**: if
activation fails, the plugin is quarantined ``FAILED`` with nothing
half-registered (fail-safe, doc 23 §11/§12); :meth:`recover` and :meth:`reload`
bring it back. The loader supplies plugins from disk.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from turkish_code.eklentiler.kayit import PluginRegistry
from turkish_code.eklentiler.modeller import PluginState
from turkish_code.eklentiler.protocol import Plugin
from turkish_code.eklentiler.yukleyici import LoadReport, PluginLoader
from turkish_code.hata import AppError

ContributionHook = Callable[[Plugin], None]
"""Activates or deactivates a plugin's contributions — the Tool Runtime bridge."""


def _noop(plugin: Plugin) -> None:
    return None


class PluginLifecycle:
    """Orchestrates plugin state transitions over the registry (doc 23 §7)."""

    def __init__(
        self,
        registry: PluginRegistry,
        loader: PluginLoader,
        *,
        activate: ContributionHook = _noop,
        deactivate: ContributionHook = _noop,
    ) -> None:
        self._registry = registry
        self._loader = loader
        self._activate = activate
        self._deactivate = deactivate

    def load(self, root: Path) -> LoadReport:
        """Discover, validate, and register every plugin under ``root`` (doc 23 §7)."""
        return self._loader.load_directory(root, self._registry)

    def enable(self, plugin_id: str) -> None:
        """Activate the plugin's contributions and mark it ENABLED (doc 23 §7).

        No-op if already enabled. If activation raises, the plugin is quarantined
        FAILED and the error re-raised — contributions are never half-registered
        (doc 23 §11/§12).
        """
        if self._registry.is_enabled(plugin_id):
            return
        plugin = self._registry.resolve(plugin_id)
        try:
            self._activate(plugin)
        except AppError:
            self._registry.mark_failed(plugin_id)
            raise
        self._registry.enable(plugin_id)

    def disable(self, plugin_id: str) -> None:
        """Deactivate the plugin's contributions and mark it DISABLED (doc 23 §7).

        No-op if not currently enabled.
        """
        if not self._registry.is_enabled(plugin_id):
            return
        plugin = self._registry.resolve(plugin_id)
        self._deactivate(plugin)
        self._registry.disable(plugin_id)

    def unload(self, plugin_id: str) -> Plugin:
        """Disable (if enabled) then remove the plugin from the registry (doc 23 §7)."""
        self.disable(plugin_id)
        return self._registry.unload(plugin_id)

    def reload(self, replacement: Plugin) -> None:
        """Swap a registered plugin for a freshly loaded one, preserving its
        enabled state (doc 23 §7 UPDATE). A plugin that was enabled is
        re-activated — so its contributions (and grants, from Increment 6) are
        re-evaluated for the new version.
        """
        plugin_id = replacement.manifest.id
        was_enabled = self._registry.is_enabled(plugin_id)
        if plugin_id in self._registry:
            self.unload(plugin_id)
        self._registry.register(replacement)
        if was_enabled:
            self.enable(plugin_id)

    def recover(self, plugin_id: str) -> None:
        """Reset a FAILED plugin to DISABLED so it can be retried (doc 23 §12).

        A no-op unless the plugin is currently FAILED; clears the quarantine
        without re-activating (the caller re-enables when the cause is fixed).
        """
        if self._registry.state_of(plugin_id) is PluginState.FAILED:
            self._registry.disable(plugin_id)
