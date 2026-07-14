"""Tests for the plugin registry (doc 23 §7/§8)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from turkish_code.araclar.protocol import Tool
from turkish_code.eklentiler.kayit import (
    PLUGIN_DUPLICATE_CODE,
    PLUGIN_NOT_FOUND_CODE,
    PluginRegistry,
)
from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import PluginState
from turkish_code.hata import AppError, ErrorKind


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


def test_register_then_resolve_returns_same_plugin() -> None:
    registry = PluginRegistry()
    plugin = _StubPlugin("org.a.one")
    registry.register(plugin)
    assert registry.resolve("org.a.one") is plugin
    assert registry.state_of("org.a.one") is PluginState.DISABLED  # initial state


def test_duplicate_registration_is_rejected() -> None:
    registry = PluginRegistry()
    registry.register(_StubPlugin("org.a.one"))
    with pytest.raises(AppError) as exc_info:
        registry.register(_StubPlugin("org.a.one"))
    assert exc_info.value.code == PLUGIN_DUPLICATE_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_resolve_missing_raises_not_found() -> None:
    registry = PluginRegistry()
    with pytest.raises(AppError) as exc_info:
        registry.resolve("absent")
    assert exc_info.value.code == PLUGIN_NOT_FOUND_CODE
    assert exc_info.value.kind is ErrorKind.NOT_FOUND


def test_get_returns_none_for_missing() -> None:
    assert PluginRegistry().get("absent") is None


def test_enable_and_disable_flip_state() -> None:
    registry = PluginRegistry()
    registry.register(_StubPlugin("org.a.one"))
    registry.enable("org.a.one")
    assert registry.is_enabled("org.a.one")
    assert registry.state_of("org.a.one") is PluginState.ENABLED
    registry.disable("org.a.one")
    assert not registry.is_enabled("org.a.one")
    assert registry.state_of("org.a.one") is PluginState.DISABLED


def test_mark_failed_quarantines_plugin() -> None:
    registry = PluginRegistry()
    registry.register(_StubPlugin("org.a.one"))
    registry.mark_failed("org.a.one")
    assert registry.state_of("org.a.one") is PluginState.FAILED
    assert not registry.is_enabled("org.a.one")


def test_unload_removes_plugin() -> None:
    registry = PluginRegistry()
    registry.register(_StubPlugin("org.a.one"))
    removed = registry.unload("org.a.one")
    assert removed.manifest.id == "org.a.one"
    assert "org.a.one" not in registry
    with pytest.raises(AppError):
        registry.resolve("org.a.one")


def test_unload_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        PluginRegistry().unload("absent")
    assert exc_info.value.code == PLUGIN_NOT_FOUND_CODE


def test_enable_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        PluginRegistry().enable("absent")
    assert exc_info.value.code == PLUGIN_NOT_FOUND_CODE


def test_ids_are_sorted() -> None:
    registry = PluginRegistry()
    for pid in ("org.z.p", "org.a.p", "org.m.p"):
        registry.register(_StubPlugin(pid))
    assert registry.ids() == ["org.a.p", "org.m.p", "org.z.p"]


def test_enabled_lists_only_enabled_sorted() -> None:
    registry = PluginRegistry()
    for pid in ("org.a.p", "org.b.p", "org.c.p"):
        registry.register(_StubPlugin(pid))
    registry.enable("org.c.p")
    registry.enable("org.a.p")
    assert [p.manifest.id for p in registry.enabled()] == ["org.a.p", "org.c.p"]


def test_contains_and_len() -> None:
    registry = PluginRegistry()
    registry.register(_StubPlugin("org.a.one"))
    assert "org.a.one" in registry
    assert "absent" not in registry
    assert 123 not in registry
    assert len(registry) == 1
