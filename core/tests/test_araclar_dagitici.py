"""Tests for the tool dispatcher — real execution flow (doc 20 §5/§14)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import pytest
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.dagitici import ToolDispatcher
from turkish_code.araclar.hata import (
    TOOL_CANCELLED_CODE,
    TOOL_DENIED_CODE,
    TOOL_FAILED_CODE,
    TOOL_NOT_FOUND_CODE,
    TOOL_TIMEOUT_CODE,
    invalid_tool_args,
)
from turkish_code.araclar.izin import (
    Allow,
    PermissionMode,
    PermissionPolicy,
    PermissionRequest,
    PolicyPermissionGate,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.modeller import (
    Capability,
    SideEffect,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from turkish_code.hata import AppError, ErrorKind

_Body = Callable[[ToolRequest, ToolContext], Awaitable[ToolResult]]


class _FnTool:
    """A tool whose ``execute`` is an injected coroutine — real flow, no mocks."""

    def __init__(self, metadata: ToolMetadata, body: _Body) -> None:
        self._metadata = metadata
        self._body = body

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return await self._body(request, context)


def _meta(
    name: str = "fs.read",
    *,
    capability: Capability | None = Capability.FS_READ,
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


def _dispatcher(
    tool: _FnTool, *, mode: PermissionMode = PermissionMode.AUTO
) -> ToolDispatcher:
    registry = ToolRegistry()
    registry.register(tool)
    gate = PolicyPermissionGate(PermissionPolicy(mode=mode))
    return ToolDispatcher(registry, gate)


def _request(name: str = "fs.read", call_id: str = "c1") -> ToolRequest:
    return ToolRequest(name=name, arguments={}, call_id=call_id)


@pytest.mark.asyncio
async def test_dispatch_runs_tool_and_returns_result() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        return ToolResult(call_id=req.call_id, output={"ok": True})

    dispatcher = _dispatcher(_FnTool(_meta(), body))
    result = await dispatcher.dispatch(_request())
    assert result.output == {"ok": True}
    assert result.call_id == "c1"


@pytest.mark.asyncio
async def test_unknown_tool_raises_not_found() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        return ToolResult(call_id=req.call_id, output=None)

    dispatcher = _dispatcher(_FnTool(_meta(), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_request(name="absent"))
    assert exc_info.value.code == TOOL_NOT_FOUND_CODE


@pytest.mark.asyncio
async def test_permission_denied_blocks_execution() -> None:
    ran = False

    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        nonlocal ran
        ran = True
        return ToolResult(call_id=req.call_id, output=None)

    # Plan mode denies a mutating tool; the body must never run (doc 24 §5).
    tool = _FnTool(
        _meta(
            "fs.write", capability=Capability.FS_WRITE, side_effect=SideEffect.MUTATE
        ),
        body,
    )
    dispatcher = _dispatcher(tool, mode=PermissionMode.PLAN)
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_request(name="fs.write"))
    assert exc_info.value.code == TOOL_DENIED_CODE
    assert exc_info.value.kind is ErrorKind.PERMISSION
    assert ran is False


@pytest.mark.asyncio
async def test_prompt_required_fails_safe_to_denied() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        return ToolResult(call_id=req.call_id, output=None)

    # Ask mode with no grant → PromptRequired; a non-interactive dispatcher
    # must fail safe to a denial, never an implicit allow (doc 24 §6).
    tool = _FnTool(
        _meta(
            "fs.write", capability=Capability.FS_WRITE, side_effect=SideEffect.MUTATE
        ),
        body,
    )
    dispatcher = _dispatcher(tool, mode=PermissionMode.ASK)
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_request(name="fs.write"))
    assert exc_info.value.code == TOOL_DENIED_CODE


@pytest.mark.asyncio
async def test_timeout_is_enforced() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        await asyncio.sleep(10)  # far exceeds the 10ms deadline
        return ToolResult(call_id=req.call_id, output=None)

    dispatcher = _dispatcher(_FnTool(_meta(timeout_ms=10), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_request())
    assert exc_info.value.code == TOOL_TIMEOUT_CODE
    assert exc_info.value.kind is ErrorKind.TIMEOUT


@pytest.mark.asyncio
async def test_cancellation_stops_execution() -> None:
    started = asyncio.Event()

    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        started.set()
        await asyncio.sleep(10)  # would outlast the test without cancellation
        return ToolResult(call_id=req.call_id, output=None)

    dispatcher = _dispatcher(_FnTool(_meta(timeout_ms=60_000), body))
    task = asyncio.ensure_future(dispatcher.dispatch(_request(call_id="cx")))
    await started.wait()
    dispatcher.cancel("cx")
    with pytest.raises(AppError) as exc_info:
        await task
    assert exc_info.value.code == TOOL_CANCELLED_CODE
    assert exc_info.value.kind is ErrorKind.CANCELLED


@pytest.mark.asyncio
async def test_cancellation_during_permission_prevents_execution() -> None:
    ran = False

    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        nonlocal ran
        ran = True
        return ToolResult(call_id=req.call_id, output=None)

    class _CancellingGate:
        """A gate that cancels the call while "prompting", then allows it."""

        def __init__(self) -> None:
            self.dispatcher: ToolDispatcher | None = None
            self.call_id = ""

        async def evaluate(self, request: PermissionRequest) -> Allow:
            assert self.dispatcher is not None
            self.dispatcher.cancel(self.call_id)  # user cancels mid-prompt
            return Allow()

    registry = ToolRegistry()
    registry.register(_FnTool(_meta(), body))
    gate = _CancellingGate()
    dispatcher = ToolDispatcher(registry, gate)
    gate.dispatcher = dispatcher
    gate.call_id = "cy"
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_request(call_id="cy"))
    assert exc_info.value.code == TOOL_CANCELLED_CODE
    assert ran is False  # the body never ran despite the gate allowing


@pytest.mark.asyncio
async def test_tool_apperror_propagates_unchanged() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        raise invalid_tool_args("fs.read", "missing path")

    dispatcher = _dispatcher(_FnTool(_meta(), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_request())
    assert exc_info.value.kind is ErrorKind.VALIDATION  # not wrapped as tool.failed


@pytest.mark.asyncio
async def test_unexpected_exception_is_wrapped_as_failed() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        raise RuntimeError("boom")

    dispatcher = _dispatcher(_FnTool(_meta(), body))
    with pytest.raises(AppError) as exc_info:
        await dispatcher.dispatch(_request())
    assert exc_info.value.code == TOOL_FAILED_CODE
    assert exc_info.value.kind is ErrorKind.INTERNAL


@pytest.mark.asyncio
async def test_context_carries_cancellation_token() -> None:
    seen: dict[str, object] = {}

    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        seen["has_token"] = ctx.cancellation is not None
        seen["call_id"] = ctx.call_id
        return ToolResult(call_id=req.call_id, output=None)

    dispatcher = _dispatcher(_FnTool(_meta(), body))
    await dispatcher.dispatch(_request(call_id="cz"))
    assert seen == {"has_token": True, "call_id": "cz"}


@pytest.mark.asyncio
async def test_call_id_is_untracked_after_completion() -> None:
    async def body(req: ToolRequest, ctx: ToolContext) -> ToolResult:
        return ToolResult(call_id=req.call_id, output=None)

    dispatcher = _dispatcher(_FnTool(_meta(), body))
    await dispatcher.dispatch(_request(call_id="done"))
    # finally-block cleanup: the token is no longer tracked.
    assert dispatcher._cancels.token_for("done") is None
