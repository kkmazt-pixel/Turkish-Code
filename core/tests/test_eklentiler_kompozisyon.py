"""Tests for plugin-runtime composition + container wiring (doc 23 §8, doc 09 §7)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.modeller import (
    Capability,
    SideEffect,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from turkish_code.araclar.protocol import Tool
from turkish_code.eklentiler.izin import PluginGrantStore
from turkish_code.eklentiler.kompozisyon import PluginRuntime, build_plugin_runtime
from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import (
    FsAccess,
    PluginState,
    RequestedCapabilities,
)


class _ReadTool:
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="lint_check",
            summary="lint",
            capability=Capability.FS_READ,
            side_effect=SideEffect.READ,
            brokered=True,
            reversible=False,
            idempotent=True,
            timeout_ms=1000,
        )

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output="linted")


def _provider(manifest: PluginManifest) -> Sequence[Tool]:
    return [_ReadTool()]


def _write_plugin(root: Path) -> None:
    plugin_dir = root / "lint"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.toml").write_text(
        '[plugin]\nid = "org.example.lint"\nname = "Lint"\nversion = "1.0.0"\n'
        'min_app_version = "0.0.0"\n\n[contributes]\ntools = ["tools/lint_check"]\n'
        '\n[capabilities-requested]\nfs = "read"\n',
        encoding="utf-8",
    )


def test_build_returns_wired_graph() -> None:
    runtime = build_plugin_runtime(
        ToolRegistry(), PluginGrantStore(), app_version="1.0.0"
    )
    assert isinstance(runtime, PluginRuntime)
    assert len(runtime.registry) == 0  # nothing loaded


def test_lifecycle_bridges_into_the_given_tool_registry() -> None:
    tool_registry = ToolRegistry()
    runtime = build_plugin_runtime(
        tool_registry, PluginGrantStore(), app_version="1.0.0"
    )

    class _P:
        @property
        def manifest(self) -> PluginManifest:
            return PluginManifest(
                id="org.a.p", name="P", version="1.0.0", min_app_version="0.0.0"
            )

        def tools(self) -> Sequence[Tool]:
            return [_ReadTool()]

    runtime.registry.register(_P())
    runtime.lifecycle.enable("org.a.p")
    # The bridge registered the plugin's tool into the shared Tool Runtime registry.
    assert "org.a.p/lint_check" in tool_registry


@pytest.mark.asyncio
async def test_end_to_end_load_grant_enable_dispatch(tmp_path: Path) -> None:
    from turkish_code.araclar.dagitici import ToolDispatcher
    from turkish_code.araclar.izin import (
        PermissionMode,
        PermissionPolicy,
        PolicyPermissionGate,
    )
    from turkish_code.eklentiler.izin import PluginPermissionGate

    _write_plugin(tmp_path)
    tool_registry = ToolRegistry()
    grants = PluginGrantStore()
    runtime = build_plugin_runtime(
        tool_registry, grants, app_version="1.0.0", tool_provider=_provider
    )
    gate = PluginPermissionGate(
        PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO)), grants
    )
    dispatcher = ToolDispatcher(tool_registry, gate)

    # 1. load from disk
    report = runtime.lifecycle.load(tmp_path)
    assert report.loaded == ("org.example.lint",)

    # 2. user grants the requested capability
    grants.grant("org.example.lint", RequestedCapabilities(fs=FsAccess.READ))

    # 3. enable → the tool is bridged in, namespaced
    runtime.lifecycle.enable("org.example.lint")
    assert runtime.registry.state_of("org.example.lint") is PluginState.ENABLED
    assert "org.example.lint/lint_check" in tool_registry

    # 4. dispatch the plugin tool end to end
    result = await dispatcher.dispatch(
        ToolRequest(name="org.example.lint/lint_check", arguments={}, call_id="c1")
    )
    assert result.output == "linted"

    # 5. disable → the tool is withdrawn
    runtime.lifecycle.disable("org.example.lint")
    assert "org.example.lint/lint_check" not in tool_registry


def test_container_exposes_plugin_runtime_sharing_tool_gate() -> None:
    from turkish_code.kompozisyon import build_container
    from turkish_code.yapilandirma.yukleyici import load_settings

    container = build_container(load_settings(environ={}))
    assert isinstance(container.plugin_runtime, PluginRuntime)
    assert len(container.plugin_runtime.registry) == 0
    # The plugin bridge targets the container's Tool Runtime registry.
    assert container.plugin_runtime.bridge is not None
    assert isinstance(container.tool_runtime.registry, ToolRegistry)


@pytest.mark.asyncio
async def test_container_grant_store_gates_plugin_tools() -> None:
    from turkish_code.eklentiler.izin import PluginToolBridge
    from turkish_code.hata import AppError
    from turkish_code.kompozisyon import build_container
    from turkish_code.yapilandirma.yukleyici import load_settings

    container = build_container(load_settings(environ={}))

    # Bridge a plugin tool into the container's Tool Runtime by hand.
    class _P:
        @property
        def manifest(self) -> PluginManifest:
            return PluginManifest(
                id="org.x.p", name="P", version="1.0.0", min_app_version="0.0.0"
            )

        def tools(self) -> Sequence[Tool]:
            return [_ReadTool()]

    PluginToolBridge(container.tool_runtime.registry).activate(_P())
    # No grant recorded → the container's plugin-aware gate denies it.
    with pytest.raises(AppError):
        await container.tool_runtime.dispatcher.dispatch(
            ToolRequest(name="org.x.p/lint_check", arguments={}, call_id="c1")
        )
