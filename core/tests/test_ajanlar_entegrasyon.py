"""End-to-end integration tests for the Agent Runtime (doc 18).

Drives the whole runtime — registry → lifecycle → session → dispatcher →
streaming/cancellation — through :func:`build_agent_runtime`, exercising how the
pieces compose (a session recording dispatched runs, lifecycle cancelling them)
plus the edge cases the per-module unit tests don't.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from turkish_code.ajanlar.baglam import AgentContext, CollectingEventSink
from turkish_code.ajanlar.dagitici import (
    AGENT_CANCELLED_CODE,
    AGENT_TIMEOUT_CODE,
)
from turkish_code.ajanlar.durum import RunState
from turkish_code.ajanlar.kayit import AGENT_DUPLICATE_CODE, AGENT_NOT_FOUND_CODE
from turkish_code.ajanlar.kompozisyon import AgentRuntime, build_agent_runtime
from turkish_code.ajanlar.modeller import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    SessionState,
)
from turkish_code.ajanlar.oturum import AgentSession
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

_Body = Callable[[AgentRequest, AgentContext], Awaitable[AgentResponse]]


class _FnAgent:
    def __init__(self, metadata: AgentMetadata, body: _Body) -> None:
        self._metadata = metadata
        self._body = body

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        return await self._body(request, context)


def _agent(
    agent_id: str,
    body: _Body,
    *,
    timeout_ms: int = 1000,
    grants: frozenset[str] = frozenset(),
) -> _FnAgent:
    return _FnAgent(
        AgentMetadata(
            id=agent_id,
            name=agent_id,
            role="worker",
            summary="s",
            tool_grants=grants,
            timeout_ms=timeout_ms,
        ),
        body,
    )


async def _echo(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
    return AgentResponse(run_id=req.run_id, output=f"cevap:{req.message}")


def _empty_tools() -> ToolDispatcher:
    gate = PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    return ToolDispatcher(ToolRegistry(), gate)


def _runtime(*agents: _FnAgent, default: str | None = None) -> AgentRuntime:
    return build_agent_runtime(
        _empty_tools(), agents=list(agents), default_agent_id=default
    )


async def _run_turn(
    runtime: AgentRuntime,
    session: AgentSession,
    request: AgentRequest,
    *,
    sink: CollectingEventSink | None = None,
) -> AgentResponse:
    """Compose session bookkeeping with a dispatch — one conversational turn."""
    session.open_run(request.run_id, request.message)
    session.start_run(request.run_id)
    try:
        response = await runtime.dispatcher.dispatch(request, sink=sink)
    except AppError as exc:
        if exc.kind is ErrorKind.CANCELLED:
            session.cancel_run(request.run_id)
        else:
            session.fail_run(request.run_id, exc.code)
        raise
    session.complete_run(request.run_id, response.output)
    return response


# --- multi-turn conversation --------------------------------------------------


@pytest.mark.asyncio
async def test_multi_turn_conversation_builds_history() -> None:
    runtime = _runtime(_agent("a", _echo))
    session = AgentSession(session_id="s1", agent_id="a")
    await _run_turn(runtime, session, AgentRequest("a", "merhaba", "r1", "s1"))
    await _run_turn(runtime, session, AgentRequest("a", "nasılsın", "r2", "s1"))

    assert [t.content for t in session.turns()] == [
        "merhaba",
        "cevap:merhaba",
        "nasılsın",
        "cevap:nasılsın",
    ]
    assert session.conversation_context().last_user_message() == "nasılsın"
    assert all(r.state is RunState.COMPLETED for r in session.runs())


# --- lifecycle + session + dispatch ------------------------------------------


@pytest.mark.asyncio
async def test_lifecycle_with_a_completed_run() -> None:
    from turkish_code.ajanlar.yasam import SessionLifecycle

    lifecycle = SessionLifecycle()
    session = lifecycle.create("s1", "a")
    lifecycle.start("s1")
    runtime = _runtime(_agent("a", _echo))
    await _run_turn(runtime, session, AgentRequest("a", "hi", "r1", "s1"))
    lifecycle.stop("s1")
    assert session.state is SessionState.STOPPED
    assert session.run("r1").state is RunState.COMPLETED  # completed run preserved


def test_stop_session_cancels_in_flight_run() -> None:
    from turkish_code.ajanlar.yasam import SessionLifecycle

    lifecycle = SessionLifecycle()
    session = lifecycle.create("s1", "a")
    lifecycle.start("s1")
    session.open_run("r1", "m")  # opened, never completed → active
    session.start_run("r1")
    lifecycle.stop("s1")
    assert session.run("r1").state is RunState.CANCELLED


# --- streaming ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_turn_records_final_output() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await ctx.emit("par")
        await ctx.emit("ça")
        return AgentResponse(run_id=req.run_id, output="parça")

    runtime = _runtime(_agent("a", body))
    session = AgentSession(session_id="s1", agent_id="a")
    sink = CollectingEventSink()
    await _run_turn(runtime, session, AgentRequest("a", "m", "r1", "s1"), sink=sink)
    assert [c.delta for c in sink.chunks] == ["par", "ça"]
    assert session.run("r1").output == "parça"


# --- cancellation -------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancelled_dispatch_marks_session_run_cancelled() -> None:
    started = asyncio.Event()

    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        started.set()
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="late")

    runtime = _runtime(_agent("a", body, timeout_ms=60_000))
    session = AgentSession(session_id="s1", agent_id="a")
    turn = asyncio.ensure_future(
        _run_turn(runtime, session, AgentRequest("a", "m", "rx", "s1"))
    )
    await started.wait()
    runtime.dispatcher.cancel("rx")
    with pytest.raises(AppError) as exc_info:
        await turn
    assert exc_info.value.code == AGENT_CANCELLED_CODE
    assert session.run("rx").state is RunState.CANCELLED


@pytest.mark.asyncio
async def test_concurrent_runs_isolated_under_cancellation() -> None:
    started = asyncio.Event()

    async def slow(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        started.set()
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="slow")

    runtime = _runtime(_agent("slow", slow, timeout_ms=60_000), _agent("fast", _echo))
    slow_task = asyncio.ensure_future(
        runtime.dispatcher.dispatch(AgentRequest("slow", "m", "s1"))
    )
    await started.wait()
    fast = await runtime.dispatcher.dispatch(AgentRequest("fast", "hi", "f1"))
    assert fast.output == "cevap:hi"  # unaffected by the in-flight slow run

    runtime.dispatcher.cancel("s1")
    with pytest.raises(AppError) as exc_info:
        await slow_task
    assert exc_info.value.code == AGENT_CANCELLED_CODE


# --- timeout ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_marks_session_run_failed() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="late")

    runtime = _runtime(_agent("a", body, timeout_ms=10))
    session = AgentSession(session_id="s1", agent_id="a")
    with pytest.raises(AppError) as exc_info:
        await _run_turn(runtime, session, AgentRequest("a", "m", "r1", "s1"))
    assert exc_info.value.code == AGENT_TIMEOUT_CODE
    record = session.run("r1")
    assert record.state is RunState.FAILED and record.error_code == AGENT_TIMEOUT_CODE


# --- routing edges ------------------------------------------------------------


@pytest.mark.asyncio
async def test_default_agent_routing_end_to_end() -> None:
    runtime = _runtime(_agent("a", _echo), _agent("def", _echo), default="def")
    result = await runtime.dispatcher.dispatch(AgentRequest("", "x", "r1"))
    assert result.output == "cevap:x"


@pytest.mark.asyncio
async def test_unknown_agent_is_reported() -> None:
    runtime = _runtime(_agent("a", _echo))
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.dispatch(AgentRequest("absent", "x", "r1"))
    assert exc_info.value.code == AGENT_NOT_FOUND_CODE


def test_duplicate_agent_registration_is_rejected() -> None:
    with pytest.raises(AppError) as exc_info:
        build_agent_runtime(
            _empty_tools(), agents=[_agent("a", _echo), _agent("a", _echo)]
        )
    assert exc_info.value.code == AGENT_DUPLICATE_CODE


# --- resume -------------------------------------------------------------------


def test_incomplete_run_is_resumable() -> None:
    session = AgentSession(session_id="s1", agent_id="a")
    session.open_run("done", "a")
    session.complete_run("done", "x")
    session.open_run("interrupted", "b")  # e.g. crashed before completing
    session.start_run("interrupted")
    assert [r.run_id for r in session.active_runs()] == ["interrupted"]


# --- tool scope end to end ----------------------------------------------------


class _ToolAgent:
    def __init__(self, agent_id: str, grants: frozenset[str], tool: str) -> None:
        self._id = agent_id
        self._grants = grants
        self._tool = tool

    @property
    def metadata(self) -> AgentMetadata:
        return AgentMetadata(
            id=self._id, name=self._id, role="w", summary="s", tool_grants=self._grants
        )

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        assert context.execution is not None
        result = await context.execution.invoke_tool(
            ToolRequest(name=self._tool, arguments={}, call_id=request.run_id)
        )
        return AgentResponse(run_id=request.run_id, output=str(result.output))


class _EchoTool:
    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="code.search",
            summary="s",
            capability=None,
            side_effect=SideEffect.READ,
            brokered=False,
            reversible=False,
            idempotent=True,
            timeout_ms=1000,
        )

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output="tool-ran")


@pytest.mark.asyncio
async def test_agent_tool_grant_enforced_end_to_end() -> None:
    registry = ToolRegistry()
    registry.register(_EchoTool())
    dispatcher = ToolDispatcher(
        registry, PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    )
    granted = _ToolAgent("g", frozenset({"code.search"}), "code.search")
    denied = _ToolAgent("d", frozenset(), "code.search")
    runtime = build_agent_runtime(dispatcher, agents=[granted, denied])

    ok = await runtime.dispatcher.dispatch(
        AgentRequest("g", "m", "r1"), execution=runtime.execution_for(granted)
    )
    assert ok.output == "tool-ran"

    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.dispatch(
            AgentRequest("d", "m", "r2"), execution=runtime.execution_for(denied)
        )
    assert exc_info.value.kind is ErrorKind.PERMISSION  # out-of-scope tool refused
