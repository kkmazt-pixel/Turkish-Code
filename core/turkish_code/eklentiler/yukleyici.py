"""Plugin loader (doc 23 §7 DISCOVER/VALIDATE) — disk → validated, registered.

Discovers ``plugin.toml`` manifests under a plugins root, parses each into a
typed :class:`PluginManifest`, validates it (:mod:`dogrulama`), resolves its Tool
contributions through an injected provider — the sandbox seam; **no plugin code
is executed here** (doc 23 §6) — and registers the loaded plugin. Per-plugin
failures are collected, never fatal: a bad plugin is skipped and reported while
the rest load (fail-safe, no partial load, doc 23 §11).
"""

from __future__ import annotations

import tomllib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from turkish_code.araclar.protocol import Tool
from turkish_code.eklentiler.dogrulama import validate_manifest
from turkish_code.eklentiler.kayit import PluginRegistry
from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import (
    Contributions,
    FsAccess,
    NetAccess,
    PluginRuntimeKind,
    RequestedCapabilities,
    ShellAccess,
)
from turkish_code.hata import AppError, ErrorKind

MANIFEST_NAME = "plugin.toml"
PLUGIN_MANIFEST_READ_CODE = "plugin.manifest_read"

ToolProvider = Callable[[PluginManifest], Sequence[Tool]]
"""Resolves a validated manifest to its Tool contributions (the sandbox seam)."""


def _no_tools(manifest: PluginManifest) -> Sequence[Tool]:
    return ()


@dataclass(frozen=True, slots=True)
class LoadedPlugin:
    """A discovered + validated plugin: its manifest and resolved Tools (doc 23 §4)."""

    manifest: PluginManifest
    contributed_tools: tuple[Tool, ...] = ()

    def tools(self) -> Sequence[Tool]:
        return self.contributed_tools


@dataclass(frozen=True, slots=True)
class LoadFailure:
    """One plugin that failed to load, with the reason (doc 23 §11)."""

    source: str
    error: AppError


@dataclass(frozen=True, slots=True)
class LoadReport:
    """The outcome of scanning a plugins root (doc 23 §7)."""

    loaded: tuple[str, ...]
    failures: tuple[LoadFailure, ...]


class PluginLoader:
    """Loads plugins from disk into a :class:`PluginRegistry` (doc 23 §7)."""

    def __init__(
        self, *, app_version: str, tool_provider: ToolProvider = _no_tools
    ) -> None:
        self._app_version = app_version
        self._tool_provider = tool_provider

    def load_directory(self, root: Path, registry: PluginRegistry) -> LoadReport:
        """Discover, validate, and register every plugin under ``root`` (doc 23 §7)."""
        loaded: list[str] = []
        failures: list[LoadFailure] = []
        for manifest_path in self._discover(root):
            try:
                plugin = self._load_one(manifest_path)
                registry.register(plugin)
                loaded.append(plugin.manifest.id)
            except AppError as exc:
                failures.append(LoadFailure(source=str(manifest_path), error=exc))
        return LoadReport(loaded=tuple(loaded), failures=tuple(failures))

    def _discover(self, root: Path) -> list[Path]:
        if not root.is_dir():
            return []
        return sorted(
            entry / MANIFEST_NAME
            for entry in root.iterdir()
            if (entry / MANIFEST_NAME).is_file()
        )

    def _load_one(self, manifest_path: Path) -> LoadedPlugin:
        manifest = self._read_manifest(manifest_path)
        validate_manifest(manifest, app_version=self._app_version)
        tools = tuple(self._tool_provider(manifest))
        return LoadedPlugin(manifest=manifest, contributed_tools=tools)

    def _read_manifest(self, path: Path) -> PluginManifest:
        try:
            with path.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise _read_error(str(path), f"cannot read manifest: {exc}") from exc
        try:
            return _manifest_from_toml(data)
        except (KeyError, ValueError, TypeError) as exc:
            raise _read_error(str(path), f"malformed manifest: {exc}") from exc


def _manifest_from_toml(data: dict[str, Any]) -> PluginManifest:
    plugin = data["plugin"]
    contributes = data.get("contributes", {})
    caps = data.get("capabilities-requested", {})
    runtime = data.get("runtime", {})
    return PluginManifest(
        id=str(plugin["id"]),
        name=str(plugin["name"]),
        version=str(plugin["version"]),
        min_app_version=str(plugin["min_app_version"]),
        authors=tuple(str(author) for author in plugin.get("authors", ())),
        license=str(plugin.get("license", "")),
        contributions=Contributions(
            tools=tuple(str(ref) for ref in contributes.get("tools", ()))
        ),
        capabilities=RequestedCapabilities(
            fs=FsAccess(caps.get("fs", "none")),
            net=NetAccess(caps.get("net", "none")),
            shell=ShellAccess(caps.get("shell", "none")),
        ),
        runtime_kind=PluginRuntimeKind(runtime.get("kind", "python")),
        entry=str(runtime.get("entry", "main.py")),
    )


def _read_error(source: str, detail: str) -> AppError:
    return AppError(
        kind=ErrorKind.VALIDATION,
        code=PLUGIN_MANIFEST_READ_CODE,
        message_key=f"hata.{PLUGIN_MANIFEST_READ_CODE}",
        retryable=False,
        detail=f"{source}: {detail}",
    )
