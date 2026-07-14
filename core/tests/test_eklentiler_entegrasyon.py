"""End-to-end integration tests for the plugin system (doc 23).

Drives the whole host — loader → registry → lifecycle → permission → Tool Runtime
— through :func:`build_plugin_runtime`, covering the edge cases the per-module
unit tests don't: broken manifests amid good ones, grant ∩ session denial,
reload, duplicate plugins, and colliding tools.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.hata import TOOL_DENIED_CODE, TOOL_NOT_FOUND_CODE
from turkish_code.araclar.izin import (
    PermissionMode,
    PermissionPolicy,
    PolicyPermissionGate,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.modeller import (
    Capability,
    SideEffect,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from turkish_code.araclar.protocol import Tool
from turkish_code.eklentiler.izin import PluginGrantStore, PluginPermissionGate
from turkish_code.eklentiler.kompozisyon import PluginRuntime, build_plugin_runtime
from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import (
    FsAccess,
    PluginState,
    RequestedCapabilities,
)
from turkish_code.eklentiler.yukleyici import LoadedPlugin
from turkish_code.hata import AppError


class _Tool:
    def __init__(self, name: str, capability: Capability | None) -> None:
        self._name = name
        self._capability = capability

    @property
    def metadata(self) -> ToolMetadata:
        mutate = self._capability is Capability.FS_WRITE
        return ToolMetadata(
            name=self._name,
            summary=self._name,
            capability=self._capability,
            side_effect=SideEffect.MUTATE if mutate else SideEffect.READ,
            brokered=self._capability is not None,
            reversible=mutate,
            idempotent=True,
            timeout_ms=1000,
        )

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output=f"{self._name}-ran")


def _provider(mapping: Mapping[str, Sequence[Tool]]) -> object:
    def provide(manifest: PluginManifest) -> Sequence[Tool]:
        return mapping.get(manifest.id, [])

    return provide


def _write(
    root: Path,
    dirname: str,
    body: str,
) -> None:
    plugin_dir = root / dirname
    plugin_dir.mkdir()
    (plugin_dir / "plugin.toml").write_text(body, encoding="utf-8")


def _toml(
    plugin_id: str,
    *,
    version: str = "1.0.0",
    min_app: str = "0.0.0",
    fs: str = "none",
) -> str:
    return (
        f'[plugin]\nid = "{plugin_id}"\nname = "P"\nversion = "{version}"\n'
        f'min_app_version = "{min_app}"\n\n[capabilities-requested]\nfs = "{fs}"\n'
    )


def _wire(
    tmp_path: Path,
    mapping: Mapping[str, Sequence[Tool]],
    *,
    mode: PermissionMode = PermissionMode.AUTO,
) -> tuple[PluginRuntime, PluginGrantStore, ToolDispatcher, ToolRegistry]:
    tool_registry = ToolRegistry()
    grants = PluginGrantStore()
    runtime = build_plugin_runtime(
        tool_registry,
        grants,
        app_version="1.0.0",
        tool_provider=_provider(mapping),  # type: ignore[arg-type]
    )
    gate = PluginPermissionGate(
        PolicyPermissionGate(PermissionPolicy(mode=mode)), grants
    )
    dispatcher = ToolDispatcher(tool_registry, gate)
    return runtime, grants, dispatcher, tool_registry


@pytest.mark.asyncio
async def test_full_journey_load_grant_enable_dispatch_disable(tmp_path: Path) -> None:
    _write(tmp_path, "lint", _toml("org.a.lint", fs="read"))
    runtime, grants, dispatcher, registry = _wire(
        tmp_path, {"org.a.lint": [_Tool("check", Capability.FS_READ)]}
    )
    report = runtime.lifecycle.load(tmp_path)
    assert report.loaded == ("org.a.lint",) and report.failures == ()

    grants.grant("org.a.lint", RequestedCapabilities(fs=FsAccess.READ))
    runtime.lifecycle.enable("org.a.lint")
    result = await dispatcher.dispatch(
        ToolRequest(name="org.a.lint/check", arguments={}, call_id="c1")
    )
    assert result.output == "check-ran"

    runtime.lifecycle.disable("org.a.lint")
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(
            ToolRequest(name="org.a.lint/check", arguments={}, call_id="c2")
        )
    assert exc_info.value.code == TOOL_NOT_FOUND_CODE  # withdrawn on disable


@pytest.mark.asyncio
async def test_broken_manifest_amid_good_ones_is_isolated(tmp_path: Path) -> None:
    _write(tmp_path, "good", _toml("org.a.good"))
    _write(tmp_path, "brokentoml", "= = not toml")
    _write(tmp_path, "badver", _toml("org.a.badver", version="1.x"))
    _write(tmp_path, "incompat", _toml("org.a.incompat", min_app="9.9.9"))
    runtime, _, _, _ = _wire(tmp_path, {})
    report = runtime.lifecycle.load(tmp_path)

    assert report.loaded == ("org.a.good",)
    assert len(report.failures) == 3  # the other three each failed, non-fatally


@pytest.mark.asyncio
async def test_missing_version_is_reported(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "p",
        '[plugin]\nid = "org.a.p"\nname = "P"\nmin_app_version = "0.0.0"\n',
    )
    runtime, _, _, _ = _wire(tmp_path, {})
    report = runtime.lifecycle.load(tmp_path)
    assert report.loaded == () and len(report.failures) == 1


@pytest.mark.asyncio
async def test_permission_denied_without_grant(tmp_path: Path) -> None:
    runtime, grants, dispatcher, _ = _wire(
        tmp_path, {"org.a.p": [_Tool("reader", Capability.FS_READ)]}
    )
    runtime.registry.register(
        LoadedPlugin(
            manifest=PluginManifest(
                id="org.a.p", name="P", version="1.0.0", min_app_version="0.0.0"
            ),
            contributed_tools=(_Tool("reader", Capability.FS_READ),),
        )
    )
    runtime.lifecycle.enable("org.a.p")  # enabled, but no capability granted
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(
            ToolRequest(name="org.a.p/reader", arguments={}, call_id="c1")
        )
    assert exc_info.value.code == TOOL_DENIED_CODE


@pytest.mark.asyncio
async def test_grant_does_not_cover_stronger_capability(tmp_path: Path) -> None:
    # Plugin granted fs:read, but its tool needs fs.write → denied (doc 23 §6).
    runtime, grants, dispatcher, _ = _wire(tmp_path, {})
    runtime.registry.register(
        LoadedPlugin(
            manifest=PluginManifest(
                id="org.a.w", name="W", version="1.0.0", min_app_version="0.0.0"
            ),
            contributed_tools=(_Tool("writer", Capability.FS_WRITE),),
        )
    )
    grants.grant("org.a.w", RequestedCapabilities(fs=FsAccess.READ))
    runtime.lifecycle.enable("org.a.w")
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(
            ToolRequest(name="org.a.w/writer", arguments={}, call_id="c1")
        )
    assert exc_info.value.code == TOOL_DENIED_CODE


@pytest.mark.asyncio
async def test_session_plan_mode_denies_even_granted_plugin(tmp_path: Path) -> None:
    runtime, grants, dispatcher, _ = _wire(tmp_path, {}, mode=PermissionMode.PLAN)
    runtime.registry.register(
        LoadedPlugin(
            manifest=PluginManifest(
                id="org.a.w", name="W", version="1.0.0", min_app_version="0.0.0"
            ),
            contributed_tools=(_Tool("writer", Capability.FS_WRITE),),
        )
    )
    grants.grant("org.a.w", RequestedCapabilities(fs=FsAccess.WRITE))
    runtime.lifecycle.enable("org.a.w")
    with pytest.raises(AppError) as exc_info:  # grant ok, but Plan is read-only
        await dispatcher.dispatch(
            ToolRequest(name="org.a.w/writer", arguments={}, call_id="c1")
        )
    assert exc_info.value.code == TOOL_DENIED_CODE


def test_duplicate_plugin_on_disk_loads_one(tmp_path: Path) -> None:
    _write(tmp_path, "a", _toml("org.a.dup"))
    _write(tmp_path, "b", _toml("org.a.dup"))
    runtime, _, _, _ = _wire(tmp_path, {})
    report = runtime.lifecycle.load(tmp_path)
    assert report.loaded == ("org.a.dup",)
    assert len(report.failures) == 1  # the second duplicate


def test_two_plugins_same_tool_name_coexist(tmp_path: Path) -> None:
    runtime, _, _, registry = _wire(
        tmp_path,
        {
            "org.a.x": [_Tool("check", None)],
            "org.b.y": [_Tool("check", None)],
        },
    )
    for pid in ("org.a.x", "org.b.y"):
        runtime.registry.register(
            LoadedPlugin(
                manifest=PluginManifest(
                    id=pid, name=pid, version="1.0.0", min_app_version="0.0.0"
                ),
                contributed_tools=(_Tool("check", None),),
            )
        )
        runtime.lifecycle.enable(pid)
    assert registry.names() == ["org.a.x/check", "org.b.y/check"]


def test_within_plugin_tool_collision_fails_enable_then_recovers(
    tmp_path: Path,
) -> None:
    runtime, _, _, registry = _wire(tmp_path, {})
    runtime.registry.register(
        LoadedPlugin(
            manifest=PluginManifest(
                id="org.a.c", name="C", version="1.0.0", min_app_version="0.0.0"
            ),
            contributed_tools=(_Tool("dup", None), _Tool("dup", None)),
        )
    )
    with pytest.raises(AppError):
        runtime.lifecycle.enable("org.a.c")
    assert runtime.registry.state_of("org.a.c") is PluginState.FAILED
    assert registry.names() == []  # atomic rollback — nothing half-registered

    runtime.lifecycle.recover("org.a.c")
    assert runtime.registry.state_of("org.a.c") is PluginState.DISABLED


@pytest.mark.asyncio
async def test_reload_swaps_tools_and_keeps_enabled(tmp_path: Path) -> None:
    runtime, _, dispatcher, registry = _wire(tmp_path, {})
    manifest = PluginManifest(
        id="org.a.v", name="V", version="1.0.0", min_app_version="0.0.0"
    )
    runtime.registry.register(
        LoadedPlugin(manifest=manifest, contributed_tools=(_Tool("old", None),))
    )
    runtime.lifecycle.enable("org.a.v")
    assert registry.names() == ["org.a.v/old"]

    # Reload a "v2" whose tool was renamed old → new.
    v2 = LoadedPlugin(
        manifest=PluginManifest(
            id="org.a.v", name="V", version="2.0.0", min_app_version="0.0.0"
        ),
        contributed_tools=(_Tool("new", None),),
    )
    runtime.lifecycle.reload(v2)
    assert runtime.registry.state_of("org.a.v") is PluginState.ENABLED
    assert registry.names() == ["org.a.v/new"]  # old withdrawn, new bridged
    result = await dispatcher.dispatch(
        ToolRequest(name="org.a.v/new", arguments={}, call_id="c1")
    )
    assert result.output == "new-ran"


def test_unload_withdraws_and_removes(tmp_path: Path) -> None:
    runtime, _, _, registry = _wire(tmp_path, {})
    runtime.registry.register(
        LoadedPlugin(
            manifest=PluginManifest(
                id="org.a.u", name="U", version="1.0.0", min_app_version="0.0.0"
            ),
            contributed_tools=(_Tool("t", None),),
        )
    )
    runtime.lifecycle.enable("org.a.u")
    assert registry.names() == ["org.a.u/t"]
    runtime.lifecycle.unload("org.a.u")
    assert registry.names() == []  # tools withdrawn
    assert "org.a.u" not in runtime.registry  # plugin removed
