"""Tests for plugin models, manifest, and the Plugin Protocol (doc 23 §4/§5/§7)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.modeller import (
    SideEffect,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from turkish_code.araclar.protocol import Tool
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


def test_capability_and_state_wire_values() -> None:
    assert FsAccess.READ.value == "read"
    assert NetAccess.EGRESS.value == "egress"
    assert ShellAccess.EXEC.value == "exec"
    assert PluginState.ENABLED.value == "enabled"
    assert PluginRuntimeKind.PYTHON.value == "python"


def test_requested_capabilities_default_to_least_privilege() -> None:
    caps = RequestedCapabilities()
    assert caps.fs is FsAccess.NONE
    assert caps.net is NetAccess.NONE
    assert caps.shell is ShellAccess.NONE


def test_contributions_default_to_empty_tools() -> None:
    assert Contributions().tools == ()


def _manifest(**overrides: object) -> PluginManifest:
    base: dict[str, object] = {
        "id": "org.example.lint",
        "name": "Türkçe Lint",
        "version": "1.2.0",
        "min_app_version": "1.0.0",
    }
    base.update(overrides)
    return PluginManifest(**base)  # type: ignore[arg-type]


def test_manifest_has_sensible_defaults() -> None:
    manifest = _manifest()
    assert manifest.authors == ()
    assert manifest.license == ""
    assert manifest.contributions.tools == ()
    assert manifest.capabilities == RequestedCapabilities()
    assert manifest.runtime_kind is PluginRuntimeKind.PYTHON
    assert manifest.entry == "main.py"


def test_manifest_carries_declared_contributions_and_capabilities() -> None:
    manifest = _manifest(
        contributions=Contributions(tools=("tools/lint_check",)),
        capabilities=RequestedCapabilities(fs=FsAccess.READ),
    )
    assert manifest.contributions.tools == ("tools/lint_check",)
    assert manifest.capabilities.fs is FsAccess.READ


@pytest.mark.parametrize("field", ["id", "name", "version", "min_app_version", "entry"])
def test_manifest_rejects_empty_required_fields(field: str) -> None:
    with pytest.raises(ValueError, match=f"{field} must be non-empty"):
        _manifest(**{field: ""})


def test_manifest_is_immutable() -> None:
    manifest = _manifest()
    with pytest.raises(AttributeError):
        manifest.version = "2.0.0"  # type: ignore[misc]


class _StubTool:
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="lint_check",
            summary="lint aracı",
            capability=None,
            side_effect=SideEffect.READ,
            brokered=False,
            reversible=False,
            idempotent=True,
            timeout_ms=1000,
        )

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output=None)


class _StubPlugin:
    def __init__(self, manifest: PluginManifest, tools: Sequence[Tool]) -> None:
        self._manifest = manifest
        self._tools = tuple(tools)

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def tools(self) -> Sequence[Tool]:
        return self._tools


def test_concrete_plugin_satisfies_protocol() -> None:
    plugin = _StubPlugin(_manifest(), [_StubTool()])
    assert isinstance(plugin, Plugin)
    assert isinstance(plugin.tools()[0], Tool)


def test_plain_object_is_not_a_plugin() -> None:
    assert not isinstance(object(), Plugin)
