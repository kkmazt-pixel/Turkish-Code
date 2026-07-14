"""Tests for agent-runtime composition + container wiring (doc 18 §10, doc 09 §7)."""

from __future__ import annotations

import pytest
from turkish_code.ajanlar.baglam import AgentContext
from turkish_code.ajanlar.dagitici import AgentDispatcher
from turkish_code.ajanlar.kayit import AgentRegistry
from turkish_code.ajanlar.kompozisyon import AgentRuntime, build_agent_runtime
from turkish_code.ajanlar.modeller import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
)
from turkish_code.ajanlar.yasam import SessionLifecycle
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


class _ToolUsingAgent:
    """An agent whose run invokes a tool through its execution context."""

    def __init__(self, agent_id: str, grants: frozenset[str], tool: str) -> None:
        self._id = agent_id
        self._grants = grants
        self._tool = tool

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            id=self._id,
            name=self._id,
            role="worker",
            summary="s",
            tool_grants=self._grants,
        )

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        assert context.execution is not None
        result = await context.execution.invoke_tool(
            ToolRequest(name=self._tool, arguments={}, call_id=request.run_id)
        )
        return AgentResponse(run_id=request.run_id, output=str(result.output))


def test_build_returns_wired_graph() -> None:
    runtime = build_agent_runtime(_tool_dispatcher())
    assert isinstance(runtime, AgentRuntime)
    assert isinstance(runtime.registry, AgentRegistry)
    assert isinstance(runtime.dispatcher, AgentDispatcher)
    assert isinstance(runtime.lifecycle, SessionLifecycle)
    assert len(runtime.registry) == 0


def test_build_registers_agents_and_default() -> None:
    agent = _ToolUsingAgent("yonetici", frozenset(), "x")
    runtime = build_agent_runtime(
        _tool_dispatcher(), agents=[agent], default_agent_id="yonetici"
    )
    assert runtime.registry.resolve("yonetici") is agent
    assert runtime.registry.default_id() == "yonetici"


def test_execution_for_scopes_to_agent_grants() -> None:
    runtime = build_agent_runtime(_tool_dispatcher("code.search"))
    agent = _ToolUsingAgent("a", frozenset({"code.search"}), "code.search")
    execution = runtime.execution_for(agent)
    assert execution.grants_tool("code.search")
    assert not execution.grants_tool("fs.write")


@pytest.mark.asyncio
async def test_end_to_end_agent_invokes_granted_tool() -> None:
    dispatcher = _tool_dispatcher("code.search")
    agent = _ToolUsingAgent("a", frozenset({"code.search"}), "code.search")
    runtime = build_agent_runtime(dispatcher, agents=[agent])
    execution = runtime.execution_for(agent)
    response = await runtime.dispatcher.dispatch(
        AgentRequest(agent_id="a", message="ara", run_id="r1"), execution=execution
    )
    assert response.output == "code.search-ran"


@pytest.mark.asyncio
async def test_end_to_end_agent_denied_ungranted_tool() -> None:
    dispatcher = _tool_dispatcher("fs.write")
    agent = _ToolUsingAgent("a", frozenset({"code.search"}), "fs.write")  # not granted
    runtime = build_agent_runtime(dispatcher, agents=[agent])
    execution = runtime.execution_for(agent)
    with pytest.raises(AppError):  # wrapped as agent.failed via the run's AppError
        await runtime.dispatcher.dispatch(
            AgentRequest(agent_id="a", message="yaz", run_id="r1"), execution=execution
        )


def test_container_exposes_agent_runtime_with_provider() -> None:
    from turkish_code.kompozisyon import build_container
    from turkish_code.yapilandirma.yukleyici import load_settings

    container = build_container(load_settings(environ={}))
    assert isinstance(container.agent_runtime, AgentRuntime)
    assert len(container.agent_runtime.registry) == 0
    # Provider Runtime is integrated; Storage is wired separately (async).
    assert container.agent_runtime.provider is container.provider_manager
    assert container.agent_runtime.storage is None


@pytest.mark.asyncio
async def test_container_agent_runtime_shares_tool_dispatcher() -> None:
    from turkish_code.kompozisyon import build_container
    from turkish_code.yapilandirma.yukleyici import load_settings

    container = build_container(load_settings(environ={}))
    # Register a tool + a granting agent, then run it through the container graph.
    container.tool_runtime.registry.register(_EchoTool("code.search"))
    agent = _ToolUsingAgent("a", frozenset({"code.search"}), "code.search")
    container.agent_runtime.registry.register(agent)
    execution = container.agent_runtime.execution_for(agent)
    response = await container.agent_runtime.dispatcher.dispatch(
        AgentRequest(agent_id="a", message="ara", run_id="r1"), execution=execution
    )
    assert response.output == "code.search-ran"
