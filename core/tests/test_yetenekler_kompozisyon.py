"""Tests for skill-runtime composition + container wiring (doc 19 §7, doc 09 §7)."""

from __future__ import annotations

import pytest
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.izin import (
    PermissionMode,
    PermissionPolicy,
    PolicyPermissionGate,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.modeller import (
    SideEffect,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from turkish_code.hata import AppError
from turkish_code.yetenekler.baglam import SkillContext
from turkish_code.yetenekler.dagitici import SkillDispatcher
from turkish_code.yetenekler.kayit import SkillRegistry
from turkish_code.yetenekler.kompozisyon import SkillRuntime, build_skill_runtime
from turkish_code.yetenekler.modeller import (
    SkillMetadata,
    SkillRequest,
    SkillResult,
)
from turkish_code.yetenekler.yasam import SkillLifecycle


class _EchoTool:
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self._name,
            summary=self._name,
            capability=None,
            side_effect=SideEffect.READ,
            brokered=False,
            reversible=False,
            idempotent=True,
            timeout_ms=1000,
        )

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output=f"{self._name}-ran")


def _tool_dispatcher(*names: str) -> ToolDispatcher:
    registry = ToolRegistry()
    for name in names:
        registry.register(_EchoTool(name))
    gate = PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    return ToolDispatcher(registry, gate)


class _ToolUsingSkill:
    """A skill whose run invokes a tool through its execution context."""

    def __init__(self, skill_id: str, allowed: frozenset[str], tool: str) -> None:
        self._id = skill_id
        self._allowed = allowed
        self._tool = tool

    @property
    def metadata(self) -> SkillMetadata:
        return SkillMetadata(
            id=self._id, description="ne zaman", allowed_tools=self._allowed
        )

    async def run(self, request: SkillRequest, context: SkillContext) -> SkillResult:
        assert context.execution is not None
        result = await context.execution.invoke_tool(
            ToolRequest(name=self._tool, arguments={}, call_id=request.invocation_id)
        )
        return SkillResult(
            invocation_id=request.invocation_id, output=str(result.output)
        )


def test_build_returns_wired_graph() -> None:
    runtime = build_skill_runtime(_tool_dispatcher())
    assert isinstance(runtime, SkillRuntime)
    assert isinstance(runtime.registry, SkillRegistry)
    assert isinstance(runtime.dispatcher, SkillDispatcher)
    assert isinstance(runtime.lifecycle, SkillLifecycle)
    assert len(runtime.registry) == 0


def test_provided_skills_are_loaded_and_enabled() -> None:
    skill = _ToolUsingSkill("s", frozenset(), "x")
    runtime = build_skill_runtime(_tool_dispatcher(), skills=[skill])
    assert runtime.lifecycle.is_enabled("s")
    assert "s" in runtime.registry  # enabled → invocable


def test_execution_for_scopes_to_allowed_tools() -> None:
    runtime = build_skill_runtime(_tool_dispatcher("code.search"))
    skill = _ToolUsingSkill("s", frozenset({"code.search"}), "code.search")
    execution = runtime.execution_for(skill)
    assert execution.allows_tool("code.search")
    assert not execution.allows_tool("fs.write")


@pytest.mark.asyncio
async def test_end_to_end_skill_invokes_allowed_tool() -> None:
    dispatcher = _tool_dispatcher("code.search")
    skill = _ToolUsingSkill("s", frozenset({"code.search"}), "code.search")
    runtime = build_skill_runtime(dispatcher, skills=[skill])
    response = await runtime.dispatcher.invoke(
        SkillRequest(skill_id="s", inputs={}, invocation_id="i1"),
        execution=runtime.execution_for(skill),
    )
    assert response.output == "code.search-ran"


@pytest.mark.asyncio
async def test_end_to_end_skill_denied_disallowed_tool() -> None:
    dispatcher = _tool_dispatcher("fs.write")
    skill = _ToolUsingSkill("s", frozenset({"code.search"}), "fs.write")  # not allowed
    runtime = build_skill_runtime(dispatcher, skills=[skill])
    with pytest.raises(AppError):
        await runtime.dispatcher.invoke(
            SkillRequest(skill_id="s", inputs={}, invocation_id="i1"),
            execution=runtime.execution_for(skill),
        )


def test_container_exposes_skill_runtime_with_facades() -> None:
    from turkish_code.kompozisyon import build_container
    from turkish_code.yapilandirma.yukleyici import load_settings

    container = build_container(load_settings(environ={}))
    assert isinstance(container.skill_runtime, SkillRuntime)
    assert len(container.skill_runtime.registry) == 0
    # Agent + Provider runtimes integrated; Storage wired separately (async).
    assert container.skill_runtime.agents is container.agent_runtime
    assert container.skill_runtime.provider is container.provider_manager
    assert container.skill_runtime.storage is None


@pytest.mark.asyncio
async def test_container_skill_runtime_shares_tool_dispatcher() -> None:
    from turkish_code.kompozisyon import build_container
    from turkish_code.yapilandirma.yukleyici import load_settings

    container = build_container(load_settings(environ={}))
    container.tool_runtime.registry.register(_EchoTool("code.search"))
    skill = _ToolUsingSkill("s", frozenset({"code.search"}), "code.search")
    container.skill_runtime.lifecycle.load(skill)
    container.skill_runtime.lifecycle.enable("s")
    response = await container.skill_runtime.dispatcher.invoke(
        SkillRequest(skill_id="s", inputs={}, invocation_id="i1"),
        execution=container.skill_runtime.execution_for(skill),
    )
    assert response.output == "code.search-ran"
