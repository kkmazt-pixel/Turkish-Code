"""Tests for manifest validation (doc 23 §7/§11)."""

from __future__ import annotations

import pytest
from turkish_code.eklentiler.dogrulama import (
    PLUGIN_INCOMPATIBLE_CODE,
    PLUGIN_INVALID_ID_CODE,
    PLUGIN_INVALID_MANIFEST_CODE,
    PLUGIN_INVALID_VERSION_CODE,
    declared_capabilities,
    parse_semver,
    validate_manifest,
)
from turkish_code.eklentiler.manifest import PluginManifest
from turkish_code.eklentiler.modeller import (
    Contributions,
    FsAccess,
    NetAccess,
    RequestedCapabilities,
    ShellAccess,
)
from turkish_code.hata import AppError, ErrorKind


def _manifest(**overrides: object) -> PluginManifest:
    base: dict[str, object] = {
        "id": "org.example.lint",
        "name": "Lint",
        "version": "1.2.0",
        "min_app_version": "1.0.0",
    }
    base.update(overrides)
    return PluginManifest(**base)  # type: ignore[arg-type]


def test_parse_semver_returns_tuple() -> None:
    assert parse_semver("1.2.3") == (1, 2, 3)


@pytest.mark.parametrize("bad", ["1.2", "1.2.3.4", "v1.2.3", "1.2.x", "", "1.2.3-beta"])
def test_parse_semver_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError, match="MAJOR.MINOR.PATCH"):
        parse_semver(bad)


def test_valid_manifest_passes() -> None:
    validate_manifest(_manifest(), app_version="1.5.0")  # no raise


def test_invalid_plugin_version_is_rejected() -> None:
    with pytest.raises(AppError) as exc_info:
        validate_manifest(_manifest(version="1.x"), app_version="1.5.0")
    assert exc_info.value.code == PLUGIN_INVALID_VERSION_CODE
    assert exc_info.value.kind is ErrorKind.VALIDATION


def test_invalid_min_app_version_is_rejected() -> None:
    with pytest.raises(AppError) as exc_info:
        validate_manifest(_manifest(min_app_version="nope"), app_version="1.5.0")
    assert exc_info.value.code == PLUGIN_INVALID_VERSION_CODE


def test_app_older_than_min_app_version_is_incompatible() -> None:
    with pytest.raises(AppError) as exc_info:
        validate_manifest(_manifest(min_app_version="2.0.0"), app_version="1.5.0")
    assert exc_info.value.code == PLUGIN_INCOMPATIBLE_CODE
    assert exc_info.value.kind is ErrorKind.VALIDATION


def test_app_equal_to_min_app_version_is_compatible() -> None:
    validate_manifest(_manifest(min_app_version="1.5.0"), app_version="1.5.0")


def test_malformed_app_version_is_rejected() -> None:
    with pytest.raises(AppError) as exc_info:
        validate_manifest(_manifest(), app_version="dev")
    assert exc_info.value.code == PLUGIN_INVALID_VERSION_CODE


@pytest.mark.parametrize("bad_id", ["nodots", "UPPER.Case", "org..example", "a.-b", ""])
def test_malformed_plugin_id_is_rejected(bad_id: str) -> None:
    with pytest.raises(AppError) as exc_info:
        validate_manifest(_manifest(id=bad_id or "x"), app_version="1.5.0")
    # empty id fails the manifest's own non-empty guard before validation.
    assert exc_info.value.code in {PLUGIN_INVALID_ID_CODE}


def test_reverse_dns_id_is_accepted() -> None:
    validate_manifest(_manifest(id="org.example.turkce-lint"), app_version="1.5.0")


def test_empty_tool_reference_is_rejected() -> None:
    manifest = _manifest(contributions=Contributions(tools=("tools/a", "  ")))
    with pytest.raises(AppError) as exc_info:
        validate_manifest(manifest, app_version="1.5.0")
    assert exc_info.value.code == PLUGIN_INVALID_MANIFEST_CODE


def test_duplicate_tool_reference_is_rejected() -> None:
    manifest = _manifest(contributions=Contributions(tools=("tools/a", "tools/a")))
    with pytest.raises(AppError) as exc_info:
        validate_manifest(manifest, app_version="1.5.0")
    assert exc_info.value.code == PLUGIN_INVALID_MANIFEST_CODE


def test_declared_capabilities_lists_non_none_axes() -> None:
    manifest = _manifest(
        capabilities=RequestedCapabilities(
            fs=FsAccess.READ, net=NetAccess.EGRESS, shell=ShellAccess.NONE
        )
    )
    assert declared_capabilities(manifest) == frozenset({"fs:read", "net:egress"})


def test_declared_capabilities_empty_for_offline_safe_plugin() -> None:
    assert declared_capabilities(_manifest()) == frozenset()
