"""Tests for the plugin lifecycle (doc 23 §7/§12)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from turkish_code.araclar.hata import duplicate_tool
from turkish_code.araclar.protocol import Tool
from turkish_code.eklentiler.kayit import PluginRegistry
from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import PluginState
from turkish_code.eklentiler.protocol import Plugin
from turkish_code.eklentiler.yasam import PluginLifecycle
from turkish_code.eklentiler.yukleyici import PluginLoader
from turkish_code.hata import AppError


class _StubPlugin:
    def __init__(self, plugin_id: str) -> None:
        self._manifest = PluginManifest(
            id=plugin_id, name=plugin_id, version="1.0.0", min_app_version="1.0.0"
        )

    @property
    def manifest(self) -> PluginManifest:
        return self._manifest

    def tools(self) -> Sequence[Tool]:
        return ()


class _Recorder:
    def __init__(self, *, fail_ids: frozenset[str] = frozenset()) -> None:
        self.activated: list[str] = []
        self.deactivated: list[str] = []
        self._fail = fail_ids

    def activate(self, plugin: Plugin) -> None:
        if plugin.manifest.id in self._fail:
            raise duplicate_tool("conflicting_tool")  # e.g. a colliding tool name
        self.activated.append(plugin.manifest.id)

    def deactivate(self, plugin: Plugin) -> None:
        self.deactivated.append(plugin.manifest.id)


def _lifecycle(
    *, fail_ids: frozenset[str] = frozenset()
) -> tuple[PluginRegistry, PluginLifecycle, _Recorder]:
    registry = PluginRegistry()
    loader = PluginLoader(app_version="1.5.0")
    rec = _Recorder(fail_ids=fail_ids)
    lifecycle = PluginLifecycle(
        registry, loader, activate=rec.activate, deactivate=rec.deactivate
    )
    return registry, lifecycle, rec


def test_load_registers_plugins_from_disk(tmp_path: Path) -> None:
    (tmp_path / "lint").mkdir()
    (tmp_path / "lint" / "plugin.toml").write_text(
        '[plugin]\nid = "org.a.lint"\nname = "L"\nversion = "1.0.0"\n'
        'min_app_version = "1.0.0"\n',
        encoding="utf-8",
    )
    registry, lifecycle, _ = _lifecycle()
    report = lifecycle.load(tmp_path)
    assert report.loaded == ("org.a.lint",)
    assert registry.state_of("org.a.lint") is PluginState.DISABLED


def test_enable_activates_and_marks_enabled() -> None:
    registry, lifecycle, rec = _lifecycle()
    registry.register(_StubPlugin("org.a.one"))
    lifecycle.enable("org.a.one")
    assert rec.activated == ["org.a.one"]
    assert registry.state_of("org.a.one") is PluginState.ENABLED


def test_enable_is_idempotent() -> None:
    registry, lifecycle, rec = _lifecycle()
    registry.register(_StubPlugin("org.a.one"))
    lifecycle.enable("org.a.one")
    lifecycle.enable("org.a.one")  # second call is a no-op
    assert rec.activated == ["org.a.one"]  # activated only once


def test_enable_failure_quarantines_plugin() -> None:
    registry, lifecycle, rec = _lifecycle(fail_ids=frozenset({"org.a.bad"}))
    registry.register(_StubPlugin("org.a.bad"))
    with pytest.raises(AppError):
        lifecycle.enable("org.a.bad")
    assert registry.state_of("org.a.bad") is PluginState.FAILED
    assert rec.activated == []  # nothing half-registered


def test_disable_deactivates_and_marks_disabled() -> None:
    registry, lifecycle, rec = _lifecycle()
    registry.register(_StubPlugin("org.a.one"))
    lifecycle.enable("org.a.one")
    lifecycle.disable("org.a.one")
    assert rec.deactivated == ["org.a.one"]
    assert registry.state_of("org.a.one") is PluginState.DISABLED


def test_disable_when_not_enabled_is_noop() -> None:
    registry, lifecycle, rec = _lifecycle()
    registry.register(_StubPlugin("org.a.one"))
    lifecycle.disable("org.a.one")  # never enabled
    assert rec.deactivated == []


def test_unload_disables_then_removes() -> None:
    registry, lifecycle, rec = _lifecycle()
    registry.register(_StubPlugin("org.a.one"))
    lifecycle.enable("org.a.one")
    lifecycle.unload("org.a.one")
    assert rec.deactivated == ["org.a.one"]  # deactivated on the way out
    assert "org.a.one" not in registry


def test_unload_disabled_plugin_does_not_deactivate() -> None:
    registry, lifecycle, rec = _lifecycle()
    registry.register(_StubPlugin("org.a.one"))
    lifecycle.unload("org.a.one")  # was never enabled
    assert rec.deactivated == []
    assert "org.a.one" not in registry


def test_reload_preserves_enabled_state_and_reactivates() -> None:
    registry, lifecycle, rec = _lifecycle()
    registry.register(_StubPlugin("org.a.one"))
    lifecycle.enable("org.a.one")
    replacement = _StubPlugin("org.a.one")  # "new version", same id
    lifecycle.reload(replacement)
    assert registry.resolve("org.a.one") is replacement  # swapped
    assert registry.state_of("org.a.one") is PluginState.ENABLED
    assert rec.activated == ["org.a.one", "org.a.one"]  # re-activated
    assert rec.deactivated == ["org.a.one"]  # old deactivated during swap


def test_reload_keeps_disabled_plugin_inactive() -> None:
    registry, lifecycle, rec = _lifecycle()
    registry.register(_StubPlugin("org.a.one"))
    lifecycle.reload(_StubPlugin("org.a.one"))
    assert registry.state_of("org.a.one") is PluginState.DISABLED
    assert rec.activated == []


def test_recover_resets_failed_to_disabled_then_reenable() -> None:
    registry, lifecycle, rec = _lifecycle(fail_ids=frozenset({"org.a.bad"}))
    registry.register(_StubPlugin("org.a.bad"))
    with pytest.raises(AppError):
        lifecycle.enable("org.a.bad")
    assert registry.state_of("org.a.bad") is PluginState.FAILED

    lifecycle.recover("org.a.bad")
    assert registry.state_of("org.a.bad") is PluginState.DISABLED

    # Once the cause is gone, a fresh recorder can enable it successfully.
    registry2, lifecycle2, rec2 = _lifecycle()
    registry2.register(_StubPlugin("org.a.bad"))
    lifecycle2.enable("org.a.bad")
    assert registry2.state_of("org.a.bad") is PluginState.ENABLED


def test_recover_is_noop_for_non_failed_plugin() -> None:
    registry, lifecycle, _ = _lifecycle()
    registry.register(_StubPlugin("org.a.one"))
    lifecycle.enable("org.a.one")
    lifecycle.recover("org.a.one")  # not FAILED → unchanged
    assert registry.state_of("org.a.one") is PluginState.ENABLED
