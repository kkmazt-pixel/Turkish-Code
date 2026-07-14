"""Agent dispatcher (doc 18 §5/§9) — route, run, bound, stream one agent run.

Resolves the target agent from the registry (or the default when the request
names none), builds its :class:`AgentContext` (cancellation token + streaming
sink), and runs it bounded by the agent's timeout and cooperatively cancellable
(doc 18 §9). Every failure surfaces as a typed
:class:`~turkish_code.hata.AppError`; a returned :class:`AgentResponse` always
means the run completed. Mirrors the Tool Runtime dispatcher — this phase runs
agents, it does not reason for them (doc 15 out of scope).
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Coroutine
from typing import Any

from turkish_code.ajanlar.baglam import (
    AgentContext,
    AgentEventSink,
    ConversationContext,
    ExecutionContext,
    NullEventSink,
    SessionContext,
)
from turkish_code.ajanlar.iptal import CancellationRegistry, CancellationToken
from turkish_code.ajanlar.kayit import AgentRegistry
from turkish_code.ajanlar.modeller import AgentRequest, AgentResponse
from turkish_code.ajanlar.protocol import Agent
from turkish_code.hata import AppError, ErrorKind

AGENT_TIMEOUT_CODE = "agent.timeout"
AGENT_CANCELLED_CODE = "agent.cancelled"
AGENT_FAILED_CODE = "agent.failed"


class _TimedOut(Exception):
    """Internal signal: the run exceeded its deadline."""


class _Cancelled(Exception):
    """Internal signal: the run was cooperatively cancelled."""


class AgentDispatcher:
    """Runs one agent run through the routed, bounded pipeline (doc 18 §5/§9)."""

    def __init__(self, registry: AgentRegistry) -> None:
        self._registry = registry
        self._cancels = CancellationRegistry()

    def cancel(self, run_id: str) -> None:
        """Cancel an in-flight run by id; no-op if unknown/finished (doc 18 §9)."""
        self._cancels.cancel(run_id)

    async def dispatch(
        self,
        request: AgentRequest,
        *,
        execution: ExecutionContext | None = None,
        conversation: ConversationContext | None = None,
        session: SessionContext | None = None,
        sink: AgentEventSink | None = None,
        timeout_ms: int | None = None,
    ) -> AgentResponse:
        """Route ``request`` to its agent and run it, bounded (doc 18 §5/§9).

        The agent id routes to a registered agent, or — when empty — to the
        registry default (doc 18 §10). Streamed :class:`AgentChunk` output goes
        to ``sink``; ``timeout_ms`` overrides the agent's own deadline. Raises a
        typed :class:`AppError`: ``agent_not_found``, ``agent_timeout``,
        ``agent_cancelled``, or ``agent_failed``.
        """
        agent = self._resolve(request)
        token = self._cancels.register(request.run_id)
        try:
            if token.is_cancelled:
                raise _cancelled(agent.metadata.id)
            context = AgentContext(
                run_id=request.run_id,
                session_id=request.session_id,
                conversation=conversation,
                execution=execution,
                session=session,
                cancellation=token,
                sink=sink if sink is not None else NullEventSink(),
            )
            deadline = (
                timeout_ms if timeout_ms is not None else agent.metadata.timeout_ms
            )
            return await self._run(agent, request, context, deadline, token)
        finally:
            self._cancels.unregister(request.run_id)

    def _resolve(self, request: AgentRequest) -> Agent:
        if request.agent_id:
            return self._registry.resolve(request.agent_id)
        return self._registry.resolve_default()

    async def _run(
        self,
        agent: Agent,
        request: AgentRequest,
        context: AgentContext,
        timeout_ms: int,
        token: CancellationToken,
    ) -> AgentResponse:
        try:
            return await _guarded(
                agent.run(request, context),
                timeout_s=timeout_ms / 1000,
                token=token,
            )
        except _TimedOut:
            raise _timeout(agent.metadata.id, timeout_ms) from None
        except _Cancelled:
            raise _cancelled(agent.metadata.id) from None
        except AppError:
            raise  # the agent produced a typed error — propagate as-is
        except asyncio.CancelledError:
            raise  # a genuine outer cancellation of the dispatch — never swallow
        except Exception as exc:
            raise _failed(agent.metadata.id, str(exc)) from exc


async def _guarded(
    run_coro: Coroutine[Any, Any, AgentResponse],
    *,
    timeout_s: float,
    token: CancellationToken,
) -> AgentResponse:
    """Run ``run_coro`` bounded by ``timeout_s``, racing ``token`` (doc 18 §9).

    Returns the run's result if it finishes first, raises :class:`_Cancelled` if
    the token fires first, or :class:`_TimedOut` if neither finishes in time. The
    losing task is always cancelled and awaited so no orphan is left behind.
    """
    run_task: asyncio.Task[AgentResponse] = asyncio.ensure_future(run_coro)
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
        return run_task.result()  # re-raises the agent's own exception, if any
    if cancel_task in done:
        raise _Cancelled
    raise _TimedOut


def _timeout(agent_id: str, timeout_ms: int) -> AppError:
    return _err(
        ErrorKind.TIMEOUT,
        AGENT_TIMEOUT_CODE,
        f"{agent_id!r} exceeded {timeout_ms}ms",
        agent_id,
        retryable=True,
    )


def _cancelled(agent_id: str) -> AppError:
    return _err(
        ErrorKind.CANCELLED,
        AGENT_CANCELLED_CODE,
        f"{agent_id!r} was cancelled",
        agent_id,
        retryable=False,
    )


def _failed(agent_id: str, detail: str) -> AppError:
    return _err(
        ErrorKind.INTERNAL,
        AGENT_FAILED_CODE,
        f"{agent_id!r} failed: {detail}",
        agent_id,
        retryable=False,
    )


def _err(
    kind: ErrorKind, code: str, detail: str, agent_id: str, *, retryable: bool
) -> AppError:
    return AppError(
        kind=kind,
        code=code,
        message_key=f"hata.{code}",
        retryable=retryable,
        detail=detail,
        context={"agent": agent_id},
    )
