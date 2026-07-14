"""Eklentiler — the Plugin System host (doc 23).

The container/format/lifecycle by which third-party extensions add capabilities
to turkish.code. This phase scopes contributions to Tools (doc 20) and builds the
host only: manifest + validation, registry, loader, lifecycle, permission
integration, and the bridge into the Tool Runtime — no marketplace, remote
install, UI, or code sandbox. Plugins are **untrusted by default**: zero
capability until the user grants it, and every effect still flows through the
permissioned tool path (doc 23 §3/§6). The host depends only on the
:class:`Plugin` Protocol (DIP).
"""

from turkish_code.eklentiler.dogrulama import (
    PLUGIN_INCOMPATIBLE_CODE,
    PLUGIN_INVALID_ID_CODE,
    PLUGIN_INVALID_MANIFEST_CODE,
    PLUGIN_INVALID_VERSION_CODE,
    declared_capabilities,
    parse_semver,
    validate_manifest,
)
from turkish_code.eklentiler.izin import (
    PluginGrantStore,
    PluginPermissionGate,
    PluginToolBridge,
    grant_covers,
    granted_tool_names,
    namespaced_name,
    plugin_id_of,
)
from turkish_code.eklentiler.kayit import (
    PLUGIN_DUPLICATE_CODE,
    PLUGIN_NOT_FOUND_CODE,
    PluginRegistry,
)
from turkish_code.eklentiler.kompozisyon import PluginRuntime, build_plugin_runtime
from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import (
    Contributions,
    FsAccess,
    NetAccess,
    PluginRuntimeKind,
    PluginState,
    RequestedCapabilities,
    ShellAccess,
)
from turkish_code.eklentiler.protocol import Plugin
from turkish_code.eklentiler.yasam import ContributionHook, PluginLifecycle
from turkish_code.eklentiler.yukleyici import (
    MANIFEST_NAME,
    PLUGIN_MANIFEST_READ_CODE,
    LoadedPlugin,
    LoadFailure,
    LoadReport,
    PluginLoader,
    ToolProvider,
)

__all__ = [
    "Plugin",
    "PluginManifest",
    "PluginState",
    "PluginRuntimeKind",
    "Contributions",
    "RequestedCapabilities",
    "FsAccess",
    "NetAccess",
    "ShellAccess",
    "validate_manifest",
    "declared_capabilities",
    "parse_semver",
    "PLUGIN_INVALID_VERSION_CODE",
    "PLUGIN_INCOMPATIBLE_CODE",
    "PLUGIN_INVALID_ID_CODE",
    "PLUGIN_INVALID_MANIFEST_CODE",
    "PluginRegistry",
    "PLUGIN_DUPLICATE_CODE",
    "PLUGIN_NOT_FOUND_CODE",
    "PluginLoader",
    "LoadedPlugin",
    "LoadReport",
    "LoadFailure",
    "ToolProvider",
    "MANIFEST_NAME",
    "PLUGIN_MANIFEST_READ_CODE",
    "PluginLifecycle",
    "ContributionHook",
    "PluginGrantStore",
    "PluginPermissionGate",
    "PluginToolBridge",
    "grant_covers",
    "granted_tool_names",
    "namespaced_name",
    "plugin_id_of",
    "PluginRuntime",
    "build_plugin_runtime",
]
