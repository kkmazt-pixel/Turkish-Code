"""Tests for streaming progress + final result (doc 20 §7/§17, doc 10 §11)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from turkish_code.araclar.akis import (
    CollectingProgressSink,
    NullProgressSink,
    ProgressSink,
)
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.hata import TOOL_CANCELLED_CODE
from turkish_code.araclar.izin import (
    PermissionMode,
    PermissionPolicy,
    PolicyPermissionGate,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.modeller import (
    SideEffect,
    ToolMetadata,
    ToolProgress,
    ToolRequest,
    ToolResult,
)
from turkish_code.hata import AppError

_Body = Callable[[ToolRequest, ToolContext], Awaitable[ToolResult]]


class _FnTool:
    def __init__(self, metadata: ToolMetadata, body: _Body) -> None:
        self._metadata = metadata
        self._body = body

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return await self._body(request, context)


def _meta(name: str = "code.search", timeout_ms: int = 1000) -> ToolMetadata:
    return ToolMetadata(
        name=name,
        summary=f"{name} aracı",
        capability=None,
        side_effect=SideEffect.READ,
        brokered=False,
        reversible=False,
        idempotent=True,
        timeout_ms=timeout_ms,
    )


def _dispatcher(tool: _FnTool) -> ToolDispatcher:
    registry = ToolRegistry()
    registry.register(tool)
    gate = PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    return ToolDispatcher(registry, gate)


def _request(call_id: str = "c1") -> ToolRequest:
    return ToolRequest(name="code.search", arguments={}, call_id=call_id)


def test_progress_and_null_sinks_satisfy_protocol() -> None:
    assert isinstance(NullProgressSink(), ProgressSink)
    assert isinstance(CollectingProgressSink(), ProgressSink)


def test_progress_fraction_must_be_in_range() -> None:
    ToolProgress(call_id="c", message="ok", fraction=0.5)  # valid
    with pytest.raises(ValueError, match=r"\[0.0, 1.0\]"):
        ToolProgress(call_id="c", message="bad", fraction=1.5)


@pytest.mark.asyncio
async def test_collecting_sink_records_events_in_order() -> None:
    sink = CollectingProgressSink()
    await sink.emit(ToolProgress(call_id="c", message="a"))
    await sink.emit(ToolProgress(call_id="c", message="b"))
    assert [e.message for e in sink.events] == ["a", "b"]


@pytest.mark.asyncio
async def test_dispatch_forwards_progress_then_returns_final_result() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        await ctx.emit("başladı", fraction=0.0)
        await ctx.emit("yarısı", fraction=0.5)
        await ctx.emit("bitti", fraction=1.0)
        return ToolResult(call_id=req.call_id, output={"hits": 3})

    sink = CollectingProgressSink()
    dispatcher = _dispatcher(_FnTool(_meta(), body))
    result = await dispatcher.dispatch(_request(), progress=sink)

    assert result.output == {"hits": 3}  # final result
    assert [e.message for e in sink.events] == ["başladı", "yarısı", "bitti"]
    assert [e.fraction for e in sink.events] == [0.0, 0.5, 1.0]
    assert all(e.call_id == "c1" for e in sink.events)  # stamped with call id


@pytest.mark.asyncio
async def test_emit_carries_structured_payload() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        await ctx.emit("chunk", payload={"line": 1})
        return ToolResult(call_id=req.call_id, output=None)

    sink = CollectingProgressSink()
    await _dispatcher(_FnTool(_meta(), body)).dispatch(_request(), progress=sink)
    assert sink.events[0].payload == {"line": 1}


@pytest.mark.asyncio
async def test_progress_defaults_to_null_sink_when_omitted() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        # Emitting without a caller sink must be a harmless no-op (doc 20 §5).
        await ctx.emit("noop")
        return ToolResult(call_id=req.call_id, output="done")

    result = await _dispatcher(_FnTool(_meta(), body)).dispatch(_request())
    assert result.output == "done"


@pytest.mark.asyncio
async def test_cancellation_stops_streaming_midway() -> None:
    sink = CollectingProgressSink()
    first = asyncio.Event()

    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        await ctx.emit("one")
        first.set()
        await asyncio.sleep(10)  # cancelled here, before "two"
        await ctx.emit("two")
        return ToolResult(call_id=req.call_id, output=None)

    dispatcher = _dispatcher(_FnTool(_meta(timeout_ms=60_000), body))
    task = asyncio.ensure_future(dispatcher.dispatch(_request("cx"), progress=sink))
    await first.wait()
    dispatcher.cancel("cx")
    with pytest.raises(AppError) as exc_info:
        await task
    assert exc_info.value.code == TOOL_CANCELLED_CODE
    assert [e.message for e in sink.events] == ["one"]  # "two" never emitted
