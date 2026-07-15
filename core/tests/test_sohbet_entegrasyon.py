"""End-to-end integration tests for the Conversation Runtime (doc 09 §7).

Drives the whole runtime — registry → lifecycle → engine → dispatcher —
through :func:`build_conversation_runtime`: multi-turn history, resume, streaming,
cancellation, timeout, parallel conversations, and history isolation.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from turkish_code.ajanlar.baglam import AgentContext
from turkish_code.ajanlar.dagitici import AGENT_CANCELLED_CODE, AGENT_TIMEOUT_CODE
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
from turkish_code.sohbet.baglam import CollectingEventSink
from turkish_code.sohbet.dagitici import CONVERSATION_NOT_OPEN_CODE
from turkish_code.sohbet.kompozisyon import (
    ConversationRuntime,
    build_conversation_runtime,
)
from turkish_code.sohbet.modeller import ConversationId

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


async def _reply(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
    return AgentResponse(run_id=req.run_id, output="cevap")


def _runtime(*agents: _FnAgent, **builder_kw: object) -> ConversationRuntime:
    tools = ToolDispatcher(
        ToolRegistry(), PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    )
    agent_runtime = build_agent_runtime(tools, agents=list(agents))
    return build_conversation_runtime(agent_runtime, **builder_kw)  # type: ignore[arg-type]


def _cid(value: str) -> ConversationId:
    return ConversationId(value)


# --- multi-turn + history -----------------------------------------------------


@pytest.mark.asyncio
async def test_multi_turn_conversation_accumulates_history() -> None:
    runtime = _runtime(_FnAgent("bot", _reply))
    conversation = runtime.lifecycle.open(_cid("c1"), agent_id="bot")
    for i in range(3):
        await runtime.dispatcher.send(_cid("c1"), f"soru-{i}")
    assert conversation.history.turn_count == 3
    assert [t.user.content for t in conversation.history.turns] == [
        "soru-0",
        "soru-1",
        "soru-2",
    ]


@pytest.mark.asyncio
async def test_agent_receives_growing_history() -> None:
    prompts: list[str] = []

    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        prompts.append(req.message)
        return AgentResponse(run_id=req.run_id, output="ok")

    runtime = _runtime(_FnAgent("bot", body))
    runtime.lifecycle.open(_cid("c1"), agent_id="bot")
    await runtime.dispatcher.send(_cid("c1"), "ilk")
    await runtime.dispatcher.send(_cid("c1"), "ikinci")
    assert prompts[0] == "user: ilk"  # no prior history
    assert "user: ilk" in prompts[1] and prompts[1].endswith("user: ikinci")


# --- resume -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_preserves_history() -> None:
    runtime = _runtime(_FnAgent("bot", _reply))
    conversation = runtime.lifecycle.open(_cid("c1"), agent_id="bot")
    await runtime.dispatcher.send(_cid("c1"), "önce")

    runtime.lifecycle.suspend(_cid("c1"))
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.send(_cid("c1"), "reddedilir")
    assert exc_info.value.code == CONVERSATION_NOT_OPEN_CODE

    runtime.lifecycle.resume(_cid("c1"))
    await runtime.dispatcher.send(_cid("c1"), "sonra")
    assert [t.user.content for t in conversation.history.turns] == ["önce", "sonra"]


# --- streaming ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_via_runtime() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await ctx.emit("mer")
        await ctx.emit("haba")
        return AgentResponse(run_id=req.run_id, output="merhaba")

    runtime = _runtime(_FnAgent("bot", body))
    runtime.lifecycle.open(_cid("c1"), agent_id="bot")
    sink = CollectingEventSink()
    await runtime.dispatcher.send(_cid("c1"), "m", sink=sink)
    assert [c.delta for c in sink.chunks] == ["mer", "haba"]
    assert all(c.conversation_id == "c1" for c in sink.chunks)


# --- cancel + timeout ---------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_via_runtime() -> None:
    started = asyncio.Event()

    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        started.set()
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="late")

    runtime = _runtime(_FnAgent("bot", body, timeout_ms=60_000))
    conversation = runtime.lifecycle.open(_cid("c1"), agent_id="bot")
    task = asyncio.ensure_future(runtime.dispatcher.send(_cid("c1"), "m"))
    await started.wait()
    runtime.dispatcher.cancel(_cid("c1"))
    with pytest.raises(AppError) as exc_info:
        await task
    assert exc_info.value.code == AGENT_CANCELLED_CODE
    assert conversation.history.turn_count == 0  # cancelled turn not persisted


@pytest.mark.asyncio
async def test_timeout_via_runtime() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="late")

    runtime = _runtime(_FnAgent("bot", body, timeout_ms=10))
    runtime.lifecycle.open(_cid("c1"), agent_id="bot")
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.send(_cid("c1"), "m")
    assert exc_info.value.code == AGENT_TIMEOUT_CODE
    assert exc_info.value.kind is ErrorKind.TIMEOUT


# --- parallel conversations + isolation ---------------------------------------


@pytest.mark.asyncio
async def test_parallel_conversations_run_independently() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await asyncio.sleep(0)  # yield to interleave
        return AgentResponse(run_id=req.run_id, output=req.message)

    runtime = _runtime(_FnAgent("bot", body))
    for n in range(4):
        runtime.lifecycle.open(_cid(f"c{n}"), agent_id="bot")
    turns = await asyncio.gather(
        *(runtime.dispatcher.send(_cid(f"c{n}"), f"msg-{n}") for n in range(4))
    )
    assert all(turn.agent.content.endswith(f"msg-{n}") for n, turn in enumerate(turns))
    for n in range(4):
        conversation = runtime.registry.resolve(_cid(f"c{n}"))
        assert conversation.history.turn_count == 1


@pytest.mark.asyncio
async def test_history_isolation_between_conversations() -> None:
    runtime = _runtime(_FnAgent("bot", _reply))
    runtime.lifecycle.open(_cid("a"), agent_id="bot")
    runtime.lifecycle.open(_cid("b"), agent_id="bot")
    await runtime.dispatcher.send(_cid("a"), "a-mesaj")
    await runtime.dispatcher.send(_cid("b"), "b-mesaj")
    await runtime.dispatcher.send(_cid("a"), "a-yine")

    hist_a = runtime.registry.resolve(_cid("a")).history
    hist_b = runtime.registry.resolve(_cid("b")).history
    assert [t.user.content for t in hist_a.turns] == ["a-mesaj", "a-yine"]
    assert [t.user.content for t in hist_b.turns] == ["b-mesaj"]


@pytest.mark.asyncio
async def test_parallel_cancellation_is_isolated() -> None:
    started: dict[str, asyncio.Event] = {n: asyncio.Event() for n in ("a", "b")}

    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        started[req.session_id or ""].set()
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="late")

    runtime = _runtime(_FnAgent("bot", body, timeout_ms=60_000))
    for name in ("a", "b"):
        runtime.lifecycle.open(_cid(name), agent_id="bot")
    tasks = {
        name: asyncio.ensure_future(runtime.dispatcher.send(_cid(name), "m"))
        for name in ("a", "b")
    }
    for event in started.values():
        await event.wait()

    runtime.dispatcher.cancel(_cid("a"))  # cancel only "a"
    with pytest.raises(AppError) as exc_info:
        await tasks["a"]
    assert exc_info.value.code == AGENT_CANCELLED_CODE

    runtime.dispatcher.cancel(_cid("b"))  # clean up "b"
    with pytest.raises(AppError):
        await tasks["b"]


# --- lifecycle edges ----------------------------------------------------------


@pytest.mark.asyncio
async def test_archived_conversation_rejects_send_but_keeps_history() -> None:
    runtime = _runtime(_FnAgent("bot", _reply))
    conversation = runtime.lifecycle.open(_cid("c1"), agent_id="bot")
    await runtime.dispatcher.send(_cid("c1"), "kalıcı")
    runtime.lifecycle.archive(_cid("c1"))
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.send(_cid("c1"), "reddedilir")
    assert exc_info.value.code == CONVERSATION_NOT_OPEN_CODE
    assert conversation.history.turn_count == 1  # history retained


@pytest.mark.asyncio
async def test_unknown_conversation_send_is_reported() -> None:
    runtime = _runtime(_FnAgent("bot", _reply))
    with pytest.raises(AppError):
        await runtime.dispatcher.send(_cid("absent"), "m")
