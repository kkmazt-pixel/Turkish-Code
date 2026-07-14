"""Tests for the skill dispatcher — invoke, streaming, cancel, timeout (doc 19 §9)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from turkish_code.hata import AppError, ErrorKind
from turkish_code.yetenekler.baglam import CollectingEventSink, SkillContext
from turkish_code.yetenekler.dagitici import SkillDispatcher
from turkish_code.yetenekler.hata import (
    SKILL_CANCELLED_CODE,
    SKILL_FAILED_CODE,
    SKILL_NOT_FOUND_CODE,
    SKILL_TIMEOUT_CODE,
)
from turkish_code.yetenekler.kayit import SkillRegistry
from turkish_code.yetenekler.modeller import (
    SkillMetadata,
    SkillRequest,
    SkillResult,
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


def _meta(skill_id: str = "s", *, timeout_ms: int = 1000) -> SkillMetadata:
    return SkillMetadata(id=skill_id, description="ne zaman", timeout_ms=timeout_ms)


async def _echo(req: SkillRequest, ctx: SkillContext) -> SkillResult:
    return SkillResult(invocation_id=req.invocation_id, output=req.inputs.get("x"))


def _dispatcher(*skills: _FnSkill) -> SkillDispatcher:
    registry = SkillRegistry()
    for skill in skills:
        registry.register(skill)
    return SkillDispatcher(registry)


def _req(skill_id: str = "s", invocation_id: str = "i1") -> SkillRequest:
    return SkillRequest(
        skill_id=skill_id, inputs={"x": 42}, invocation_id=invocation_id
    )


# --- invoke -------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoke_runs_skill_and_returns_result() -> None:
    dispatcher = _dispatcher(_FnSkill(_meta(), _echo))
    result = await dispatcher.invoke(_req())
    assert result.output == 42
    assert result.invocation_id == "i1"


@pytest.mark.asyncio
async def test_unknown_skill_raises_not_found() -> None:
    dispatcher = _dispatcher(_FnSkill(_meta("s"), _echo))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.invoke(_req("absent"))
    assert exc_info.value.code == SKILL_NOT_FOUND_CODE


# --- streaming ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_invoke_streams_chunks_then_returns_result() -> None:
    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        await ctx.emit("bir")
        await ctx.emit("iki")
        return SkillResult(invocation_id=req.invocation_id, output="son")

    dispatcher = _dispatcher(_FnSkill(_meta(), body))
    sink = CollectingEventSink()
    result = await dispatcher.invoke(_req(), sink=sink)
    assert result.output == "son"
    assert [c.delta for c in sink.chunks] == ["bir", "iki"]
    assert all(c.invocation_id == "i1" for c in sink.chunks)


@pytest.mark.asyncio
async def test_emit_without_sink_is_noop() -> None:
    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        await ctx.emit("noop")
        return SkillResult(invocation_id=req.invocation_id, output="ok")

    dispatcher = _dispatcher(_FnSkill(_meta(), body))
    assert (await dispatcher.invoke(_req())).output == "ok"


# --- timeout ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_is_enforced() -> None:
    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        await asyncio.sleep(10)
        return SkillResult(invocation_id=req.invocation_id, output="late")

    dispatcher = _dispatcher(_FnSkill(_meta(timeout_ms=10), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.invoke(_req())
    assert exc_info.value.code == SKILL_TIMEOUT_CODE
    assert exc_info.value.kind is ErrorKind.TIMEOUT


@pytest.mark.asyncio
async def test_timeout_override() -> None:
    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        await asyncio.sleep(10)
        return SkillResult(invocation_id=req.invocation_id, output="late")

    dispatcher = _dispatcher(_FnSkill(_meta(timeout_ms=60_000), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.invoke(_req(), timeout_ms=10)
    assert exc_info.value.code == SKILL_TIMEOUT_CODE


# --- cancellation -------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_stops_invocation() -> None:
    started = asyncio.Event()

    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        started.set()
        await asyncio.sleep(10)
        return SkillResult(invocation_id=req.invocation_id, output="done")

    dispatcher = _dispatcher(_FnSkill(_meta(timeout_ms=60_000), body))
    task = asyncio.ensure_future(dispatcher.invoke(_req(invocation_id="ix")))
    await started.wait()
    dispatcher.cancel("ix")
    with pytest.raises(AppError) as exc_info:
        await task
    assert exc_info.value.code == SKILL_CANCELLED_CODE
    assert exc_info.value.kind is ErrorKind.CANCELLED


@pytest.mark.asyncio
async def test_context_carries_cancellation_token() -> None:
    seen: dict[str, object] = {}

    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        seen["has_token"] = ctx.cancellation is not None
        seen["invocation_id"] = ctx.invocation_id
        return SkillResult(invocation_id=req.invocation_id, output=None)

    dispatcher = _dispatcher(_FnSkill(_meta(), body))
    await dispatcher.invoke(_req(invocation_id="iz"))
    assert seen == {"has_token": True, "invocation_id": "iz"}


# --- error propagation --------------------------------------------------------


@pytest.mark.asyncio
async def test_skill_apperror_propagates_unchanged() -> None:
    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        raise AppError(
            kind=ErrorKind.VALIDATION,
            code="x.bad",
            message_key="hata.x.bad",
            retryable=False,
        )

    dispatcher = _dispatcher(_FnSkill(_meta(), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.invoke(_req())
    assert exc_info.value.kind is ErrorKind.VALIDATION  # not wrapped


@pytest.mark.asyncio
async def test_unexpected_exception_is_wrapped_as_failed() -> None:
    async def body(req: SkillRequest, ctx: SkillContext) -> SkillResult:
        raise RuntimeError("boom")

    dispatcher = _dispatcher(_FnSkill(_meta(), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.invoke(_req())
    assert exc_info.value.code == SKILL_FAILED_CODE
    assert exc_info.value.kind is ErrorKind.INTERNAL


@pytest.mark.asyncio
async def test_invocation_untracked_after_completion() -> None:
    dispatcher = _dispatcher(_FnSkill(_meta(), _echo))
    await dispatcher.invoke(_req(invocation_id="done"))
    assert dispatcher._cancels.token_for("done") is None
