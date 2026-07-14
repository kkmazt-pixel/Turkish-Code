"""Tool dispatcher (doc 20 §5) — the one execution pipeline for a tool call.

Runs the non-bypassable lifecycle for a single call: **resolve → permission →
execute**, bounded by the tool's timeout and cooperatively cancellable (doc 20
§5/§14). Every failure surfaces as a typed :class:`~turkish_code.hata.AppError`
(:mod:`turkish_code.araclar.hata`); a returned :class:`ToolResult` therefore
always means the tool ran and succeeded. The snapshot (doc 27) and timeline
(doc 26) hooks of the full lifecycle are out of this runtime's scope — brokered
mutation and audit live in the Kabuk (doc 20 §5 steps 5/7); this dispatcher owns
permission + execution + bounding.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Coroutine
from typing import Any

from turkish_code.araclar.akis import NullProgressSink, ProgressSink
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.hata import (
    tool_cancelled,
    tool_denied,
    tool_failed,
    tool_timeout,
)
from turkish_code.araclar.iptal import CancellationRegistry, CancellationToken
from turkish_code.araclar.izin import Allow, PermissionGate, PermissionRequest
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.modeller import ToolMetadata, ToolRequest, ToolResult
from turkish_code.araclar.protocol import Tool
from turkish_code.hata import AppError


class _TimedOut(Exception):
    """Internal signal: execution exceeded the deadline."""


class _Cancelled(Exception):
    """Internal signal: execution was cooperatively cancelled."""


class ToolDispatcher:
    """Executes one tool call through the gated, bounded pipeline (doc 20 §5)."""

    def __init__(self, registry: ToolRegistry, gate: PermissionGate) -> None:
        self._registry = registry
        self._gate = gate
        self._cancels = CancellationRegistry()

    def cancel(self, call_id: str) -> None:
        """Cancel an in-flight call by id; no-op if unknown/finished (doc 20 §14)."""
        self._cancels.cancel(call_id)

    async def dispatch(
        self, request: ToolRequest, *, progress: ProgressSink | None = None
    ) -> ToolResult:
        """Resolve, permission-gate, and execute ``request`` (doc 20 §5).

        Incremental :class:`ToolProgress` events the tool emits are forwarded to
        ``progress`` (dropped when ``None``); the returned :class:`ToolResult` is
        the call's final event (doc 20 §7). Raises a typed :class:`AppError`:
        ``tool_not_found`` (unknown tool), ``tool_denied`` (permission),
        ``tool_timeout``/``tool_cancelled`` (bounding), or ``tool_failed`` (the
        tool raised). Never bypasses the permission gate.
        """
        tool = self._registry.resolve(request.name)  # raises tool_not_found
        meta = tool.metadata
        # Register the token before gating so a cancellation arriving while the
        # permission prompt is pending (doc 24 §6 may await the user) aborts the
        # call before it ever executes (doc 20 §14).
        token = self._cancels.register(request.call_id)
        try:
            await self._check_permission(meta)
            if token.is_cancelled:
                raise tool_cancelled(meta.name)
            context = ToolContext(
                call_id=request.call_id,
                run_id=request.run_id,
                cancellation=token,
                progress=progress if progress is not None else NullProgressSink(),
            )
            return await self._execute(tool, request, context, meta, token)
        finally:
            self._cancels.unregister(request.call_id)

    async def _check_permission(self, meta: ToolMetadata) -> None:
        decision = await self._gate.evaluate(
            PermissionRequest(
                tool=meta.name,
                capability=meta.capability,
                side_effect=meta.side_effect,
                # Capability-level gating; target-scoped gating (fs.write on
                # src/**) needs tool-specific target extraction — a documented
                # refinement (doc 24 §8/§18), not modelled in this substrate.
                target=None,
            )
        )
        if isinstance(decision, Allow):
            return
        # Deny → typed denial. PromptRequired → a non-interactive dispatcher
        # cannot resolve consent, so it fails safe to a denial (doc 24 §6); the
        # Kabuk-bridge gate resolves prompts itself before returning allow/deny.
        raise tool_denied(meta.name, meta.capability)

    async def _execute(
        self,
        tool: Tool,
        request: ToolRequest,
        context: ToolContext,
        meta: ToolMetadata,
        token: CancellationToken,
    ) -> ToolResult:
        try:
            return await _guarded(
                tool.execute(request, context),
                timeout_s=meta.timeout_ms / 1000,
                token=token,
            )
        except _TimedOut:
            raise tool_timeout(meta.name, meta.timeout_ms) from None
        except _Cancelled:
            raise tool_cancelled(meta.name) from None
        except AppError:
            raise  # the tool already produced a typed error — propagate as-is
        except asyncio.CancelledError:
            raise  # a genuine outer cancellation of the dispatch — never swallow
        except Exception as exc:
            raise tool_failed(meta.name, detail=str(exc)) from exc


async def _guarded(
    exec_coro: Coroutine[Any, Any, ToolResult],
    *,
    timeout_s: float,
    token: CancellationToken,
) -> ToolResult:
    """Run ``exec_coro`` bounded by ``timeout_s`` and racing ``token`` (doc 20 §14).

    Returns the tool's result if it finishes first, raises :class:`_Cancelled` if
    the token fires first, or :class:`_TimedOut` if neither finishes in time. The
    losing task is always cancelled and awaited so no orphan is left behind
    (doc 20 §14, doc 08 §11 "no orphans").
    """
    exec_task: asyncio.Task[ToolResult] = asyncio.ensure_future(exec_coro)
    cancel_task: asyncio.Task[None] = asyncio.ensure_future(token.wait())
    tasks: set[asyncio.Task[Any]] = {exec_task, cancel_task}
    try:
        done, pending = await asyncio.wait(
            tasks, timeout=timeout_s, return_when=asyncio.FIRST_COMPLETED
        )
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        raise
    for task in pending:
        task.cancel()
    for task in pending:
        with contextlib.suppress(asyncio.CancelledError):
            await task
    if exec_task in done:
        return exec_task.result()  # re-raises the tool's own exception, if any
    if cancel_task in done:
        raise _Cancelled
    raise _TimedOut
