"""Tests for skill context — cancellation + scoped runtime access (doc 19 §8/§15)."""

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
from turkish_code.hata import AppError, ErrorKind
from turkish_code.yetenekler.baglam import (
    CancellationToken,
    SkillContext,
    SkillExecutionContext,
)
from turkish_code.yetenekler.hata import SKILL_TOOL_OUT_OF_SCOPE_CODE


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


def _dispatcher(*names: str) -> ToolDispatcher:
    registry = ToolRegistry()
    for name in names:
        registry.register(_EchoTool(name))
    gate = PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    return ToolDispatcher(registry, gate)


# --- cancellation token -------------------------------------------------------


def test_cancellation_token_flag() -> None:
    assert CancellationToken().is_cancelled is False  # fresh token
    token = CancellationToken()
    token.cancel()
    assert token.is_cancelled is True
    token.cancel()  # idempotent — still cancelled
    assert token.is_cancelled is True


# --- execution context (scoped tool access) -----------------------------------


@pytest.mark.asyncio
async def test_invokes_allowed_tool() -> None:
    execution = SkillExecutionContext(
        allowed_tools=frozenset({"fs.read"}), tool_dispatcher=_dispatcher("fs.read")
    )
    assert execution.allows_tool("fs.read")
    result = await execution.invoke_tool(
        ToolRequest(name="fs.read", arguments={}, call_id="c1")
    )
    assert result.output == "fs.read-ran"


@pytest.mark.asyncio
async def test_refuses_disallowed_tool_before_dispatch() -> None:
    # Tool exists in the runtime, but it's outside allowed_tools → refused.
    execution = SkillExecutionContext(
        allowed_tools=frozenset({"fs.read"}), tool_dispatcher=_dispatcher("fs.write")
    )
    assert not execution.allows_tool("fs.write")
    with pytest.raises(AppError) as exc_info:
        await execution.invoke_tool(
            ToolRequest(name="fs.write", arguments={}, call_id="c1")
        )
    assert exc_info.value.code == SKILL_TOOL_OUT_OF_SCOPE_CODE
    assert exc_info.value.kind is ErrorKind.PERMISSION


def test_runtime_facades_default_to_none() -> None:
    execution = SkillExecutionContext(
        allowed_tools=frozenset(), tool_dispatcher=_dispatcher()
    )
    assert execution.storage is None
    assert execution.agents is None
    assert execution.provider is None


# --- skill context aggregate --------------------------------------------------


def test_skill_context_holds_ids_and_parts() -> None:
    token = CancellationToken()
    execution = SkillExecutionContext(
        allowed_tools=frozenset(), tool_dispatcher=_dispatcher()
    )
    ctx = SkillContext(
        invocation_id="i1", run_id="r1", cancellation=token, execution=execution
    )
    assert ctx.invocation_id == "i1"
    assert ctx.run_id == "r1"
    assert ctx.cancellation is token
    assert ctx.execution is execution


def test_skill_context_minimal_still_valid() -> None:
    ctx = SkillContext(invocation_id="i1")
    assert ctx.cancellation is None
    assert ctx.execution is None
