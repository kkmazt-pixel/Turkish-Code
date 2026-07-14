"""Tests for plugin permission integration (doc 23 §6/§8)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.hata import TOOL_DENIED_CODE
from turkish_code.araclar.izin import (
    Allow,
    Deny,
    PermissionMode,
    PermissionPolicy,
    PermissionRequest,
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
from turkish_code.eklentiler.izin import (
    PluginGrantStore,
    PluginPermissionGate,
    PluginToolBridge,
    grant_covers,
    namespaced_name,
    plugin_id_of,
)
from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import FsAccess, NetAccess, RequestedCapabilities
from turkish_code.hata import AppError


class _Tool:
    def __init__(self, name: str, capability: Capability | None) -> None:
        self._name = name
        self._capability = capability

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self._name,
            summary=self._name,
            capability=self._capability,
            side_effect=(
                SideEffect.READ
                if self._capability in (None, Capability.FS_READ)
                else (
                    SideEffect.MUTATE
                    if self._capability is Capability.FS_WRITE
                    else SideEffect.EGRESS
                )
            ),
            brokered=self._capability is not None,
            reversible=self._capability is Capability.FS_WRITE,
            idempotent=True,
            timeout_ms=1000,
        )

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output="ran")


class _Plugin:
    def __init__(self, plugin_id: str, tools: Sequence[Tool]) -> None:
        self._manifest = PluginManifest(
            id=plugin_id, name=plugin_id, version="1.0.0", min_app_version="1.0.0"
        )
        self._tools = tuple(tools)

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def tools(self) -> Sequence[Tool]:
        return self._tools


# --- namespacing --------------------------------------------------------------


def test_namespacing_round_trip() -> None:
    name = namespaced_name("org.a.lint", "lint_check")
    assert name == "org.a.lint/lint_check"
    assert plugin_id_of(name) == "org.a.lint"


def test_first_party_tool_has_no_plugin_namespace() -> None:
    assert plugin_id_of("fs.write") is None


# --- grant coverage -----------------------------------------------------------


def test_fs_write_grant_implies_read() -> None:
    caps = RequestedCapabilities(fs=FsAccess.WRITE)
    assert grant_covers(caps, Capability.FS_READ)
    assert grant_covers(caps, Capability.FS_WRITE)


def test_fs_read_grant_does_not_imply_write() -> None:
    caps = RequestedCapabilities(fs=FsAccess.READ)
    assert grant_covers(caps, Capability.FS_READ)
    assert not grant_covers(caps, Capability.FS_WRITE)


def test_undeclarable_capability_is_never_covered() -> None:
    caps = RequestedCapabilities(fs=FsAccess.WRITE, net=NetAccess.EGRESS)
    assert not grant_covers(caps, Capability.OPEN_EXTERNAL)
    assert not grant_covers(caps, Capability.SECRET_USE)


# --- grant store --------------------------------------------------------------


def test_grant_store_defaults_to_no_capability() -> None:
    store = PluginGrantStore()
    assert store.granted("org.a.x") == RequestedCapabilities()
    assert not store.covers("org.a.x", Capability.FS_READ)


def test_grant_and_revoke() -> None:
    store = PluginGrantStore()
    store.grant("org.a.x", RequestedCapabilities(fs=FsAccess.READ))
    assert store.covers("org.a.x", Capability.FS_READ)
    store.revoke("org.a.x")
    assert not store.covers("org.a.x", Capability.FS_READ)


# --- permission gate (grant ∩ session) ----------------------------------------


def _gate(store: PluginGrantStore, mode: PermissionMode) -> PluginPermissionGate:
    base = PolicyPermissionGate(PermissionPolicy(mode=mode))
    return PluginPermissionGate(base, store)


def _req(
    tool: str, capability: Capability | None, side: SideEffect
) -> PermissionRequest:
    return PermissionRequest(tool=tool, capability=capability, side_effect=side)


@pytest.mark.asyncio
async def test_ungranted_plugin_capability_is_denied() -> None:
    gate = _gate(PluginGrantStore(), PermissionMode.AUTO)
    decision = await gate.evaluate(
        _req("org.a.x/reader", Capability.FS_READ, SideEffect.READ)
    )
    assert isinstance(decision, Deny)  # session would allow, but no grant


@pytest.mark.asyncio
async def test_granted_plugin_capability_defers_to_session() -> None:
    store = PluginGrantStore()
    store.grant("org.a.x", RequestedCapabilities(fs=FsAccess.WRITE))
    # Grant covers fs.write, but session is PLAN (read-only) → still denied.
    plan = _gate(store, PermissionMode.PLAN)
    assert isinstance(
        await plan.evaluate(_req("org.a.x/w", Capability.FS_WRITE, SideEffect.MUTATE)),
        Deny,
    )
    # Same grant under AUTO → allowed (both grant and session agree).
    auto = _gate(store, PermissionMode.AUTO)
    assert isinstance(
        await auto.evaluate(_req("org.a.x/w", Capability.FS_WRITE, SideEffect.MUTATE)),
        Allow,
    )


@pytest.mark.asyncio
async def test_first_party_tool_bypasses_grant_check() -> None:
    gate = _gate(PluginGrantStore(), PermissionMode.AUTO)
    decision = await gate.evaluate(_req("fs.read", Capability.FS_READ, SideEffect.READ))
    assert isinstance(decision, Allow)  # no namespace → session only


@pytest.mark.asyncio
async def test_local_plugin_tool_needs_no_grant() -> None:
    gate = _gate(PluginGrantStore(), PermissionMode.AUTO)
    decision = await gate.evaluate(_req("org.a.x/mem", None, SideEffect.READ))
    assert isinstance(decision, Allow)


# --- tool bridge --------------------------------------------------------------


def test_bridge_registers_namespaced_tools() -> None:
    registry = ToolRegistry()
    bridge = PluginToolBridge(registry)
    plugin = _Plugin("org.a.lint", [_Tool("lint_check", Capability.FS_READ)])
    bridge.activate(plugin)
    assert registry.names() == ["org.a.lint/lint_check"]


def test_bridge_deactivate_withdraws_tools() -> None:
    registry = ToolRegistry()
    bridge = PluginToolBridge(registry)
    plugin = _Plugin("org.a.lint", [_Tool("lint_check", Capability.FS_READ)])
    bridge.activate(plugin)
    bridge.deactivate(plugin)
    assert registry.names() == []


def test_two_plugins_same_tool_name_do_not_collide() -> None:
    registry = ToolRegistry()
    bridge = PluginToolBridge(registry)
    bridge.activate(_Plugin("org.a.x", [_Tool("check", None)]))
    bridge.activate(_Plugin("org.b.y", [_Tool("check", None)]))
    assert registry.names() == ["org.a.x/check", "org.b.y/check"]


def test_within_plugin_duplicate_tool_rolls_back_atomically() -> None:
    registry = ToolRegistry()
    bridge = PluginToolBridge(registry)
    plugin = _Plugin("org.a.x", [_Tool("dup", None), _Tool("dup", None)])
    with pytest.raises(AppError):
        bridge.activate(plugin)
    assert registry.names() == []  # the first registration was rolled back


@pytest.mark.asyncio
async def test_bridged_plugin_tool_runs_through_dispatcher_when_granted() -> None:
    from turkish_code.araclar.dagitici import ToolDispatcher

    registry = ToolRegistry()
    store = PluginGrantStore()
    store.grant("org.a.lint", RequestedCapabilities(fs=FsAccess.READ))
    PluginToolBridge(registry).activate(
        _Plugin("org.a.lint", [_Tool("lint_check", Capability.FS_READ)])
    )
    gate = PluginPermissionGate(
        PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO)), store
    )
    dispatcher = ToolDispatcher(registry, gate)
    result = await dispatcher.dispatch(
        ToolRequest(name="org.a.lint/lint_check", arguments={}, call_id="c1")
    )
    assert result.output == "ran"


@pytest.mark.asyncio
async def test_bridged_plugin_tool_denied_without_grant() -> None:
    from turkish_code.araclar.dagitici import ToolDispatcher

    registry = ToolRegistry()
    PluginToolBridge(registry).activate(
        _Plugin("org.a.lint", [_Tool("lint_check", Capability.FS_READ)])
    )
    gate = PluginPermissionGate(
        PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO)),
        PluginGrantStore(),  # no grant recorded
    )
    dispatcher = ToolDispatcher(registry, gate)
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(
            ToolRequest(name="org.a.lint/lint_check", arguments={}, call_id="c1")
        )
    assert exc_info.value.code == TOOL_DENIED_CODE
