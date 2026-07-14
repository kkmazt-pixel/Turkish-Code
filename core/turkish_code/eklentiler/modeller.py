"""Plugin value objects (doc 23 §4/§7) — manifest parts + lifecycle state.

The declarative pieces a :class:`~turkish_code.eklentiler.manifest.PluginManifest`
is assembled from: the requested-capability contract (doc 23 §4/§6 — the single
most security-critical field, an *undeclared* capability is impossible to use),
what the plugin contributes (Tools only in this phase, doc 23 §5), the sandbox
runtime kind, and the registered plugin's lifecycle :class:`PluginState`
(doc 23 §7). Pure data — no behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class FsAccess(StrEnum):
    """Filesystem access a plugin requests (doc 23 §4). Least privilege: none."""

    NONE = "none"
    READ = "read"
    WRITE = "write"


class NetAccess(StrEnum):
    """Network access a plugin requests (doc 23 §4). ``none`` ⇒ offline-safe."""

    NONE = "none"
    EGRESS = "egress"


class ShellAccess(StrEnum):
    """Shell access a plugin requests (doc 23 §4)."""

    NONE = "none"
    EXEC = "exec"


class PluginRuntimeKind(StrEnum):
    """How the plugin runs (doc 23 §4). Only the sandboxed Çekirdek worker here."""

    PYTHON = "python"


class PluginState(StrEnum):
    """A registered plugin's lifecycle state (doc 23 §7).

    A plugin registers ``DISABLED`` (loaded, contributions inert); ``ENABLED``
    means its contributions are live in the host registries; ``FAILED`` marks a
    plugin quarantined after a lifecycle error until it is reloaded (doc 23 §12).
    """

    DISABLED = "disabled"
    ENABLED = "enabled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RequestedCapabilities:
    """The capabilities a plugin declares it needs (doc 23 §4/§6).

    This *is* the security contract: the user grants exactly these at install,
    and nothing undeclared is ever usable. Defaults are the least-privilege,
    offline-safe ``none`` on every axis (doc 23 §3/§6).
    """

    fs: FsAccess = FsAccess.NONE
    net: NetAccess = NetAccess.NONE
    shell: ShellAccess = ShellAccess.NONE


@dataclass(frozen=True, slots=True)
class Contributions:
    """What a plugin adds to the host (doc 23 §5).

    This phase supports Tool contributions only (doc 20); each entry is a
    reference to a ToolDef the plugin provides. Other contribution types
    (skills/providers/agents/UI) are out of scope.
    """

    tools: tuple[str, ...] = field(default_factory=tuple)
