"""Plugin-runtime composition (doc 23 §8, doc 09 §7) — wire the host graph.

Assembles the plugin host from its parts and connects it to the Tool Runtime: a
:class:`PluginRegistry`, a :class:`PluginLoader`, the :class:`PluginGrantStore`
(shared with the Tool Runtime's :class:`PluginPermissionGate` so grant ∩ session
holds), the :class:`PluginToolBridge` that registers enabled plugins' Tools into
the *given* Tool Runtime registry, and the :class:`PluginLifecycle` bound to the
bridge. Pure construction by explicit injection — no import-time side effects, no
singletons (PR-9). No plugins are loaded or enabled here (doc 23 §9).
"""

from __future__ import annotations

from dataclasses import dataclass

from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.eklentiler.izin import PluginGrantStore, PluginToolBridge
from turkish_code.eklentiler.kayit import PluginRegistry
from turkish_code.eklentiler.yasam import PluginLifecycle
from turkish_code.eklentiler.yukleyici import PluginLoader, ToolProvider


@dataclass(frozen=True, slots=True)
class PluginRuntime:
    """The wired plugin host (doc 23 §8): registry, loader, grants, bridge, life."""

    registry: PluginRegistry
    loader: PluginLoader
    grants: PluginGrantStore
    bridge: PluginToolBridge
    lifecycle: PluginLifecycle


def build_plugin_runtime(
    tool_registry: ToolRegistry,
    grants: PluginGrantStore,
    *,
    app_version: str,
    tool_provider: ToolProvider | None = None,
) -> PluginRuntime:
    """Assemble the plugin host, bridged into ``tool_registry`` (doc 23 §7/§8).

    ``grants`` is shared with the Tool Runtime's permission gate so a plugin
    tool call is checked against both its grant and the session (doc 23 §6).
    ``tool_provider`` is the sandbox seam that resolves a manifest to its Tools;
    omitted, plugins contribute no tools (host-only, doc 23 §6).
    """
    registry = PluginRegistry()
    loader = (
        PluginLoader(app_version=app_version, tool_provider=tool_provider)
        if tool_provider is not None
        else PluginLoader(app_version=app_version)
    )
    bridge = PluginToolBridge(tool_registry)
    lifecycle = PluginLifecycle(
        registry, loader, activate=bridge.activate, deactivate=bridge.deactivate
    )
    return PluginRuntime(
        registry=registry,
        loader=loader,
        grants=grants,
        bridge=bridge,
        lifecycle=lifecycle,
    )
