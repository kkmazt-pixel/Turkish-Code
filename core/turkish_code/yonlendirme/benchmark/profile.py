"""Performance profiles (doc 50 §6) — the digestible output scoring/UI consume.

Buckets a raw median-of-K latency measurement into the capability taxonomy's
:class:`~turkish_code.yonlendirme.capability.taxonomy.LatencyClass` (doc 46
§4), so benchmark evidence and declared capabilities share one vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from turkish_code.yonlendirme.benchmark.quality import QualitySignal
from turkish_code.yonlendirme.capability.taxonomy import LatencyClass

FAST_TTFT_SECONDS = 0.5
"""At/below this median ttft, a model is classified fast (doc 50 §6, OPEN-tunable)."""

NORMAL_TTFT_SECONDS = 2.0
"""At or below this median ttft (and above fast), a model is classified normal."""


@dataclass(frozen=True, slots=True)
class PerformanceProfile:
    """A model/provider's digestible latency + quality summary (doc 50 §6)."""

    latency_class: LatencyClass
    typical_tps: float
    quality: QualitySignal
    measured_at: datetime


def classify_latency(
    median_ttft_seconds: float,
    *,
    fast_threshold: float = FAST_TTFT_SECONDS,
    normal_threshold: float = NORMAL_TTFT_SECONDS,
) -> LatencyClass:
    """Bucket a median ttft into fast/normal/slow (doc 50 §6)."""
    if median_ttft_seconds <= fast_threshold:
        return LatencyClass.FAST
    if median_ttft_seconds <= normal_threshold:
        return LatencyClass.NORMAL
    return LatencyClass.SLOW
