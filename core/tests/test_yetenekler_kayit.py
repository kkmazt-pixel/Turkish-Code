"""Tests for the skill registry (doc 19 §5/§7)."""

from __future__ import annotations

import pytest
from turkish_code.hata import AppError, ErrorKind
from turkish_code.yetenekler.baglam import SkillContext
from turkish_code.yetenekler.hata import SKILL_DUPLICATE_CODE, SKILL_NOT_FOUND_CODE
from turkish_code.yetenekler.kayit import SkillRegistry
from turkish_code.yetenekler.modeller import (
    SkillMetadata,
    SkillRequest,
    SkillResult,
    SkillScope,
)


class _StubSkill:
    def __init__(
        self,
        skill_id: str,
        *,
        scope: SkillScope = SkillScope.WORKSPACE,
        version: int = 1,
    ) -> None:
        self._metadata = SkillMetadata(
            id=skill_id, description="ne zaman kullanılır", scope=scope, version=version
        )

    @property
    def metadata(self) -> SkillMetadata:
        return self._metadata

    async def run(self, request: SkillRequest, context: SkillContext) -> SkillResult:
        return SkillResult(invocation_id=request.invocation_id, output=None)


def test_register_then_resolve() -> None:
    registry = SkillRegistry()
    skill = _StubSkill("tauri-komut")
    registry.register(skill)
    assert registry.resolve("tauri-komut") is skill


def test_duplicate_registration_is_rejected() -> None:
    registry = SkillRegistry()
    registry.register(_StubSkill("a"))
    with pytest.raises(AppError) as exc_info:
        registry.register(_StubSkill("a"))
    assert exc_info.value.code == SKILL_DUPLICATE_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_resolve_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        SkillRegistry().resolve("absent")
    assert exc_info.value.code == SKILL_NOT_FOUND_CODE
    assert exc_info.value.kind is ErrorKind.NOT_FOUND


def test_get_returns_none_for_missing() -> None:
    assert SkillRegistry().get("absent") is None


def test_contains_and_len() -> None:
    registry = SkillRegistry()
    registry.register(_StubSkill("a"))
    assert "a" in registry
    assert "absent" not in registry
    assert 7 not in registry
    assert len(registry) == 1


def test_register_all_adds_each() -> None:
    registry = SkillRegistry()
    registry.register_all([_StubSkill("a"), _StubSkill("b")])
    assert registry.ids() == ["a", "b"]


def test_register_all_aborts_on_first_duplicate() -> None:
    registry = SkillRegistry()
    with pytest.raises(AppError):
        registry.register_all([_StubSkill("a"), _StubSkill("b"), _StubSkill("a")])
    assert registry.ids() == ["a", "b"]  # the second "a" is what failed


def test_ids_are_sorted() -> None:
    registry = SkillRegistry()
    registry.register_all([_StubSkill("z"), _StubSkill("a"), _StubSkill("m")])
    assert registry.ids() == ["a", "m", "z"]


def test_catalog_returns_metadata_sorted() -> None:
    registry = SkillRegistry()
    registry.register_all([_StubSkill("b", version=3), _StubSkill("a", version=2)])
    catalog = registry.catalog()
    assert [m.id for m in catalog] == ["a", "b"]
    assert [m.version for m in catalog] == [2, 3]


def test_by_scope_groups_skills() -> None:
    registry = SkillRegistry()
    registry.register(_StubSkill("w1", scope=SkillScope.WORKSPACE))
    registry.register(_StubSkill("g1", scope=SkillScope.GLOBAL))
    registry.register(_StubSkill("w2", scope=SkillScope.WORKSPACE))
    workspace = registry.by_scope(SkillScope.WORKSPACE)
    assert [s.metadata.id for s in workspace] == ["w1", "w2"]
    globals_ = registry.by_scope(SkillScope.GLOBAL)
    assert [s.metadata.id for s in globals_] == ["g1"]


def test_version_of_returns_registered_version() -> None:
    registry = SkillRegistry()
    registry.register(_StubSkill("a", version=5))
    assert registry.version_of("a") == 5


def test_version_of_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        SkillRegistry().version_of("absent")
    assert exc_info.value.code == SKILL_NOT_FOUND_CODE
