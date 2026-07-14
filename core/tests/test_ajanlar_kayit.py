"""Tests for the agent registry (doc 18 §10)."""

from __future__ import annotations

import pytest
from turkish_code.ajanlar.baglam import AgentContext
from turkish_code.ajanlar.kayit import (
    AGENT_DUPLICATE_CODE,
    AGENT_NO_DEFAULT_CODE,
    AGENT_NOT_FOUND_CODE,
    AgentRegistry,
)
from turkish_code.ajanlar.modeller import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
)
from turkish_code.hata import AppError, ErrorKind


class _StubAgent:
    def __init__(self, agent_id: str, role: str = "worker") -> None:
        self._metadata = AgentMetadata(
            id=agent_id, name=agent_id, role=role, summary="s"
        )

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        return AgentResponse(run_id=request.run_id, output="ok")


def test_register_then_resolve() -> None:
    registry = AgentRegistry()
    agent = _StubAgent("yonetici")
    registry.register(agent)
    assert registry.resolve("yonetici") is agent


def test_duplicate_registration_is_rejected() -> None:
    registry = AgentRegistry()
    registry.register(_StubAgent("a"))
    with pytest.raises(AppError) as exc_info:
        registry.register(_StubAgent("a"))
    assert exc_info.value.code == AGENT_DUPLICATE_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_resolve_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        AgentRegistry().resolve("absent")
    assert exc_info.value.code == AGENT_NOT_FOUND_CODE
    assert exc_info.value.kind is ErrorKind.NOT_FOUND


def test_get_returns_none_for_missing() -> None:
    assert AgentRegistry().get("absent") is None


def test_contains_and_len() -> None:
    registry = AgentRegistry()
    registry.register(_StubAgent("a"))
    assert "a" in registry
    assert "absent" not in registry
    assert 42 not in registry
    assert len(registry) == 1


def test_ids_are_sorted() -> None:
    registry = AgentRegistry()
    for aid in ("z", "a", "m"):
        registry.register(_StubAgent(aid))
    assert registry.ids() == ["a", "m", "z"]


def test_by_role_groups_agents() -> None:
    registry = AgentRegistry()
    registry.register(_StubAgent("impl1", role="kodlayici"))
    registry.register(_StubAgent("rev", role="reviewer"))
    registry.register(_StubAgent("impl2", role="kodlayici"))
    assert [a.metadata.id for a in registry.by_role("kodlayici")] == ["impl1", "impl2"]
    assert registry.by_role("absent") == []


def test_roles_are_distinct_and_sorted() -> None:
    registry = AgentRegistry()
    registry.register(_StubAgent("a", role="reviewer"))
    registry.register(_StubAgent("b", role="kodlayici"))
    registry.register(_StubAgent("c", role="kodlayici"))
    assert registry.roles() == ["kodlayici", "reviewer"]


def test_register_with_default_flag_sets_default() -> None:
    registry = AgentRegistry()
    agent = _StubAgent("yonetici")
    registry.register(agent, default=True)
    assert registry.default_id() == "yonetici"
    assert registry.default() is agent
    assert registry.resolve_default() is agent


def test_set_default_requires_registration() -> None:
    registry = AgentRegistry()
    registry.register(_StubAgent("a"))
    registry.set_default("a")
    assert registry.default_id() == "a"
    with pytest.raises(AppError) as exc_info:
        registry.set_default("absent")
    assert exc_info.value.code == AGENT_NOT_FOUND_CODE


def test_default_is_none_when_unset() -> None:
    registry = AgentRegistry()
    registry.register(_StubAgent("a"))
    assert registry.default_id() is None
    assert registry.default() is None


def test_resolve_default_without_default_raises() -> None:
    registry = AgentRegistry()
    registry.register(_StubAgent("a"))
    with pytest.raises(AppError) as exc_info:
        registry.resolve_default()
    assert exc_info.value.code == AGENT_NO_DEFAULT_CODE
