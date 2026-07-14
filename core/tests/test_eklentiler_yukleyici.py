"""Tests for the plugin loader — real manifests on disk (doc 23 §7/§11)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.modeller import (
    SideEffect,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from turkish_code.araclar.protocol import Tool
from turkish_code.eklentiler.dogrulama import (
    PLUGIN_INCOMPATIBLE_CODE,
    PLUGIN_INVALID_VERSION_CODE,
)
from turkish_code.eklentiler.kayit import PLUGIN_DUPLICATE_CODE, PluginRegistry
from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import FsAccess, PluginState
from turkish_code.eklentiler.protocol import Plugin
from turkish_code.eklentiler.yukleyici import (
    PLUGIN_MANIFEST_READ_CODE,
    PluginLoader,
)

_VALID = """
[plugin]
id = "org.example.lint"
name = "Türkçe Lint"
version = "1.2.0"
min_app_version = "1.0.0"
authors = ["Ada"]
license = "MIT"

[contributes]
tools = ["tools/lint_check"]

[capabilities-requested]
fs = "read"
net = "none"

[runtime]
kind = "python"
entry = "main.py"
"""


def _write(root: Path, dirname: str, toml: str) -> None:
    plugin_dir = root / dirname
    plugin_dir.mkdir()
    (plugin_dir / "plugin.toml").write_text(toml, encoding="utf-8")


class _StubTool:
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="lint_check",
            summary="lint",
            capability=None,
            side_effect=SideEffect.READ,
            brokered=False,
            reversible=False,
            idempotent=True,
            timeout_ms=1000,
        )

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output=None)


def _loader(**kw: object) -> PluginLoader:
    return PluginLoader(app_version="1.5.0", **kw)  # type: ignore[arg-type]


def test_loads_and_registers_a_valid_plugin(tmp_path: Path) -> None:
    _write(tmp_path, "lint", _VALID)
    registry = PluginRegistry()
    report = _loader().load_directory(tmp_path, registry)

    assert report.loaded == ("org.example.lint",)
    assert report.failures == ()
    assert "org.example.lint" in registry
    assert registry.state_of("org.example.lint") is PluginState.DISABLED
    manifest: PluginManifest = registry.resolve("org.example.lint").manifest
    assert manifest.contributions.tools == ("tools/lint_check",)
    assert manifest.capabilities.fs is FsAccess.READ
    assert manifest.authors == ("Ada",)


def test_tool_provider_supplies_contributed_tools(tmp_path: Path) -> None:
    _write(tmp_path, "lint", _VALID)

    def provider(manifest: PluginManifest) -> Sequence[Tool]:
        return [_StubTool()]

    registry = PluginRegistry()
    _loader(tool_provider=provider).load_directory(tmp_path, registry)
    plugin: Plugin = registry.resolve("org.example.lint")
    assert [t.metadata.name for t in plugin.tools()] == ["lint_check"]


def test_missing_root_yields_empty_report(tmp_path: Path) -> None:
    report = _loader().load_directory(tmp_path / "nope", PluginRegistry())
    assert report.loaded == () and report.failures == ()


def test_directory_without_manifest_is_skipped(tmp_path: Path) -> None:
    (tmp_path / "not-a-plugin").mkdir()
    report = _loader().load_directory(tmp_path, PluginRegistry())
    assert report.loaded == () and report.failures == ()


def test_malformed_toml_is_reported_not_fatal(tmp_path: Path) -> None:
    _write(tmp_path, "bad", "this is = = not toml")
    _write(tmp_path, "good", _VALID)
    registry = PluginRegistry()
    report = _loader().load_directory(tmp_path, registry)

    assert report.loaded == ("org.example.lint",)  # the good one still loaded
    assert len(report.failures) == 1
    assert report.failures[0].error.code == PLUGIN_MANIFEST_READ_CODE
    assert "org.example.lint" in registry


def test_missing_required_field_is_a_read_failure(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "p",
        '[plugin]\nid = "org.a.p"\nname = "P"\nmin_app_version = "1.0.0"\n',
    )
    report = _loader().load_directory(tmp_path, PluginRegistry())
    assert report.loaded == ()
    assert report.failures[0].error.code == PLUGIN_MANIFEST_READ_CODE


def test_bad_capability_value_is_a_read_failure(tmp_path: Path) -> None:
    toml = (
        '[plugin]\nid = "org.a.p"\nname = "P"\nversion = "1.0.0"\n'
        'min_app_version = "1.0.0"\n\n[capabilities-requested]\nfs = "teleport"\n'
    )
    _write(tmp_path, "p", toml)
    report = _loader().load_directory(tmp_path, PluginRegistry())
    assert report.failures[0].error.code == PLUGIN_MANIFEST_READ_CODE


def test_invalid_version_is_reported(tmp_path: Path) -> None:
    toml = (
        '[plugin]\nid = "org.a.p"\nname = "P"\nversion = "1.x"\n'
        'min_app_version = "1.0.0"\n'
    )
    _write(tmp_path, "p", toml)
    report = _loader().load_directory(tmp_path, PluginRegistry())
    assert report.failures[0].error.code == PLUGIN_INVALID_VERSION_CODE


def test_incompatible_plugin_is_reported(tmp_path: Path) -> None:
    toml = (
        '[plugin]\nid = "org.a.p"\nname = "P"\nversion = "1.0.0"\n'
        'min_app_version = "9.0.0"\n'
    )
    _write(tmp_path, "p", toml)
    report = _loader().load_directory(tmp_path, PluginRegistry())
    assert report.failures[0].error.code == PLUGIN_INCOMPATIBLE_CODE
    assert report.loaded == ()


def test_duplicate_id_across_dirs_loads_one_reports_other(tmp_path: Path) -> None:
    _write(tmp_path, "a", _VALID)
    _write(tmp_path, "b", _VALID)  # same id inside
    registry = PluginRegistry()
    report = _loader().load_directory(tmp_path, registry)

    assert report.loaded == ("org.example.lint",)  # first (sorted) wins
    assert len(report.failures) == 1
    assert report.failures[0].error.code == PLUGIN_DUPLICATE_CODE
