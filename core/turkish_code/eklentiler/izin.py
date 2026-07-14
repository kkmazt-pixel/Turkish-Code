"""Plugin permission integration (doc 23 §6) — grants, bridge, gate.

The security core: a plugin gets **zero** capability until the user grants it,
and every plugin tool call must satisfy **both** the plugin's grant *and* the
session permission mode — least privilege by intersection (doc 23 §6/§19 #2).

- :class:`PluginGrantStore` records what the user approved per plugin (default:
  nothing).
- :class:`PluginToolBridge` registers an enabled plugin's Tools into the Tool
  Runtime, namespaced ``<plugin-id>/<tool>`` (doc 23 §8), atomically.
- :class:`PluginPermissionGate` wraps the session gate: for a plugin tool it
  first denies any capability the plugin wasn't granted, then defers to the
  session decision — so grant ∩ session both hold.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.izin import (
    Decision,
    Deny,
    PermissionGate,
    PermissionRequest,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.modeller import (
    Capability,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from turkish_code.araclar.protocol import Tool
from turkish_code.eklentiler.modeller import (
    FsAccess,
    NetAccess,
    RequestedCapabilities,
    ShellAccess,
)
from turkish_code.eklentiler.protocol import Plugin
from turkish_code.hata import AppError


def namespaced_name(plugin_id: str, tool_name: str) -> str:
    """The registry name for a plugin's tool: ``<plugin-id>/<tool>`` (doc 23 §8)."""
    return f"{plugin_id}/{tool_name}"


def plugin_id_of(tool_name: str) -> str | None:
    """The plugin id namespacing ``tool_name``, or ``None`` for a first-party tool."""
    prefix, sep, _ = tool_name.partition("/")
    return prefix if sep else None


def grant_covers(capabilities: RequestedCapabilities, capability: Capability) -> bool:
    """Whether ``capabilities`` (what the user granted) permits ``capability``.

    ``fs.write`` implies ``fs.read``; capabilities a plugin cannot even declare
    (open.external/secret.use/workspace.switch, doc 23 §4) are never covered —
    least privilege (doc 23 §6).
    """
    match capability:
        case Capability.FS_READ:
            return capabilities.fs in (FsAccess.READ, FsAccess.WRITE)
        case Capability.FS_WRITE:
            return capabilities.fs is FsAccess.WRITE
        case Capability.SHELL_EXEC:
            return capabilities.shell is ShellAccess.EXEC
        case Capability.NET_EGRESS:
            return capabilities.net is NetAccess.EGRESS
        case _:
            return False


class PluginGrantStore:
    """Per-plugin capability grants (doc 23 §6/§8) — the user's approvals.

    A plugin with no recorded grant has none (least privilege by default,
    doc 23 §3/§9); the composition records the user's decision here.
    """

    def __init__(self) -> None:
        self._grants: dict[str, RequestedCapabilities] = {}

    def grant(self, plugin_id: str, capabilities: RequestedCapabilities) -> None:
        """Record the capabilities the user approved for ``plugin_id``."""
        self._grants[plugin_id] = capabilities

    def revoke(self, plugin_id: str) -> None:
        """Remove all grants for ``plugin_id`` (doc 23 §7 DISABLE/UNINSTALL)."""
        self._grants.pop(plugin_id, None)

    def granted(self, plugin_id: str) -> RequestedCapabilities:
        """The capabilities granted to ``plugin_id`` — ``none`` if unrecorded."""
        return self._grants.get(plugin_id, RequestedCapabilities())

    def covers(self, plugin_id: str, capability: Capability) -> bool:
        """Whether ``plugin_id`` is granted ``capability`` (doc 23 §6)."""
        return grant_covers(self.granted(plugin_id), capability)


class PluginPermissionGate:
    """A :class:`PermissionGate` enforcing grant ∩ session for plugin tools.

    Wraps the base session gate: a plugin tool (namespaced name) is denied
    outright if the plugin lacks the required capability grant; otherwise the
    base session decision stands (doc 23 §6). First-party tools pass straight to
    the base gate.
    """

    def __init__(self, base: PermissionGate, grants: PluginGrantStore) -> None:
        self._base = base
        self._grants = grants

    async def evaluate(self, request: PermissionRequest) -> Decision:
        plugin_id = plugin_id_of(request.tool)
        if (
            plugin_id is not None
            and request.capability is not None
            and not self._grants.covers(plugin_id, request.capability)
        ):
            return Deny(f"plugin {plugin_id!r} not granted {request.capability.value}")
        return await self._base.evaluate(request)


class PluginToolBridge:
    """Registers an enabled plugin's Tools into the Tool Runtime (doc 23 §5/§7)."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def activate(self, plugin: Plugin) -> None:
        """Register the plugin's Tools, namespaced, atomically (doc 23 §7/§8).

        If any tool collides, the already-registered ones are rolled back and
        the error re-raised — so a failed enable leaves nothing half-registered
        (doc 23 §11/§12).
        """
        plugin_id = plugin.manifest.id
        registered: list[str] = []
        try:
            for tool in plugin.tools():
                wrapped = _NamespacedTool(plugin_id, tool)
                self._registry.register(wrapped)
                registered.append(wrapped.metadata.name)
        except AppError:
            for name in registered:
                self._registry.unregister(name)
            raise

    def deactivate(self, plugin: Plugin) -> None:
        """Withdraw the plugin's namespaced Tools from the runtime (doc 23 §7)."""
        plugin_id = plugin.manifest.id
        for tool in plugin.tools():
            self._registry.unregister(namespaced_name(plugin_id, tool.metadata.name))


class _NamespacedTool:
    """Wraps a plugin :class:`Tool` so its registry name is plugin-namespaced."""

    def __init__(self, plugin_id: str, tool: Tool) -> None:
        self._tool = tool
        self._metadata = replace(
            tool.metadata,
            name=namespaced_name(plugin_id, tool.metadata.name),
        )

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return await self._tool.execute(request, context)


def granted_tool_names(plugin: Plugin) -> Sequence[str]:
    """The namespaced names a plugin's tools take in the runtime (doc 23 §8)."""
    plugin_id = plugin.manifest.id
    return [namespaced_name(plugin_id, tool.metadata.name) for tool in plugin.tools()]
