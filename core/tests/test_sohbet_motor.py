"""Tests for the conversation engine + dispatcher — real Agent Runtime (doc 09 §7)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from turkish_code.ajanlar.baglam import AgentContext
from turkish_code.ajanlar.dagitici import AGENT_CANCELLED_CODE, AGENT_TIMEOUT_CODE
from turkish_code.ajanlar.kompozisyon import build_agent_runtime
from turkish_code.ajanlar.modeller import AgentMetadata, AgentRequest, AgentResponse
from turkish_code.araclar.izin import (
    PermissionMode,
    PermissionPolicy,
    PolicyPermissionGate,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.hata import AppError, ErrorKind
from turkish_code.sohbet.baglam import CollectingEventSink
from turkish_code.sohbet.dagitici import ConversationDispatcher
from turkish_code.sohbet.modeller import ConversationId
from turkish_code.sohbet.motor import ConversationEngine
from turkish_code.sohbet.oturum import ConversationRegistry

_Body = Callable[[AgentRequest, AgentContext], Awaitable[AgentResponse]]


class _FnAgent:
    def __init__(self, agent_id: str, body: _Body, *, timeout_ms: int = 1000) -> None:
        self._id = agent_id
        self._body = body
        self._timeout = timeout_ms

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            id=self._id,
            name=self._id,
            role="chat",
            summary="s",
            timeout_ms=self._timeout,
        )

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        return await self._body(request, context)


def _tools() -> object:
    from turkish_code.araclar.dagitici import ToolDispatcher

    return ToolDispatcher(
        ToolRegistry(), PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    )


def _engine(*agents: _FnAgent) -> ConversationEngine:
    runtime = build_agent_runtime(_tools(), agents=list(agents))  # type: ignore[arg-type]
    return ConversationEngine(runtime)


def _dispatcher(
    engine: ConversationEngine,
) -> tuple[ConversationRegistry, ConversationDispatcher]:
    registry = ConversationRegistry()
    return registry, ConversationDispatcher(registry, engine)


async def _reply(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
    return AgentResponse(run_id=req.run_id, output="cevap")


# --- engine chain -------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_dispatches_agent_and_persists_turn() -> None:
    engine = _engine(_FnAgent("bot", _reply))
    registry = ConversationRegistry()
    conversation = registry.create(ConversationId("c1"), agent_id="bot")
    turn = await engine.send(conversation, "merhaba", turn_id="t1")
    assert turn.user.content == "merhaba"
    assert turn.agent.content == "cevap"
    assert conversation.history.turn_count == 1  # persisted


@pytest.mark.asyncio
async def test_agent_sees_rendered_history_context() -> None:
    seen: dict[str, str] = {}

    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        seen["message"] = req.message
        return AgentResponse(run_id=req.run_id, output="ok")

    engine = _engine(_FnAgent("bot", body))
    registry = ConversationRegistry()
    conversation = registry.create(ConversationId("c1"), agent_id="bot")
    await engine.send(conversation, "ilk", turn_id="t1")
    await engine.send(conversation, "ikinci", turn_id="t2")
    # the second turn's rendered prompt includes the prior turn + new message
    assert "user: ilk" in seen["message"]
    assert "agent: ok" in seen["message"]
    assert seen["message"].endswith("user: ikinci")


# --- streaming ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_bridges_agent_stream_to_conversation_sink() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await ctx.emit("dü")
        await ctx.emit("şün")
        return AgentResponse(run_id=req.run_id, output="düşün")

    engine = _engine(_FnAgent("bot", body))
    registry = ConversationRegistry()
    conversation = registry.create(ConversationId("c1"), agent_id="bot")
    sink = CollectingEventSink()
    await engine.send(conversation, "m", turn_id="t1", sink=sink)
    assert [c.delta for c in sink.chunks] == ["dü", "şün"]
    assert all(c.conversation_id == "c1" for c in sink.chunks)


# --- dispatcher: send / cancel / timeout --------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_send_runs_a_turn() -> None:
    engine = _engine(_FnAgent("bot", _reply))
    registry, dispatcher = _dispatcher(engine)
    registry.create(ConversationId("c1"), agent_id="bot")
    turn = await dispatcher.send(ConversationId("c1"), "selam")
    assert turn.agent.content == "cevap"


@pytest.mark.asyncio
async def test_dispatcher_send_unknown_conversation_raises() -> None:
    engine = _engine(_FnAgent("bot", _reply))
    _, dispatcher = _dispatcher(engine)
    with pytest.raises(AppError):
        await dispatcher.send(ConversationId("absent"), "m")


@pytest.mark.asyncio
async def test_dispatcher_cancel_stops_turn() -> None:
    started = asyncio.Event()

    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        started.set()
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="late")

    engine = _engine(_FnAgent("bot", body, timeout_ms=60_000))
    registry, dispatcher = _dispatcher(engine)
    conversation = registry.create(ConversationId("c1"), agent_id="bot")
    task = asyncio.ensure_future(dispatcher.send(ConversationId("c1"), "m"))
    await started.wait()
    dispatcher.cancel(ConversationId("c1"))
    with pytest.raises(AppError) as exc_info:
        await task
    assert exc_info.value.code == AGENT_CANCELLED_CODE
    assert conversation.history.turn_count == 0  # cancelled turn not persisted


@pytest.mark.asyncio
async def test_dispatcher_timeout_is_enforced() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="late")

    engine = _engine(_FnAgent("bot", body, timeout_ms=60_000))
    registry, dispatcher = _dispatcher(engine)
    registry.create(ConversationId("c1"), agent_id="bot")
    with pytest.raises(AppError) as exc_info:
        await dispatcher.send(ConversationId("c1"), "m", timeout_ms=10)
    assert exc_info.value.code == AGENT_TIMEOUT_CODE
    assert exc_info.value.kind is ErrorKind.TIMEOUT


@pytest.mark.asyncio
async def test_cancel_with_no_active_turn_is_noop() -> None:
    engine = _engine(_FnAgent("bot", _reply))
    registry, dispatcher = _dispatcher(engine)
    registry.create(ConversationId("c1"), agent_id="bot")
    dispatcher.cancel(ConversationId("c1"))  # nothing in flight → no raise
    turn = await dispatcher.send(ConversationId("c1"), "m")
    assert turn.agent.content == "cevap"
