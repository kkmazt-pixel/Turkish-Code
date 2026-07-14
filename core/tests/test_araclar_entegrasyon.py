"""End-to-end integration tests for the tool runtime (doc 20).

Exercises the whole stack — registry → permission → dispatcher → streaming —
through :func:`build_tool_runtime`, plus the edge cases the per-module unit tests
don't cover (concurrency/isolation, streaming×timeout, no-op cancellation).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from turkish_code.araclar.akis import CollectingProgressSink
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.hata import (
    TOOL_CANCELLED_CODE,
    TOOL_DENIED_CODE,
    TOOL_FAILED_CODE,
    TOOL_TIMEOUT_CODE,
    invalid_tool_args,
)
from turkish_code.araclar.izin import Grant, PermissionMode
from turkish_code.araclar.kompozisyon import ToolRuntime, build_tool_runtime
from turkish_code.araclar.modeller import (
    Capability,
    SideEffect,
    ToolMetadata,
    ToolProgress,
    ToolRequest,
    ToolResult,
)
from turkish_code.hata import AppError, ErrorKind

_Body = Callable[[ToolRequest, ToolContext], Awaitable[ToolResult]]


class _Tool:
    def __init__(self, metadata: ToolMetadata, body: _Body) -> None:
        self._metadata = metadata
        self._body = body

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return await self._body(request, context)


def _meta(
    name: str,
    *,
    capability: Capability | None = None,
    side_effect: SideEffect = SideEffect.READ,
    timeout_ms: int = 1000,
) -> ToolMetadata:
    return ToolMetadata(
        name=name,
        summary=f"{name} aracı",
        capability=capability,
        side_effect=side_effect,
        brokered=capability is not None,
        reversible=side_effect is SideEffect.MUTATE,
        idempotent=True,
        timeout_ms=timeout_ms,
    )


async def _ok(req: ToolRequest, ctx: ToolContext) -> ToolResult:
    return ToolResult(call_id=req.call_id, output="ok")


def _req(name: str, call_id: str = "c1") -> ToolRequest:
    return ToolRequest(name=name, arguments={}, call_id=call_id)


# --- Permission × dispatch integration ---------------------------------------


@pytest.mark.parametrize("mode", list(PermissionMode))
@pytest.mark.asyncio
async def test_local_tool_runs_in_every_mode(mode: PermissionMode) -> None:
    runtime = build_tool_runtime(
        tools=[_Tool(_meta("memory.get"), _ok)], permission_mode=mode
    )
    result = await runtime.dispatcher.dispatch(_req("memory.get"))
    assert result.output == "ok"


@pytest.mark.asyncio
async def test_brokered_mutation_denied_in_plan_mode() -> None:
    ran = False

    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        nonlocal ran
        ran = True
        return ToolResult(call_id=req.call_id, output=None)

    runtime = build_tool_runtime(
        tools=[
            _Tool(
                _meta(
                    "fs.write",
                    capability=Capability.FS_WRITE,
                    side_effect=SideEffect.MUTATE,
                ),
                body,
            )
        ],
        permission_mode=PermissionMode.PLAN,
    )
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.dispatch(_req("fs.write"))
    assert exc_info.value.code == TOOL_DENIED_CODE
    assert ran is False


@pytest.mark.asyncio
async def test_brokered_mutation_allowed_by_injected_grant() -> None:
    runtime = build_tool_runtime(
        tools=[
            _Tool(
                _meta(
                    "fs.write",
                    capability=Capability.FS_WRITE,
                    side_effect=SideEffect.MUTATE,
                ),
                _ok,
            )
        ],
        permission_mode=PermissionMode.ASK,
        grants=frozenset({Grant(Capability.FS_WRITE)}),
    )
    result = await runtime.dispatcher.dispatch(_req("fs.write"))
    assert result.output == "ok"


@pytest.mark.asyncio
async def test_egress_denied_in_auto_but_allowed_with_grant() -> None:
    tool = _Tool(
        _meta(
            "net.fetch", capability=Capability.NET_EGRESS, side_effect=SideEffect.EGRESS
        ),
        _ok,
    )
    denied = build_tool_runtime(tools=[tool], permission_mode=PermissionMode.AUTO)
    with pytest.raises(AppError) as exc_info:
        await denied.dispatcher.dispatch(_req("net.fetch"))
    assert exc_info.value.kind is ErrorKind.PERMISSION

    allowed = build_tool_runtime(
        tools=[tool],
        permission_mode=PermissionMode.AUTO,
        grants=frozenset({Grant(Capability.NET_EGRESS)}),
    )
    assert (await allowed.dispatcher.dispatch(_req("net.fetch"))).output == "ok"


# --- Concurrency & cancellation isolation ------------------------------------


@pytest.mark.asyncio
async def test_concurrent_calls_are_isolated_under_cancellation() -> None:
    slow_started = asyncio.Event()

    async def slow(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        slow_started.set()
        await asyncio.sleep(10)
        return ToolResult(call_id=req.call_id, output="slow")

    runtime = build_tool_runtime(
        tools=[
            _Tool(_meta("slow", timeout_ms=60_000), slow),
            _Tool(_meta("fast"), _ok),
        ],
        permission_mode=PermissionMode.AUTO,
    )
    slow_task = asyncio.ensure_future(
        runtime.dispatcher.dispatch(_req("slow", call_id="s1"))
    )
    await slow_started.wait()
    fast_result = await runtime.dispatcher.dispatch(_req("fast", call_id="f1"))
    assert fast_result.output == "ok"  # unaffected by the in-flight slow call

    runtime.dispatcher.cancel("s1")  # cancel only the slow call
    with pytest.raises(AppError) as exc_info:
        await slow_task
    assert exc_info.value.code == TOOL_CANCELLED_CODE


@pytest.mark.asyncio
async def test_cancel_unknown_call_id_is_noop() -> None:
    runtime = build_tool_runtime(
        tools=[_Tool(_meta("t"), _ok)], permission_mode=PermissionMode.AUTO
    )
    runtime.dispatcher.cancel("never-registered")  # must not raise
    assert (await runtime.dispatcher.dispatch(_req("t"))).output == "ok"


@pytest.mark.asyncio
async def test_cancel_after_completion_is_noop() -> None:
    runtime = build_tool_runtime(
        tools=[_Tool(_meta("t"), _ok)], permission_mode=PermissionMode.AUTO
    )
    await runtime.dispatcher.dispatch(_req("t", call_id="done"))
    runtime.dispatcher.cancel("done")  # finished + untracked → no-op, no raise


@pytest.mark.asyncio
async def test_same_call_id_can_be_redispatched_sequentially() -> None:
    runtime = build_tool_runtime(
        tools=[_Tool(_meta("t"), _ok)], permission_mode=PermissionMode.AUTO
    )
    first = await runtime.dispatcher.dispatch(_req("t", call_id="x"))
    second = await runtime.dispatcher.dispatch(_req("t", call_id="x"))
    assert first.output == "ok" and second.output == "ok"


# --- Streaming × timeout/cancel/denied ---------------------------------------


@pytest.mark.asyncio
async def test_timeout_during_streaming_keeps_partial_progress() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        await ctx.emit("step-1")
        await asyncio.sleep(10)  # exceeds the 20ms deadline
        await ctx.emit("step-2")
        return ToolResult(call_id=req.call_id, output=None)

    runtime = build_tool_runtime(
        tools=[_Tool(_meta("t", timeout_ms=20), body)],
        permission_mode=PermissionMode.AUTO,
    )
    sink = CollectingProgressSink()
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.dispatch(_req("t"), progress=sink)
    assert exc_info.value.code == TOOL_TIMEOUT_CODE
    assert [e.message for e in sink.events] == ["step-1"]  # step-2 never emitted


@pytest.mark.asyncio
async def test_denied_call_emits_no_progress() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        await ctx.emit("should-not-happen")
        return ToolResult(call_id=req.call_id, output=None)

    runtime = build_tool_runtime(
        tools=[
            _Tool(
                _meta(
                    "fs.write",
                    capability=Capability.FS_WRITE,
                    side_effect=SideEffect.MUTATE,
                ),
                body,
            )
        ],
        permission_mode=PermissionMode.PLAN,
    )
    sink = CollectingProgressSink()
    with pytest.raises(AppError):
        await runtime.dispatcher.dispatch(_req("fs.write"), progress=sink)
    assert sink.events == []  # denied before execution → no progress


@pytest.mark.asyncio
async def test_failing_progress_sink_surfaces_as_tool_failed() -> None:
    class _BoomSink:
        async def emit(self, progress: ToolProgress) -> None:
            raise RuntimeError("sink down")

    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        await ctx.emit("x")
        return ToolResult(call_id=req.call_id, output=None)

    runtime = build_tool_runtime(
        tools=[_Tool(_meta("t"), body)], permission_mode=PermissionMode.AUTO
    )
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.dispatch(_req("t"), progress=_BoomSink())
    assert exc_info.value.code == TOOL_FAILED_CODE


# --- Error propagation & catalog ---------------------------------------------


@pytest.mark.asyncio
async def test_tool_raised_apperror_propagates_unchanged() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        raise invalid_tool_args("t", "missing arg")

    runtime = build_tool_runtime(
        tools=[_Tool(_meta("t"), body)], permission_mode=PermissionMode.AUTO
    )
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.dispatch(_req("t"))
    assert exc_info.value.kind is ErrorKind.VALIDATION  # not remapped to tool.failed


@pytest.mark.asyncio
async def test_runtime_registry_reflects_catalog_and_capabilities() -> None:
    runtime: ToolRuntime = build_tool_runtime(
        tools=[
            _Tool(_meta("memory.get"), _ok),
            _Tool(_meta("fs.read", capability=Capability.FS_READ), _ok),
            _Tool(
                _meta(
                    "fs.write",
                    capability=Capability.FS_WRITE,
                    side_effect=SideEffect.MUTATE,
                ),
                _ok,
            ),
        ]
    )
    assert [m.name for m in runtime.registry.catalog()] == [
        "fs.read",
        "fs.write",
        "memory.get",
    ]
    assert [t.metadata.name for t in runtime.registry.by_capability(None)] == [
        "memory.get"
    ]
    assert [
        t.metadata.name for t in runtime.registry.by_capability(Capability.FS_WRITE)
    ] == ["fs.write"]
