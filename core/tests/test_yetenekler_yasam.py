"""Tests for the skill lifecycle (doc 19 §10/§14)."""

from __future__ import annotations

import pytest
from turkish_code.hata import AppError, ErrorKind
from turkish_code.yetenekler.baglam import SkillContext
from turkish_code.yetenekler.dagitici import SkillDispatcher
from turkish_code.yetenekler.hata import SKILL_DUPLICATE_CODE, SKILL_NOT_FOUND_CODE
from turkish_code.yetenekler.kayit import SkillRegistry
from turkish_code.yetenekler.modeller import (
    SkillMetadata,
    SkillRequest,
    SkillResult,
    SkillState,
)
from turkish_code.yetenekler.yasam import SkillLifecycle


class _StubSkill:
    def __init__(self, skill_id: str) -> None:
        self._metadata = SkillMetadata(id=skill_id, description="ne zaman")

    @property
    def metadata(self) -> SkillMetadata:
        return self._metadata

    async def run(self, request: SkillRequest, context: SkillContext) -> SkillResult:
        return SkillResult(invocation_id=request.invocation_id, output="ran")


def _lifecycle() -> tuple[SkillRegistry, SkillLifecycle]:
    registry = SkillRegistry()
    return registry, SkillLifecycle(registry)


def test_load_is_disabled_and_not_yet_invocable() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.load(_StubSkill("a"))
    assert lifecycle.state_of("a") is SkillState.DISABLED
    assert "a" not in registry  # not registered until enabled


def test_duplicate_load_is_rejected() -> None:
    _, lifecycle = _lifecycle()
    lifecycle.load(_StubSkill("a"))
    with pytest.raises(AppError) as exc_info:
        lifecycle.load(_StubSkill("a"))
    assert exc_info.value.code == SKILL_DUPLICATE_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_enable_makes_skill_invocable() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.load(_StubSkill("a"))
    lifecycle.enable("a")
    assert lifecycle.state_of("a") is SkillState.ENABLED
    assert lifecycle.is_enabled("a")
    assert "a" in registry  # now resolvable by the dispatcher


def test_enable_is_idempotent() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.load(_StubSkill("a"))
    lifecycle.enable("a")
    lifecycle.enable("a")  # no duplicate registration
    assert registry.ids() == ["a"]


def test_disable_withdraws_from_registry() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.load(_StubSkill("a"))
    lifecycle.enable("a")
    lifecycle.disable("a")
    assert lifecycle.state_of("a") is SkillState.DISABLED
    assert "a" not in registry


def test_mark_failed_quarantines_and_withdraws() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.load(_StubSkill("a"))
    lifecycle.enable("a")
    lifecycle.mark_failed("a")
    assert lifecycle.state_of("a") is SkillState.FAILED
    assert "a" not in registry


def test_recover_resets_failed_to_disabled() -> None:
    _, lifecycle = _lifecycle()
    lifecycle.load(_StubSkill("a"))
    lifecycle.mark_failed("a")
    lifecycle.recover("a")
    assert lifecycle.state_of("a") is SkillState.DISABLED


def test_unload_forgets_skill() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.load(_StubSkill("a"))
    lifecycle.enable("a")
    removed = lifecycle.unload("a")
    assert removed.metadata.id == "a"
    assert lifecycle.loaded_ids() == []
    assert "a" not in registry
    with pytest.raises(AppError):
        lifecycle.state_of("a")


def test_operations_on_unknown_skill_raise_not_found() -> None:
    _, lifecycle = _lifecycle()
    for op in (
        lifecycle.enable,
        lifecycle.disable,
        lifecycle.mark_failed,
        lifecycle.unload,
        lifecycle.state_of,
    ):
        with pytest.raises(AppError) as exc_info:
            op("absent")
        assert exc_info.value.code == SKILL_NOT_FOUND_CODE


def test_enabled_and_loaded_ids() -> None:
    _, lifecycle = _lifecycle()
    for sid in ("c", "a", "b"):
        lifecycle.load(_StubSkill(sid))
    lifecycle.enable("a")
    lifecycle.enable("c")
    assert lifecycle.loaded_ids() == ["a", "b", "c"]
    assert lifecycle.enabled_ids() == ["a", "c"]


@pytest.mark.asyncio
async def test_disabled_skill_is_not_invocable_via_dispatcher() -> None:
    registry, lifecycle = _lifecycle()
    dispatcher = SkillDispatcher(registry)
    lifecycle.load(_StubSkill("a"))
    lifecycle.enable("a")
    result = await dispatcher.invoke(
        SkillRequest(skill_id="a", inputs={}, invocation_id="i1")
    )
    assert result.output == "ran"

    lifecycle.disable("a")
    with pytest.raises(AppError) as exc_info:  # withdrawn → dispatcher can't find it
        await dispatcher.invoke(
            SkillRequest(skill_id="a", inputs={}, invocation_id="i2")
        )
    assert exc_info.value.code == SKILL_NOT_FOUND_CODE
