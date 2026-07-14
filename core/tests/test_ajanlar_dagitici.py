"""Tests for the agent dispatcher — routing, streaming, cancel, timeout (doc 18 §5)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from turkish_code.ajanlar.baglam import AgentContext, CollectingEventSink
from turkish_code.ajanlar.dagitici import (
    AGENT_CANCELLED_CODE,
    AGENT_FAILED_CODE,
    AGENT_TIMEOUT_CODE,
    AgentDispatcher,
)
from turkish_code.ajanlar.kayit import AGENT_NOT_FOUND_CODE, AgentRegistry
from turkish_code.ajanlar.modeller import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
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


def _meta(agent_id: str = "yonetici", *, timeout_ms: int = 1000) -> AgentMetadata:
    return AgentMetadata(
        id=agent_id, name=agent_id, role="worker", summary="s", timeout_ms=timeout_ms
    )


async def _echo(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
    return AgentResponse(run_id=req.run_id, output=f"echo:{req.message}")


def _dispatcher(*agents: _FnAgent, default: str | None = None) -> AgentDispatcher:
    registry = AgentRegistry()
    for agent in agents:
        registry.register(agent, default=agent.metadata.id == default)
    return AgentDispatcher(registry)


def _req(
    agent_id: str = "yonetici", run_id: str = "r1", message: str = "m"
) -> AgentRequest:
    return AgentRequest(agent_id=agent_id, message=message, run_id=run_id)


# --- routing ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_routes_to_named_agent() -> None:
    dispatcher = _dispatcher(_FnAgent(_meta("yonetici"), _echo))
    result = await dispatcher.dispatch(_req("yonetici", message="hi"))
    assert result.output == "echo:hi"


@pytest.mark.asyncio
async def test_empty_agent_id_routes_to_default() -> None:
    dispatcher = _dispatcher(
        _FnAgent(_meta("a"), _echo),
        _FnAgent(_meta("def"), _echo),
        default="def",
    )
    result = await dispatcher.dispatch(_req(agent_id="", message="x"))
    assert result.output == "echo:x"


@pytest.mark.asyncio
async def test_unknown_agent_raises_not_found() -> None:
    dispatcher = _dispatcher(_FnAgent(_meta("a"), _echo))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_req("absent"))
    assert exc_info.value.code == AGENT_NOT_FOUND_CODE


# --- streaming ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_streams_chunks_then_returns_result() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await ctx.emit("düşün")
        await ctx.emit("üyor")
        return AgentResponse(run_id=req.run_id, output="düşünüyor")

    dispatcher = _dispatcher(_FnAgent(_meta("a"), body))
    sink = CollectingEventSink()
    result = await dispatcher.dispatch(_req("a"), sink=sink)
    assert result.output == "düşünüyor"
    assert [c.delta for c in sink.chunks] == ["düşün", "üyor"]
    assert all(c.run_id == "r1" for c in sink.chunks)


@pytest.mark.asyncio
async def test_emit_without_sink_is_noop() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await ctx.emit("noop")
        return AgentResponse(run_id=req.run_id, output="ok")

    dispatcher = _dispatcher(_FnAgent(_meta("a"), body))
    assert (await dispatcher.dispatch(_req("a"))).output == "ok"


# --- timeout ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_is_enforced() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="late")

    dispatcher = _dispatcher(_FnAgent(_meta("a", timeout_ms=10), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_req("a"))
    assert exc_info.value.code == AGENT_TIMEOUT_CODE
    assert exc_info.value.kind is ErrorKind.TIMEOUT


@pytest.mark.asyncio
async def test_dispatch_timeout_override() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="late")

    dispatcher = _dispatcher(_FnAgent(_meta("a", timeout_ms=60_000), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_req("a"), timeout_ms=10)  # override the deadline
    assert exc_info.value.code == AGENT_TIMEOUT_CODE


# --- cancellation -------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_stops_run() -> None:
    started = asyncio.Event()

    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        started.set()
        await asyncio.sleep(10)
        return AgentResponse(run_id=req.run_id, output="done")

    dispatcher = _dispatcher(_FnAgent(_meta("a", timeout_ms=60_000), body))
    task = asyncio.ensure_future(dispatcher.dispatch(_req("a", run_id="rx")))
    await started.wait()
    dispatcher.cancel("rx")
    with pytest.raises(AppError) as exc_info:
        await task
    assert exc_info.value.code == AGENT_CANCELLED_CODE
    assert exc_info.value.kind is ErrorKind.CANCELLED


@pytest.mark.asyncio
async def test_context_carries_cancellation_token() -> None:
    seen: dict[str, object] = {}

    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        seen["has_token"] = ctx.cancellation is not None
        seen["run_id"] = ctx.run_id
        return AgentResponse(run_id=req.run_id, output="ok")

    dispatcher = _dispatcher(_FnAgent(_meta("a"), body))
    await dispatcher.dispatch(_req("a", run_id="rz"))
    assert seen == {"has_token": True, "run_id": "rz"}


# --- failure ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_apperror_propagates_unchanged() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        raise AppError(
            kind=ErrorKind.VALIDATION,
            code="x.bad",
            message_key="hata.x.bad",
            retryable=False,
        )

    dispatcher = _dispatcher(_FnAgent(_meta("a"), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_req("a"))
    assert exc_info.value.kind is ErrorKind.VALIDATION  # not wrapped


@pytest.mark.asyncio
async def test_unexpected_exception_is_wrapped_as_failed() -> None:
    async def body(req: AgentRequest, ctx: AgentContext) -> AgentResponse:
        raise RuntimeError("boom")

    dispatcher = _dispatcher(_FnAgent(_meta("a"), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_req("a"))
    assert exc_info.value.code == AGENT_FAILED_CODE
    assert exc_info.value.kind is ErrorKind.INTERNAL


@pytest.mark.asyncio
async def test_run_untracked_after_completion() -> None:
    dispatcher = _dispatcher(_FnAgent(_meta("a"), _echo))
    await dispatcher.dispatch(_req("a", run_id="done"))
    assert dispatcher._cancels.token_for("done") is None
