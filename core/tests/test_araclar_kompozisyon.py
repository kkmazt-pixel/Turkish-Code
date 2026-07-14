"""Tests for tool-runtime composition + container wiring (doc 20, doc 09 §7)."""

from __future__ import annotations

import pytest
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.izin import (
    Allow,
    Grant,
    PermissionMode,
    PermissionRequest,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.kompozisyon import ToolRuntime, build_tool_runtime
from turkish_code.araclar.modeller import (
    Capability,
    SideEffect,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)


class _StubTool:
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name=self._name,
            summary=f"{self._name} aracı",
            capability=None,
            side_effect=SideEffect.READ,
            brokered=False,
            reversible=False,
            idempotent=True,
            timeout_ms=1000,
        )

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output="ok")


def test_build_tool_runtime_returns_wired_graph() -> None:
    runtime = build_tool_runtime()
    assert isinstance(runtime, ToolRuntime)
    assert isinstance(runtime.registry, ToolRegistry)
    assert isinstance(runtime.dispatcher, ToolDispatcher)
    assert len(runtime.registry) == 0  # no first-party tools yet


def test_build_registers_injected_tools() -> None:
    runtime = build_tool_runtime(tools=[_StubTool("a"), _StubTool("b")])
    assert runtime.registry.names() == ["a", "b"]


def test_dispatcher_shares_the_runtime_registry_and_gate() -> None:
    runtime = build_tool_runtime(tools=[_StubTool("a")])
    # The dispatcher resolves against the same registry the runtime exposes.
    assert runtime.dispatcher._registry is runtime.registry
    assert runtime.dispatcher._gate is runtime.gate


@pytest.mark.asyncio
async def test_default_gate_is_ask_mode() -> None:
    # Ask + ungranted mutation → PromptRequired, not Allow (doc 24 §5 default).
    runtime = build_tool_runtime()
    decision = await runtime.gate.evaluate(
        PermissionRequest(
            tool="fs.write",
            capability=Capability.FS_WRITE,
            side_effect=SideEffect.MUTATE,
        )
    )
    assert not isinstance(decision, Allow)


@pytest.mark.asyncio
async def test_permission_mode_and_grants_are_injectable() -> None:
    runtime = build_tool_runtime(
        permission_mode=PermissionMode.ASK,
        grants=frozenset({Grant(Capability.FS_WRITE)}),
    )
    decision = await runtime.gate.evaluate(
        PermissionRequest(
            tool="fs.write",
            capability=Capability.FS_WRITE,
            side_effect=SideEffect.MUTATE,
        )
    )
    assert isinstance(decision, Allow)  # the injected grant allows it


@pytest.mark.asyncio
async def test_injected_gate_is_used_verbatim() -> None:
    class _AlwaysAllow:
        async def evaluate(self, request: PermissionRequest) -> Allow:
            return Allow()

    gate = _AlwaysAllow()
    runtime = build_tool_runtime(gate=gate)
    assert runtime.gate is gate


@pytest.mark.asyncio
async def test_runtime_dispatch_runs_a_registered_tool_end_to_end() -> None:
    runtime = build_tool_runtime(
        tools=[_StubTool("code.search")], permission_mode=PermissionMode.AUTO
    )
    result = await runtime.dispatcher.dispatch(
        ToolRequest(name="code.search", arguments={}, call_id="c1")
    )
    assert result.output == "ok"


def test_container_exposes_a_tool_runtime() -> None:
    from turkish_code.kompozisyon import build_container
    from turkish_code.yapilandirma.yukleyici import load_settings

    settings = load_settings(environ={})
    container = build_container(settings)
    assert isinstance(container.tool_runtime, ToolRuntime)
    assert len(container.tool_runtime.registry) == 0
