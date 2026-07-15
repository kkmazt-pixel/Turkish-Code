"""Tests for the conversation lifecycle + the dispatcher's open-state guard."""

from __future__ import annotations

import pytest
from turkish_code.ajanlar.baglam import AgentContext
from turkish_code.ajanlar.kompozisyon import build_agent_runtime
from turkish_code.ajanlar.modeller import AgentMetadata, AgentRequest, AgentResponse
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.izin import (
    PermissionMode,
    PermissionPolicy,
    PolicyPermissionGate,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.hata import AppError, ErrorKind
from turkish_code.sohbet.dagitici import (
    CONVERSATION_NOT_OPEN_CODE,
    ConversationDispatcher,
)
from turkish_code.sohbet.modeller import ConversationId, ConversationState
from turkish_code.sohbet.motor import ConversationEngine
from turkish_code.sohbet.oturum import CONVERSATION_DUPLICATE_CODE, ConversationRegistry
from turkish_code.sohbet.yasam import (
    CONVERSATION_INVALID_TRANSITION_CODE,
    ConversationLifecycle,
)


def _lifecycle() -> tuple[ConversationRegistry, ConversationLifecycle]:
    registry = ConversationRegistry()
    return registry, ConversationLifecycle(registry)


def _cid(value: str = "c1") -> ConversationId:
    return ConversationId(value)


def _state(registry: ConversationRegistry, cid: ConversationId) -> ConversationState:
    return registry.resolve(cid).state


# --- transitions --------------------------------------------------------------


def test_open_creates_open_conversation() -> None:
    registry, lifecycle = _lifecycle()
    conversation = lifecycle.open(_cid(), agent_id="bot")
    assert conversation.state is ConversationState.OPEN


def test_open_duplicate_is_rejected() -> None:
    _, lifecycle = _lifecycle()
    lifecycle.open(_cid(), agent_id="bot")
    with pytest.raises(AppError) as exc_info:
        lifecycle.open(_cid(), agent_id="bot")
    assert exc_info.value.code == CONVERSATION_DUPLICATE_CODE


def test_suspend_and_resume_round_trip() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.open(_cid(), agent_id="bot")
    lifecycle.suspend(_cid())
    assert _state(registry, _cid()) is ConversationState.SUSPENDED
    lifecycle.resume(_cid())
    assert _state(registry, _cid()) is ConversationState.OPEN


def test_close_from_open_and_suspended() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.open(_cid("a"), agent_id="bot")
    lifecycle.close(_cid("a"))
    assert _state(registry, _cid("a")) is ConversationState.CLOSED

    lifecycle.open(_cid("b"), agent_id="bot")
    lifecycle.suspend(_cid("b"))
    lifecycle.close(_cid("b"))
    assert _state(registry, _cid("b")) is ConversationState.CLOSED


def test_archive_from_various_states() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.open(_cid("a"), agent_id="bot")
    lifecycle.close(_cid("a"))
    lifecycle.archive(_cid("a"))
    assert _state(registry, _cid("a")) is ConversationState.ARCHIVED

    lifecycle.open(_cid("b"), agent_id="bot")
    lifecycle.archive(_cid("b"))  # direct from OPEN
    assert _state(registry, _cid("b")) is ConversationState.ARCHIVED


def test_illegal_transitions_are_rejected() -> None:
    _, lifecycle = _lifecycle()
    lifecycle.open(_cid(), agent_id="bot")  # OPEN
    # resume requires SUSPENDED
    with pytest.raises(AppError) as exc_info:
        lifecycle.resume(_cid())
    assert exc_info.value.code == CONVERSATION_INVALID_TRANSITION_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT
    # suspend twice: SUSPENDED cannot suspend again
    lifecycle.suspend(_cid())
    with pytest.raises(AppError):
        lifecycle.suspend(_cid())


def test_archived_is_terminal() -> None:
    _, lifecycle = _lifecycle()
    lifecycle.open(_cid(), agent_id="bot")
    lifecycle.archive(_cid())
    for op in (lifecycle.suspend, lifecycle.resume, lifecycle.close, lifecycle.archive):
        with pytest.raises(AppError) as exc_info:
            op(_cid())
        assert exc_info.value.code == CONVERSATION_INVALID_TRANSITION_CODE


def test_full_lifecycle_flow() -> None:
    registry, lifecycle = _lifecycle()
    lifecycle.open(_cid(), agent_id="bot")
    lifecycle.suspend(_cid())
    lifecycle.resume(_cid())
    lifecycle.close(_cid())
    lifecycle.archive(_cid())
    assert _state(registry, _cid()) is ConversationState.ARCHIVED


# --- dispatcher open-state guard ----------------------------------------------


class _Bot:
    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(id="bot", name="bot", role="chat", summary="s")

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        return AgentResponse(run_id=request.run_id, output="cevap")


def _dispatcher() -> (
    tuple[ConversationRegistry, ConversationLifecycle, ConversationDispatcher]
):
    registry = ConversationRegistry()
    lifecycle = ConversationLifecycle(registry)
    tools = ToolDispatcher(
        ToolRegistry(), PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    )
    agents = build_agent_runtime(tools, agents=[_Bot()])
    dispatcher = ConversationDispatcher(registry, ConversationEngine(agents))
    return registry, lifecycle, dispatcher


@pytest.mark.asyncio
async def test_suspended_conversation_rejects_send_then_resume_allows() -> None:
    _, lifecycle, dispatcher = _dispatcher()
    lifecycle.open(_cid(), agent_id="bot")
    lifecycle.suspend(_cid())
    with pytest.raises(AppError) as exc_info:
        await dispatcher.send(_cid(), "m")
    assert exc_info.value.code == CONVERSATION_NOT_OPEN_CODE

    lifecycle.resume(_cid())
    turn = await dispatcher.send(_cid(), "m")
    assert turn.agent.content == "cevap"


@pytest.mark.asyncio
async def test_archived_conversation_rejects_send() -> None:
    _, lifecycle, dispatcher = _dispatcher()
    lifecycle.open(_cid(), agent_id="bot")
    lifecycle.archive(_cid())
    with pytest.raises(AppError) as exc_info:
        await dispatcher.send(_cid(), "m")
    assert exc_info.value.code == CONVERSATION_NOT_OPEN_CODE
