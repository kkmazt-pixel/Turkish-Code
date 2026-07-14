"""Skill dispatcher (doc 19 §9) — resolve, run, bound, stream one invocation.

Resolves the skill from the registry, builds its :class:`SkillContext`
(cancellation token + streaming sink), and runs it bounded by the skill's timeout
and cooperatively cancellable (doc 19 §14). Every failure surfaces as a typed
:class:`~turkish_code.hata.AppError`; a returned :class:`SkillResult` always means
the invocation completed. Mirrors the Tool/Agent dispatchers — this runs skills,
it does not plan for them (no reasoning/workflow here).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Coroutine
from typing import Any

from turkish_code.hata import AppError
from turkish_code.yetenekler.baglam import (
    CancellationToken,
    NullEventSink,
    SkillContext,
    SkillEventSink,
    SkillExecutionContext,
)
from turkish_code.yetenekler.hata import (
    skill_cancelled,
    skill_failed,
    skill_timeout,
)
from turkish_code.yetenekler.kayit import SkillRegistry
from turkish_code.yetenekler.modeller import SkillRequest, SkillResult
from turkish_code.yetenekler.protocol import Skill


class _TimedOut(Exception):
    """Internal signal: the invocation exceeded its deadline."""


class _Cancelled(Exception):
    """Internal signal: the invocation was cooperatively cancelled."""


class CancellationRegistry:
    """Tracks one :class:`CancellationToken` per in-flight ``invocation_id``."""

    def __init__(self) -> None:
        self._tokens: dict[str, CancellationToken] = {}

    def register(self, invocation_id: str) -> CancellationToken:
        token = CancellationToken()
        self._tokens[invocation_id] = token
        return token

    def cancel(self, invocation_id: str) -> None:
        token = self._tokens.get(invocation_id)
        if token is not None:
            token.cancel()

    def unregister(self, invocation_id: str) -> None:
        self._tokens.pop(invocation_id, None)

    def token_for(self, invocation_id: str) -> CancellationToken | None:
        return self._tokens.get(invocation_id)


class SkillDispatcher:
    """Runs one skill invocation through the bounded pipeline (doc 19 §9)."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry
        self._cancels = CancellationRegistry()

    def cancel(self, invocation_id: str) -> None:
        """Cancel an in-flight invocation by id; no-op if unknown/finished."""
        self._cancels.cancel(invocation_id)

    async def invoke(
        self,
        request: SkillRequest,
        *,
        execution: SkillExecutionContext | None = None,
        sink: SkillEventSink | None = None,
        timeout_ms: int | None = None,
    ) -> SkillResult:
        """Resolve and run ``request``, bounded (doc 19 §9).

        Streamed :class:`SkillChunk` output goes to ``sink``; ``timeout_ms``
        overrides the skill's deadline. Raises a typed :class:`AppError`:
        ``skill_not_found``, ``skill_timeout``, ``skill_cancelled``, or
        ``skill_failed``.
        """
        skill = self._registry.resolve(request.skill_id)  # raises skill_not_found
        token = self._cancels.register(request.invocation_id)
        try:
            if token.is_cancelled:
                raise skill_cancelled(skill.metadata.id)
            context = SkillContext(
                invocation_id=request.invocation_id,
                run_id=request.run_id,
                cancellation=token,
                execution=execution,
                sink=sink if sink is not None else NullEventSink(),
            )
            deadline = (
                timeout_ms if timeout_ms is not None else skill.metadata.timeout_ms
            )
            return await self._run(skill, request, context, deadline, token)
        finally:
            self._cancels.unregister(request.invocation_id)

    async def _run(
        self,
        skill: Skill,
        request: SkillRequest,
        context: SkillContext,
        timeout_ms: int,
        token: CancellationToken,
    ) -> SkillResult:
        try:
            return await _guarded(
                skill.run(request, context),
                timeout_s=timeout_ms / 1000,
                token=token,
            )
        except _TimedOut:
            raise skill_timeout(skill.metadata.id, timeout_ms) from None
        except _Cancelled:
            raise skill_cancelled(skill.metadata.id) from None
        except AppError:
            raise  # the skill produced a typed error — propagate as-is
        except asyncio.CancelledError:
            raise  # a genuine outer cancellation of the invoke — never swallow
        except Exception as exc:
            raise skill_failed(skill.metadata.id, detail=str(exc)) from exc


async def _guarded(
    run_coro: Coroutine[Any, Any, SkillResult],
    *,
    timeout_s: float,
    token: CancellationToken,
) -> SkillResult:
    """Run ``run_coro`` bounded by ``timeout_s``, racing ``token`` (doc 19 §14).

    Returns the result if it finishes first, raises :class:`_Cancelled` if the
    token fires first, or :class:`_TimedOut` if neither finishes in time. The
    losing task is always cancelled and awaited so no orphan is left behind.
    """
    run_task: asyncio.Task[SkillResult] = asyncio.ensure_future(run_coro)
    cancel_task: asyncio.Task[None] = asyncio.ensure_future(token.wait())
    tasks: set[asyncio.Task[Any]] = {run_task, cancel_task}
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
    if run_task in done:
        return run_task.result()  # re-raises the skill's own exception, if any
    if cancel_task in done:
        raise _Cancelled
    raise _TimedOut
