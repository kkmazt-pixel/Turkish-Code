"""Manifest validation (doc 23 §7 VALIDATE, §11) — reject invalid, fail-safe.

Turns a parsed :class:`PluginManifest` into a trusted one or a typed
:class:`AppError`: the semantic checks the value object deliberately omits — the
semver shape of the plugin ``version`` and ``min_app_version``, compatibility of
the running app against ``min_app_version`` (doc 23 §21), a well-formed
namespaced id (doc 23 §8), and coherent tool contributions. Any failure rejects
the plugin wholesale — no partial load (doc 23 §11). :func:`declared_capabilities`
surfaces the exact capability set the user must grant (doc 23 §4/§6).
"""

from __future__ import annotations

import re

from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import FsAccess, NetAccess, ShellAccess
from turkish_code.hata import AppError, ErrorKind

PLUGIN_INVALID_VERSION_CODE = "plugin.invalid_version"
PLUGIN_INCOMPATIBLE_CODE = "plugin.incompatible"
PLUGIN_INVALID_ID_CODE = "plugin.invalid_id"
PLUGIN_INVALID_MANIFEST_CODE = "plugin.invalid_manifest"

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_PLUGIN_ID = re.compile(
    r"^[a-z0-9]+(?:[-a-z0-9]*[a-z0-9])?(?:\.[a-z0-9]+(?:[-a-z0-9]*[a-z0-9])?)+$"
)


def parse_semver(value: str) -> tuple[int, int, int]:
    """Parse a strict ``MAJOR.MINOR.PATCH`` version, or raise ``ValueError``."""
    match = _SEMVER.match(value)
    if match is None:
        raise ValueError(f"not a MAJOR.MINOR.PATCH version: {value!r}")
    return int(match[1]), int(match[2]), int(match[3])


def validate_manifest(manifest: PluginManifest, *, app_version: str) -> None:
    """Validate ``manifest`` against the running ``app_version`` (doc 23 §7).

    Raises a typed ``VALIDATION`` :class:`AppError` on the first problem;
    returns ``None`` when the manifest is trusted.
    """
    _validate_id(manifest)
    _require_semver(manifest.version, manifest, "version")
    min_app = _require_semver(manifest.min_app_version, manifest, "min_app_version")
    _validate_compatibility(manifest, min_app=min_app, app_version=app_version)
    _validate_contributions(manifest)


def declared_capabilities(manifest: PluginManifest) -> frozenset[str]:
    """The non-``none`` capabilities the manifest declares (doc 23 §4/§6).

    The exact set the user must grant; empty means an offline-safe, no-privilege
    plugin. Returned as stable ``"axis:level"`` tokens, e.g. ``"fs:read"``.
    """
    caps = manifest.capabilities
    declared: set[str] = set()
    if caps.fs is not FsAccess.NONE:
        declared.add(f"fs:{caps.fs.value}")
    if caps.net is not NetAccess.NONE:
        declared.add(f"net:{caps.net.value}")
    if caps.shell is not ShellAccess.NONE:
        declared.add(f"shell:{caps.shell.value}")
    return frozenset(declared)


def _validate_id(manifest: PluginManifest) -> None:
    # A well-formed reverse-DNS id keeps contributions namespaced and safe as a
    # registry key / future path segment (doc 23 §8).
    if _PLUGIN_ID.match(manifest.id) is None:
        raise _err(PLUGIN_INVALID_ID_CODE, f"invalid plugin id: {manifest.id!r}")


def _require_semver(
    value: str, manifest: PluginManifest, field: str
) -> tuple[int, int, int]:
    try:
        return parse_semver(value)
    except ValueError as exc:
        raise _err(
            PLUGIN_INVALID_VERSION_CODE, f"{manifest.id}: {field} {exc}"
        ) from exc


def _validate_compatibility(
    manifest: PluginManifest,
    *,
    min_app: tuple[int, int, int],
    app_version: str,
) -> None:
    try:
        current = parse_semver(app_version)
    except ValueError as exc:
        raise _err(PLUGIN_INVALID_VERSION_CODE, f"app_version {exc}") from exc
    if current < min_app:
        raise _err(
            PLUGIN_INCOMPATIBLE_CODE,
            f"{manifest.id} needs app >= {manifest.min_app_version}, "
            f"running {app_version}",
        )


def _validate_contributions(manifest: PluginManifest) -> None:
    tools = manifest.contributions.tools
    if any(not ref.strip() for ref in tools):
        raise _err(
            PLUGIN_INVALID_MANIFEST_CODE,
            f"{manifest.id}: empty tool contribution reference",
        )
    if len(set(tools)) != len(tools):
        raise _err(
            PLUGIN_INVALID_MANIFEST_CODE,
            f"{manifest.id}: duplicate tool contribution reference",
        )


def _err(code: str, detail: str) -> AppError:
    return AppError(
        kind=ErrorKind.VALIDATION,
        code=code,
        message_key=f"hata.{code}",
        retryable=False,
        detail=detail,
    )
