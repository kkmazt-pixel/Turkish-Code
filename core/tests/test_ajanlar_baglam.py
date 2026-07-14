"""Tests for agent contexts — conversation, session, scoped execution (doc 18 §7)."""

from __future__ import annotations

import pytest
from turkish_code.ajanlar.baglam import (
    AGENT_TOOL_OUT_OF_SCOPE_CODE,
    AgentContext,
    ConversationContext,
    ExecutionContext,
    SessionContext,
)
from turkish_code.ajanlar.modeller import ConversationTurn, SessionState, TurnRole
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


# --- conversation context -----------------------------------------------------


def test_conversation_context_history_and_last_user_message() -> None:
    turns = (
        ConversationTurn(role=TurnRole.USER, content="merhaba"),
        ConversationTurn(role=TurnRole.AGENT, content="selam"),
        ConversationTurn(role=TurnRole.USER, content="özellik ekle"),
    )
    ctx = ConversationContext(session_id="s1", turns=turns)
    assert ctx.turn_count == 3
    assert ctx.last_user_message() == "özellik ekle"


def test_conversation_context_empty_has_no_last_user_message() -> None:
    ctx = ConversationContext(session_id=None)
    assert ctx.turn_count == 0
    assert ctx.last_user_message() is None


def test_conversation_turn_rejects_empty_content() -> None:
    with pytest.raises(ValueError, match="content must be non-empty"):
        ConversationTurn(role=TurnRole.USER, content="")


# --- session context ----------------------------------------------------------


def test_session_context_carries_identity_and_state() -> None:
    ctx = SessionContext(
        session_id="s1", agent_id="yonetici", state=SessionState.RUNNING
    )
    assert ctx.session_id == "s1"
    assert ctx.agent_id == "yonetici"
    assert ctx.state is SessionState.RUNNING


# --- execution context (scoped tool access) -----------------------------------


@pytest.mark.asyncio
async def test_execution_context_invokes_granted_tool() -> None:
    execution = ExecutionContext(
        tool_grants=frozenset({"code.search"}), dispatcher=_dispatcher("code.search")
    )
    assert execution.grants_tool("code.search")
    result = await execution.invoke_tool(
        ToolRequest(name="code.search", arguments={}, call_id="c1")
    )
    assert result.output == "code.search-ran"


@pytest.mark.asyncio
async def test_execution_context_refuses_ungranted_tool() -> None:
    ran_registry = _dispatcher("fs.write")
    execution = ExecutionContext(
        tool_grants=frozenset({"code.search"}), dispatcher=ran_registry
    )
    assert not execution.grants_tool("fs.write")
    with pytest.raises(AppError) as exc_info:
        await execution.invoke_tool(
            ToolRequest(name="fs.write", arguments={}, call_id="c1")
        )
    assert exc_info.value.code == AGENT_TOOL_OUT_OF_SCOPE_CODE
    assert exc_info.value.kind is ErrorKind.PERMISSION


@pytest.mark.asyncio
async def test_execution_context_refusal_never_reaches_dispatcher() -> None:
    # The tool exists in the runtime, but the agent lacks the grant → refused
    # before dispatch (least privilege, doc 18 §16), so no run happens.
    execution = ExecutionContext(
        tool_grants=frozenset(), dispatcher=_dispatcher("code.search")
    )
    with pytest.raises(AppError) as exc_info:
        await execution.invoke_tool(
            ToolRequest(name="code.search", arguments={}, call_id="c1")
        )
    assert exc_info.value.code == AGENT_TOOL_OUT_OF_SCOPE_CODE


# --- agent context aggregate --------------------------------------------------


def test_agent_context_aggregates_the_three_views() -> None:
    conversation = ConversationContext(session_id="s1")
    session = SessionContext(session_id="s1", agent_id="a", state=SessionState.RUNNING)
    execution = ExecutionContext(tool_grants=frozenset(), dispatcher=_dispatcher())
    ctx = AgentContext(
        run_id="r1",
        session_id="s1",
        conversation=conversation,
        execution=execution,
        session=session,
    )
    assert ctx.conversation is conversation
    assert ctx.session is session
    assert ctx.execution is execution


def test_agent_context_minimal_still_valid() -> None:
    ctx = AgentContext(run_id="r1")
    assert ctx.conversation is None
    assert ctx.execution is None
    assert ctx.session is None
