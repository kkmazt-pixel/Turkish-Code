"""Tests for the failover/retry/timeout/cooldown loop (doc 45 §6)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from turkish_code.hata import AppError, ErrorKind
from turkish_code.ortak.saat import Clock
from turkish_code.saglayicilar.provider import RATE_LIMIT_CODE, ChatChunk
from turkish_code.yonlendirme.candidates import Candidate
from turkish_code.yonlendirme.quota.store import InMemoryQuotaStore
from turkish_code.yonlendirme.quota.tracker import QuotaTracker
from turkish_code.yonlendirme.resilience import execute_with_failover
from turkish_code.yonlendirme.scoring.combine import ScoredCandidate, score_candidate
from turkish_code.yonlendirme.scoring.model_score import ScoreBreakdown

from tests.fakes import StubProvider, failing_behavior, success_behavior


async def _make_candidate(
    provider: StubProvider, score: float
) -> tuple[Candidate, ScoredCandidate]:
    models = await provider.list_models()
    model = models[0]
    candidate = Candidate(model=model, provider=provider)
    breakdown = ScoreBreakdown(factors={}, total=score)
    scored = score_candidate(model.id, provider.id, breakdown, breakdown)
    return candidate, scored


async def _collect(stream: AsyncIterator[ChatChunk]) -> list[str]:
    return [chunk.delta async for chunk in stream]


@pytest.mark.asyncio
async def test_first_candidate_success_no_failover(fixed_clock: Clock) -> None:
    provider = StubProvider("groq", chat_behavior=success_behavior("hi"))
    candidate, scored = await _make_candidate(provider, 1.0)
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    stream = execute_with_failover(
        [scored],
        {(scored.provider_id, scored.model_id): candidate},
        [],
        quota_tracker=tracker,
        clock=fixed_clock,
    )
    assert await _collect(stream) == ["hi"]


@pytest.mark.asyncio
async def test_rate_limit_triggers_cooldown_and_failover(fixed_clock: Clock) -> None:
    rate_limit_error = AppError(
        kind=ErrorKind.PROVIDER,
        code=RATE_LIMIT_CODE,
        message_key="hata.provider.rate_limited",
        retryable=True,
    )
    bad_provider = StubProvider(
        "groq", chat_behavior=failing_behavior(rate_limit_error)
    )
    good_provider = StubProvider("gemini", chat_behavior=success_behavior("backup"))
    bad_candidate, bad_scored = await _make_candidate(bad_provider, 1.0)
    good_candidate, good_scored = await _make_candidate(good_provider, 0.5)
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    lookup = {
        (bad_scored.provider_id, bad_scored.model_id): bad_candidate,
        (good_scored.provider_id, good_scored.model_id): good_candidate,
    }
    stream = execute_with_failover(
        [bad_scored, good_scored], lookup, [], quota_tracker=tracker, clock=fixed_clock
    )

    assert await _collect(stream) == ["backup"]
    assert tracker.is_cooling_down("groq") is True


@pytest.mark.asyncio
async def test_all_candidates_failing_raises_unroutable(fixed_clock: Clock) -> None:
    error = AppError(
        kind=ErrorKind.PROVIDER,
        code="provider.broken",
        message_key="hata.provider.broken",
        retryable=False,
    )
    provider = StubProvider("groq", chat_behavior=failing_behavior(error))
    candidate, scored = await _make_candidate(provider, 1.0)
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    stream = execute_with_failover(
        [scored],
        {(scored.provider_id, scored.model_id): candidate},
        [],
        quota_tracker=tracker,
        clock=fixed_clock,
        max_retries=0,
    )
    with pytest.raises(AppError) as excinfo:
        await _collect(stream)
    assert excinfo.value.code == "routing.unroutable"


@pytest.mark.asyncio
async def test_non_rate_limit_error_does_not_trigger_cooldown(
    fixed_clock: Clock,
) -> None:
    error = AppError(
        kind=ErrorKind.PROVIDER,
        code="provider.broken",
        message_key="hata.provider.broken",
        retryable=False,
    )
    bad_provider = StubProvider("groq", chat_behavior=failing_behavior(error))
    good_provider = StubProvider("gemini", chat_behavior=success_behavior("ok"))
    bad_candidate, bad_scored = await _make_candidate(bad_provider, 1.0)
    good_candidate, good_scored = await _make_candidate(good_provider, 0.5)
    tracker = QuotaTracker(InMemoryQuotaStore(), fixed_clock)

    lookup = {
        (bad_scored.provider_id, bad_scored.model_id): bad_candidate,
        (good_scored.provider_id, good_scored.model_id): good_candidate,
    }
    stream = execute_with_failover(
        [bad_scored, good_scored],
        lookup,
        [],
        quota_tracker=tracker,
        clock=fixed_clock,
        max_retries=0,
    )

    assert await _collect(stream) == ["ok"]
    assert tracker.is_cooling_down("groq") is False
