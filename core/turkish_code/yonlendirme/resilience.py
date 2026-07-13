"""Failover, retry, timeout, cooldown — the resilience loop (doc 45 §6).

Tries ranked candidates in order. A failure **before any chunk was yielded**
is retried on the same model (bounded) unless it's a rate-limit, then fails
over to the next-best candidate; a rate-limit cools the provider down
immediately. A failure **after streaming has started** is not retried or
failed over silently — partial output was already delivered to the caller,
so resuming mid-stream would require checkpoint/resume machinery (doc 28),
which is out of scope here; the error simply propagates.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import timedelta

from turkish_code.hata import AppError, ErrorKind
from turkish_code.ortak.saat import Clock
from turkish_code.saglayicilar.provider import RATE_LIMIT_CODE, ChatChunk, ChatMessage
from turkish_code.yonlendirme.candidates import Candidate
from turkish_code.yonlendirme.quota.tracker import QuotaTracker
from turkish_code.yonlendirme.scoring.combine import ScoredCandidate

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_COOLDOWN = timedelta(seconds=30)


async def execute_with_failover(
    ranked: Sequence[ScoredCandidate],
    candidates_by_key: Mapping[tuple[str, str], Candidate],
    messages: Sequence[ChatMessage],
    *,
    quota_tracker: QuotaTracker,
    clock: Clock,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    cooldown: timedelta = DEFAULT_COOLDOWN,
) -> AsyncIterator[ChatChunk]:
    """Stream from the best candidate that succeeds, failing over as needed."""
    last_error: AppError | None = None
    for scored in ranked:
        candidate = candidates_by_key[(scored.provider_id, scored.model_id)]
        try:
            async for chunk in _attempt_with_retry(
                candidate,
                messages,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            ):
                yield chunk
            return
        except AppError as err:
            last_error = err
            if err.code == RATE_LIMIT_CODE:
                quota_tracker.enter_cooldown(
                    candidate.provider.id, until=clock.now() + cooldown
                )
            continue

    raise AppError(
        kind=ErrorKind.PROVIDER,
        code="routing.unroutable",
        message_key="hata.routing.unroutable",
        retryable=False,
        cause=last_error,
    )


async def _attempt_with_retry(
    candidate: Candidate,
    messages: Sequence[ChatMessage],
    *,
    timeout_seconds: float,
    max_retries: int,
) -> AsyncIterator[ChatChunk]:
    """Call ``candidate`` once, retrying pre-stream failures up to ``max_retries``."""
    attempt = 0
    while True:
        yielded_any = False
        try:
            async with asyncio.timeout(timeout_seconds):
                stream = candidate.provider.chat(candidate.model.id, messages)
                async for chunk in stream:
                    yielded_any = True
                    yield chunk
            return
        except TimeoutError as exc:
            timeout_error = AppError(
                kind=ErrorKind.TIMEOUT,
                code="provider.timeout",
                message_key="hata.provider.timeout",
                retryable=not yielded_any,
            )
            if yielded_any or attempt >= max_retries:
                raise timeout_error from exc
            attempt += 1
            continue
        except AppError as err:
            if yielded_any or err.code == RATE_LIMIT_CODE or attempt >= max_retries:
                raise
            attempt += 1
            continue
