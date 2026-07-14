"""Tests for skill models, metadata, and the Skill Protocol (doc 19 §4/§9)."""

from __future__ import annotations

import pytest
from turkish_code.yetenekler.baglam import SkillContext
from turkish_code.yetenekler.modeller import (
    SkillMetadata,
    SkillRequest,
    SkillResult,
    SkillScope,
)
from turkish_code.yetenekler.protocol import Skill


def _meta(**overrides: object) -> SkillMetadata:
    base: dict[str, object] = {
        "id": "tauri-komut-yaz",
        "description": "Yeni bir Tauri Bridge komutu eklemek gerektiğinde kullan",
    }
    base.update(overrides)
    return SkillMetadata(**base)  # type: ignore[arg-type]


def test_scope_wire_values() -> None:
    assert SkillScope.WORKSPACE.value == "workspace"
    assert SkillScope.GLOBAL.value == "global"


def test_metadata_defaults_are_least_privilege() -> None:
    meta = _meta()
    assert meta.allowed_tools == frozenset()
    assert meta.requires == frozenset()
    assert meta.scope is SkillScope.WORKSPACE
    assert meta.timeout_ms == 30_000
    assert meta.version == 1


def test_metadata_allows_tool() -> None:
    meta = _meta(allowed_tools=frozenset({"fs.read", "fs.write"}))
    assert meta.allows_tool("fs.read")
    assert not meta.allows_tool("shell.exec")


def test_metadata_rejects_empty_id() -> None:
    with pytest.raises(ValueError, match="id must be non-empty"):
        _meta(id="")


def test_metadata_rejects_empty_description() -> None:
    with pytest.raises(ValueError, match="description must be non-empty"):
        _meta(description="")


def test_metadata_rejects_non_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_ms must be positive"):
        _meta(timeout_ms=0)


def test_metadata_rejects_bad_version() -> None:
    with pytest.raises(ValueError, match="version must be"):
        _meta(version=0)


def test_metadata_is_immutable() -> None:
    meta = _meta()
    with pytest.raises(AttributeError):
        meta.id = "other"  # type: ignore[misc]


def test_request_and_result_correlate_by_invocation_id() -> None:
    req = SkillRequest(skill_id="s", inputs={"x": 1}, invocation_id="i1", run_id="r1")
    result = SkillResult(invocation_id=req.invocation_id, output={"ok": True})
    assert result.invocation_id == "i1"
    assert req.run_id == "r1"


def test_request_run_id_defaults_to_none() -> None:
    req = SkillRequest(skill_id="s", inputs={}, invocation_id="i")
    assert req.run_id is None


def test_context_holds_correlation_ids() -> None:
    ctx = SkillContext(invocation_id="i2", run_id="r2")
    assert ctx.invocation_id == "i2" and ctx.run_id == "r2"


class _StubSkill:
    """A minimal structural :class:`Skill` — proves the Protocol is satisfiable."""

    def __init__(self, metadata: SkillMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> SkillMetadata:
        return self._metadata

    async def run(self, request: SkillRequest, context: SkillContext) -> SkillResult:
        return SkillResult(invocation_id=request.invocation_id, output=None)


def test_concrete_skill_satisfies_protocol() -> None:
    assert isinstance(_StubSkill(_meta()), Skill)


def test_plain_object_is_not_a_skill() -> None:
    assert not isinstance(object(), Skill)
