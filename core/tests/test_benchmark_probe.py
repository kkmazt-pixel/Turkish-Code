"""Tests for latency probes (doc 50 §4)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from datetime import UTC, datetime, timedelta

import pytest
from turkish_code.gomme import EmbeddingKind
from turkish_code.saglayicilar.provider import (
    ChatChunk,
    ChatMessage,
    HealthStatus,
    ModelInfo,
    ProviderKind,
    RankedCandidate,
    TierInfo,
)
from turkish_code.yonlendirme.benchmark.probe import probe_median, probe_once
from turkish_code.yonlendirme.capability import CapabilitySet


class _SequenceClock:
    """A Clock that advances by a fixed step on every ``now()`` call.

    Local to this test module (deterministic elapsed-time testing for
    probes, doc 50) — not shared via conftest to avoid a dotted vs. bare
    module-name ambiguity under mypy without a ``tests`` package init.
    """

    def __init__(self, start: datetime, *, step: timedelta) -> None:
        self._next = start
        self._step = step

    def now(self) -> datetime:
        current = self._next
        self._next = self._next + self._step
        return current


class _TimedProvider:
    """A fake Provider whose ``chat`` yields a fixed number of chunks."""

    def __init__(self, chunk_count: int) -> None:
        self._chunk_count = chunk_count

    @property
    def id(self) -> str:
        return "timed"

    @property
    def kind(self) -> ProviderKind:
        return ProviderKind.CLOUD

    @property
    def is_offline_fallback(self) -> bool:
        return False

    @property
    def tier_info(self) -> TierInfo:
        return TierInfo(tier="free", quota_limits={})

    async def list_models(self) -> Sequence[ModelInfo]:
        return []

    async def chat(
        self,
        model: str,
        messages: Sequence[ChatMessage],
        *,
        tools: Sequence[Mapping[str, object]] | None = None,
        opts: Mapping[str, object] | None = None,
    ) -> AsyncIterator[ChatChunk]:
        for i in range(self._chunk_count):
            is_last = i == self._chunk_count - 1
            yield ChatChunk(delta="tok", finish_reason="stop" if is_last else None)

    async def embed(
        self, model: str, texts: Sequence[str], kind: EmbeddingKind
    ) -> Sequence[Sequence[float]]:
        raise NotImplementedError

    async def rerank(
        self, model: str, query: str, candidates: Sequence[str]
    ) -> Sequence[RankedCandidate]:
        raise NotImplementedError

    async def health(self) -> HealthStatus:
        return HealthStatus.UP

    def capabilities(self, model: str) -> CapabilitySet:
        raise NotImplementedError


@pytest.mark.asyncio
async def test_probe_once_measures_ttft_and_total() -> None:
    clock = _SequenceClock(datetime(2026, 7, 13, tzinfo=UTC), step=timedelta(seconds=1))
    sample = await probe_once(_TimedProvider(3), "m", prompt="hi", clock=clock)

    # start=t0, chunk1 at t0+1s (ttft), chunk2 at t0+2s, chunk3 at t0+3s (total)
    assert sample.ttft_seconds == 1.0
    assert sample.total_seconds == 3.0
    assert sample.chunk_count == 3


@pytest.mark.asyncio
async def test_probe_median_of_k_repeats() -> None:
    clock = _SequenceClock(datetime(2026, 7, 13, tzinfo=UTC), step=timedelta(seconds=1))
    median = await probe_median(_TimedProvider(2), "m", clock=clock, k=3)

    assert median.ttft_seconds == 1.0
    assert median.chunk_count == 2


@pytest.mark.asyncio
async def test_probe_median_rejects_non_positive_k() -> None:
    clock = _SequenceClock(datetime(2026, 7, 13, tzinfo=UTC), step=timedelta(seconds=1))
    with pytest.raises(ValueError):
        await probe_median(_TimedProvider(1), "m", clock=clock, k=0)
