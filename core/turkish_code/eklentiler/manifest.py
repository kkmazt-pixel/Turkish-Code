"""The plugin manifest (doc 23 §4) — the parsed ``plugin.toml`` contract.

:class:`PluginManifest` is the declarative identity + contribution + capability
contract of one plugin. Construction enforces only the light structural
invariants (non-empty identity/entry); semantic validation — semver shape,
``min_app_version`` compatibility, capability coherence — is the validator's job
(:mod:`turkish_code.eklentiler.dogrulama`), kept separate so the manifest stays a
pure value object.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from turkish_code.eklentiler.modeller import (
    Contributions,
    PluginRuntimeKind,
    RequestedCapabilities,
)


@dataclass(frozen=True, slots=True)
class PluginManifest:
    """A plugin's ``plugin.toml`` as an immutable value (doc 23 §4).

    Attributes:
        id: Reverse-DNS plugin id, e.g. ``"org.example.turkce-lint"`` — the
            namespace for its contributions and its registry key (doc 23 §8).
        name: Human-facing display name (Turkish).
        version: The plugin's own semantic version, e.g. ``"1.2.0"``.
        min_app_version: Minimum turkish.code version required (doc 23 §4/§21).
        authors: Free-form author strings.
        license: SPDX-ish license string.
        contributions: What the plugin adds — Tools only this phase (doc 23 §5).
        capabilities: The declared capability contract the user grants (doc 23 §6).
        runtime_kind: How the plugin runs (doc 23 §4).
        entry: Entry module path within the package (doc 23 §4).
    """

    id: str
    name: str
    version: str
    min_app_version: str
    authors: tuple[str, ...] = field(default_factory=tuple)
    license: str = ""
    contributions: Contributions = field(default_factory=Contributions)
    capabilities: RequestedCapabilities = field(default_factory=RequestedCapabilities)
    runtime_kind: PluginRuntimeKind = PluginRuntimeKind.PYTHON
    entry: str = "main.py"

    def __post_init__(self) -> None:
        for name, value in (
            ("id", self.id),
            ("name", self.name),
            ("version", self.version),
            ("min_app_version", self.min_app_version),
            ("entry", self.entry),
        ):
            if not value:
                raise ValueError(f"PluginManifest.{name} must be non-empty")
