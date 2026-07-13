"""Latency probes: ttft, tokens/sec, total (doc 50 §4).

Sends a small standard prompt through the real :class:`Provider` interface and
measures via the injected :class:`Clock` (not the wall clock directly) so
timing is deterministic under test. Repeats ``k`` times and takes the median,
robust to outliers (doc 50 §4). Probing is quota-aware: callers should check
:meth:`~turkish_code.yonlendirme.quota.tracker.QuotaTracker.is_cooling_down`
before probing (doc 50 §4/§8) — this module only measures.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from turkish_code.ortak.saat import Clock
from turkish_code.saglayicilar.provider import ChatMessage, Provider

DEFAULT_PROBE_PROMPT = "Merhaba, kısaca kendini tanıt."
"""The small, fixed, quota-cheap probe prompt (doc 50 §4)."""

DEFAULT_K = 5
"""Default repeat count for median-of-K probing (doc 50 §4)."""


@dataclass(frozen=True, slots=True)
class ProbeSample:
    """One probe run's raw measurements (doc 50 §4)."""

    ttft_seconds: float
    total_seconds: float
    chunk_count: int


async def probe_once(
    provider: Provider, model: str, *, prompt: str, clock: Clock
) -> ProbeSample:
    """Run a single probe against ``model`` and measure ttft/total/chunks."""
    start = clock.now()
    ttft_seconds: float | None = None
    chunk_count = 0
    finish_at = start
    async for chunk in provider.chat(model, [ChatMessage(role="user", content=prompt)]):
        now = clock.now()
        if ttft_seconds is None:
            ttft_seconds = (now - start).total_seconds()
        if chunk.delta:
            chunk_count += 1
        finish_at = now
    total_seconds = (finish_at - start).total_seconds()
    return ProbeSample(
        ttft_seconds=ttft_seconds if ttft_seconds is not None else total_seconds,
        total_seconds=total_seconds,
        chunk_count=chunk_count,
    )


async def probe_median(
    provider: Provider,
    model: str,
    *,
    clock: Clock,
    prompt: str = DEFAULT_PROBE_PROMPT,
    k: int = DEFAULT_K,
) -> ProbeSample:
    """Probe ``model`` ``k`` times and return the median sample (doc 50 §4)."""
    if k < 1:
        raise ValueError("k must be at least 1")
    samples = [
        await probe_once(provider, model, prompt=prompt, clock=clock) for _ in range(k)
    ]
    return ProbeSample(
        ttft_seconds=statistics.median(s.ttft_seconds for s in samples),
        total_seconds=statistics.median(s.total_seconds for s in samples),
        chunk_count=round(statistics.median(s.chunk_count for s in samples)),
    )
