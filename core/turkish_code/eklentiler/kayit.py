"""Plugin registry (doc 23 §8) — tracks installed plugins, state, contributions.

Holds every registered plugin keyed by its manifest id, with its lifecycle
:class:`PluginState` (doc 23 §7). Registration is **fail-safe**: a duplicate id
is rejected so two plugins can never share a namespace (doc 23 §8/§11). The
registry owns the state transitions (enable/disable/unload/mark-failed) but not
their *effects* — registering an enabled plugin's Tools into the Tool Runtime is
the lifecycle/bridge job (doc 23 §7). Nothing is enabled by default (doc 23 §9).
"""

from __future__ import annotations

from dataclasses import dataclass

from turkish_code.eklentiler.modeller import PluginState
from turkish_code.eklentiler.protocol import Plugin
from turkish_code.hata import AppError, ErrorKind

PLUGIN_DUPLICATE_CODE = "plugin.duplicate"
PLUGIN_NOT_FOUND_CODE = "plugin.not_found"


@dataclass(slots=True)
class _Entry:
    plugin: Plugin
    state: PluginState


class PluginRegistry:
    """An in-memory id→plugin registry with lifecycle state (doc 23 §8)."""

    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    def register(self, plugin: Plugin) -> None:
        """Register ``plugin`` as DISABLED; reject a duplicate id (doc 23 §8/§11)."""
        plugin_id = plugin.manifest.id
        if plugin_id in self._entries:
            raise _duplicate(plugin_id)
        self._entries[plugin_id] = _Entry(plugin=plugin, state=PluginState.DISABLED)

    def get(self, plugin_id: str) -> Plugin | None:
        """The registered plugin, or ``None`` if absent."""
        entry = self._entries.get(plugin_id)
        return entry.plugin if entry is not None else None

    def resolve(self, plugin_id: str) -> Plugin:
        """The registered plugin, or raise ``plugin.not_found`` (doc 23 §8)."""
        return self._entry(plugin_id).plugin

    def state_of(self, plugin_id: str) -> PluginState:
        """The plugin's lifecycle state, or raise ``plugin.not_found``."""
        return self._entry(plugin_id).state

    def is_enabled(self, plugin_id: str) -> bool:
        """Whether the plugin is registered and ENABLED."""
        entry = self._entries.get(plugin_id)
        return entry is not None and entry.state is PluginState.ENABLED

    def enable(self, plugin_id: str) -> Plugin:
        """Mark the plugin ENABLED and return it (doc 23 §7)."""
        entry = self._entry(plugin_id)
        entry.state = PluginState.ENABLED
        return entry.plugin

    def disable(self, plugin_id: str) -> Plugin:
        """Mark the plugin DISABLED and return it (doc 23 §7)."""
        entry = self._entry(plugin_id)
        entry.state = PluginState.DISABLED
        return entry.plugin

    def mark_failed(self, plugin_id: str) -> None:
        """Quarantine the plugin as FAILED after a lifecycle error (doc 23 §12)."""
        self._entry(plugin_id).state = PluginState.FAILED

    def unload(self, plugin_id: str) -> Plugin:
        """Remove the plugin from the registry and return it (doc 23 §7)."""
        entry = self._entry(plugin_id)
        del self._entries[plugin_id]
        return entry.plugin

    def ids(self) -> list[str]:
        """All registered plugin ids, sorted."""
        return sorted(self._entries)

    def enabled(self) -> list[Plugin]:
        """Every ENABLED plugin, id-sorted — the active contribution set."""
        return [
            self._entries[pid].plugin
            for pid in sorted(self._entries)
            if self._entries[pid].state is PluginState.ENABLED
        ]

    def __contains__(self, plugin_id: object) -> bool:
        return isinstance(plugin_id, str) and plugin_id in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def _entry(self, plugin_id: str) -> _Entry:
        entry = self._entries.get(plugin_id)
        if entry is None:
            raise _not_found(plugin_id)
        return entry


def _duplicate(plugin_id: str) -> AppError:
    return AppError(
        kind=ErrorKind.CONFLICT,
        code=PLUGIN_DUPLICATE_CODE,
        message_key=f"hata.{PLUGIN_DUPLICATE_CODE}",
        retryable=False,
        detail=f"a plugin is already registered as {plugin_id!r}",
        context={"plugin": plugin_id},
    )


def _not_found(plugin_id: str) -> AppError:
    return AppError(
        kind=ErrorKind.NOT_FOUND,
        code=PLUGIN_NOT_FOUND_CODE,
        message_key=f"hata.{PLUGIN_NOT_FOUND_CODE}",
        retryable=False,
        detail=f"no plugin registered as {plugin_id!r}",
        context={"plugin": plugin_id},
    )
