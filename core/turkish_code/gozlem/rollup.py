"""Aggregated metric snapshots (doc 51 §5/§6) — what consumers read.

Consumed by the provider-status UI (doc 06), scoring's reliability factor
(doc 47 §5), and diagnostics (doc 39). Read-only value types; the
accumulation logic lives in :mod:`~turkish_code.gozlem.collect`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from turkish_code.gozlem.catalog import MetricName


@dataclass(frozen=True, slots=True)
class CounterSnapshot:
    """A counter's accumulated total for one dimension combination (doc 51 §4)."""

    name: MetricName
    dims: Mapping[str, str]
    value: int


@dataclass(frozen=True, slots=True)
class GaugeSnapshot:
    """A gauge's current value for one dimension combination (doc 51 §4)."""

    name: MetricName
    dims: Mapping[str, str]
    value: float


@dataclass(frozen=True, slots=True)
class HistogramSnapshot:
    """A histogram's accumulated observations for one dimension combination."""

    name: MetricName
    dims: Mapping[str, str]
    count: int
    total: float
    minimum: float
    maximum: float

    @property
    def mean(self) -> float:
        """The mean observed value, or ``0.0`` if nothing was observed yet."""
        return self.total / self.count if self.count else 0.0
