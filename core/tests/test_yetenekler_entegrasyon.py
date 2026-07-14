"""End-to-end integration tests for the Skill Runtime (doc 19).

Drives the whole runtime — registry → lifecycle → dispatcher → streaming /
cancellation — through :func:`build_skill_runtime`, including parallel execution
and the edge cases the per-module unit tests don't.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

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
from turkish_code.yetenekler.baglam import CollectingEventSink, SkillContext
from turkish_code.yetenekler.hata import (
    SKILL_CANCELLED_CODE,
    SKILL_DUPLICATE_CODE,
    SKILL_NOT_FOUND_CODE,
    SKILL_TIMEOUT_CODE,
    SKILL_TOOL_OUT_OF_SCOPE_CODE,
)
from turkish_code.yetenekler.kompozisyon import SkillRuntime, build_skill_runtime
from turkish_code.yetenekler.modeller import (
    SkillMetadata,
    SkillRequest,
    SkillResult,
    SkillState,
)

_Body = Callable[[SkillRequest, SkillContext], Awaitable[SkillResult]]


class _FnSkill:
    def __init__(self, metadata: SkillMetadata, body: _Body) -> None:
        self._metadata = metadata
        self._body = body

    @property
    def metadata(self) -> SkillMetadata:
        return self._metadata

    async def run(self, request: SkillRequest, context: SkillContext) -> SkillResult:
        return await self._body(request, context)


def _skill(
    skill_id: str,
    body: _Body,
    *,
    timeout_ms: int = 1000,
    allowed: frozenset[str] = frozenset(),
) -> _FnSkill:
    return _FnSkill(
        SkillMetadata(
            id=skill_id,
            description="ne zaman kullanılır",
            allowed_tools=allowed,
            timeout_ms=timeout_ms,
        ),
        body,
    )


async def _echo(req: SkillRequest, ctx: SkillContext) -> SkillResult:
    return SkillResult(invocation_id=req.invocation_id, output=req.inputs.get("x"))


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


def _empty_tools() -> ToolDispatcher:
    gate = PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    return ToolDispatcher(ToolRegistry(), gate)


def _runtime(*skills: _FnSkill, tools: ToolDispatcher | None = None) -> SkillRuntime:
    return build_skill_runtime(tools or _empty_tools(), skills=list(skills))


def _req(skill_id: str, invocation_id: str, x: object = 1) -> SkillRequest:
    return SkillRequest(skill_id=skill_id, inputs={"x": x}, invocation_id=invocation_id)


# --- lifecycle + dispatch -----------------------------------------------------


@pytest.mark.asyncio
async def test_full_lifecycle_load_enable_invoke_disable() -> None:
    runtime = _runtime()
    runtime.lifecycle.load(_skill("s", _echo))
    runtime.lifecycle.enable("s")
    result = await runtime.dispatcher.invoke(_req("s", "i1", x=42))
    assert result.output == 42

    runtime.lifecycle.disable("s")
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.invoke(_req("s", "i2"))
    assert exc_info.value.code == SKILL_NOT_FOUND_CODE  # withdrawn on disable


def test_duplicate_load_is_rejected() -> None:
    runtime = _runtime(_skill("s", _echo))
    with pytest.raises(AppError) as exc_info:
        runtime.lifecycle.load(_skill("s", _echo))
    assert exc_info.value.code == SKILL_DUPLICATE_CODE


@pytest.mark.asyncio
async def test_unknown_skill_is_reported() -> None:
    runtime = _runtime(_skill("s", _echo))
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.invoke(_req("absent", "i1"))
    assert exc_info.value.code == SKILL_NOT_FOUND_CODE


def test_failed_recover_reenable() -> None:
    runtime = _runtime()
    runtime.lifecycle.load(_skill("s", _echo))
    runtime.lifecycle.enable("s")
    runtime.lifecycle.mark_failed("s")
    assert runtime.lifecycle.state_of("s") is SkillState.FAILED
    assert "s" not in runtime.registry
    runtime.lifecycle.recover("s")
    runtime.lifecycle.enable("s")
    assert runtime.lifecycle.is_enabled("s")
    assert "s" in runtime.registry


# --- streaming ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_streaming_end_to_end() -> None:
    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        await ctx.emit("a")
        await ctx.emit("b")
        return SkillResult(invocation_id=req.invocation_id, output="ab")

    runtime = _runtime(_skill("s", body))
    sink = CollectingEventSink()
    result = await runtime.dispatcher.invoke(_req("s", "i1"), sink=sink)
    assert result.output == "ab"
    assert [c.delta for c in sink.chunks] == ["a", "b"]


# --- cancellation & timeout ---------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_end_to_end() -> None:
    started = asyncio.Event()

    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        started.set()
        await asyncio.sleep(10)
        return SkillResult(invocation_id=req.invocation_id, output="late")

    runtime = _runtime(_skill("s", body, timeout_ms=60_000))
    task = asyncio.ensure_future(runtime.dispatcher.invoke(_req("s", "ix")))
    await started.wait()
    runtime.dispatcher.cancel("ix")
    with pytest.raises(AppError) as exc_info:
        await task
    assert exc_info.value.code == SKILL_CANCELLED_CODE


@pytest.mark.asyncio
async def test_timeout_end_to_end() -> None:
    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        await asyncio.sleep(10)
        return SkillResult(invocation_id=req.invocation_id, output="late")

    runtime = _runtime(_skill("s", body, timeout_ms=10))
    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.invoke(_req("s", "i1"))
    assert exc_info.value.code == SKILL_TIMEOUT_CODE
    assert exc_info.value.kind is ErrorKind.TIMEOUT


# --- permission (allowed_tools scoping) ---------------------------------------


@pytest.mark.asyncio
async def test_permission_allowed_tool_scoping() -> None:
    tool_registry = ToolRegistry()
    tool_registry.register(_EchoTool())
    tools = ToolDispatcher(
        tool_registry, PolicyPermissionGate(PermissionPolicy(mode=PermissionMode.AUTO))
    )

    async def use_tool(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        assert ctx.execution is not None
        result = await ctx.execution.invoke_tool(
            ToolRequest(name="code.search", arguments={}, call_id=req.invocation_id)
        )
        return SkillResult(invocation_id=req.invocation_id, output=str(result.output))

    granted = _skill("g", use_tool, allowed=frozenset({"code.search"}))
    denied = _skill("d", use_tool, allowed=frozenset())
    runtime = build_skill_runtime(tools, skills=[granted, denied])

    ok = await runtime.dispatcher.invoke(
        _req("g", "i1"), execution=runtime.execution_for(granted)
    )
    assert ok.output == "tool-ran"

    with pytest.raises(AppError) as exc_info:
        await runtime.dispatcher.invoke(
            _req("d", "i2"), execution=runtime.execution_for(denied)
        )
    assert exc_info.value.code == SKILL_TOOL_OUT_OF_SCOPE_CODE


# --- parallel execution -------------------------------------------------------


@pytest.mark.asyncio
async def test_parallel_invocations_all_complete() -> None:
    async def double(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        await asyncio.sleep(0)  # yield to interleave
        value = req.inputs["x"]
        assert isinstance(value, int)
        return SkillResult(invocation_id=req.invocation_id, output=value * 2)

    runtime = _runtime(_skill("s", double))
    results = await asyncio.gather(
        *(runtime.dispatcher.invoke(_req("s", f"i{n}", x=n)) for n in range(5))
    )
    assert sorted(r.output for r in results) == [0, 2, 4, 6, 8]  # type: ignore[type-var]
    # every invocation cleaned up its cancellation token
    assert all(runtime.dispatcher._cancels.token_for(f"i{n}") is None for n in range(5))


@pytest.mark.asyncio
async def test_parallel_cancellation_is_isolated() -> None:
    started: dict[str, asyncio.Event] = {n: asyncio.Event() for n in ("a", "b", "c")}

    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        started[req.invocation_id].set()
        await asyncio.sleep(10)
        return SkillResult(invocation_id=req.invocation_id, output="done")

    fast = _echo

    async def _fast(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        return await fast(req, ctx)

    runtime = build_skill_runtime(
        _empty_tools(),
        skills=[_skill("slow", body, timeout_ms=60_000), _skill("fast", _fast)],
    )
    tasks = {
        name: asyncio.ensure_future(runtime.dispatcher.invoke(_req("slow", name)))
        for name in ("a", "b", "c")
    }
    for event in started.values():
        await event.wait()

    runtime.dispatcher.cancel("b")  # cancel only "b"
    with pytest.raises(AppError) as exc_info:
        await tasks["b"]
    assert exc_info.value.code == SKILL_CANCELLED_CODE

    # "a" and "c" are unaffected; the fast skill also still runs.
    runtime.dispatcher.cancel("a")
    runtime.dispatcher.cancel("c")
    for name in ("a", "c"):
        with pytest.raises(AppError):
            await tasks[name]
    fast_result = await runtime.dispatcher.invoke(_req("fast", "f1", x="hi"))
    assert fast_result.output == "hi"


@pytest.mark.asyncio
async def test_parallel_streaming_sinks_stay_separate() -> None:
    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        await ctx.emit(f"{req.invocation_id}-1")
        await asyncio.sleep(0)
        await ctx.emit(f"{req.invocation_id}-2")
        return SkillResult(invocation_id=req.invocation_id, output="ok")

    runtime = _runtime(_skill("s", body))
    sink_a = CollectingEventSink()
    sink_b = CollectingEventSink()
    await asyncio.gather(
        runtime.dispatcher.invoke(_req("s", "ia"), sink=sink_a),
        runtime.dispatcher.invoke(_req("s", "ib"), sink=sink_b),
    )
    assert [c.delta for c in sink_a.chunks] == ["ia-1", "ia-2"]
    assert [c.delta for c in sink_b.chunks] == ["ib-1", "ib-2"]
