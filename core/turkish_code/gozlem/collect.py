"""Metric emission (doc 51 §5/§7).

Emission is best-effort and never blocks/fails a real call (doc 51 §9):
recording failures — including hitting the per-metric cardinality cap
(doc 51 §8) — degrade silently rather than raising. Dimension values are
passed through the same redactor as logging (doc 39 §8) so a secret can
never reach a metric even if one is accidentally passed as a dimension
(doc 51 §4/§8, defense in depth).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from turkish_code.gozlem.catalog import MetricKind, MetricName, kind_of
from turkish_code.gozlem.rollup import CounterSnapshot, GaugeSnapshot, HistogramSnapshot
from turkish_code.gunluk.redaksiyon import FieldNameRedactor, Redactor

MAX_DIM_COMBINATIONS_PER_METRIC = 200
"""Caps unbounded cardinality growth per metric name (doc 51 §8, PR-14)."""

DimKey = tuple[tuple[str, str], ...]


@runtime_checkable
class MetricsCollector(Protocol):
    """Emits metrics from the catalog at their code points (doc 51 §5)."""

    def increment(
        self, name: MetricName, *, by: int = 1, dims: Mapping[str, str] | None = None
    ) -> None:
        """Add ``by`` to a counter metric."""
        ...

    def set_gauge(
        self, name: MetricName, value: float, *, dims: Mapping[str, str] | None = None
    ) -> None:
        """Set a gauge metric to ``value``."""
        ...

    def observe(
        self, name: MetricName, value: float, *, dims: Mapping[str, str] | None = None
    ) -> None:
        """Record one observation into a histogram metric."""
        ...


class InMemoryMetricsCollector:
    """Process-lifetime :class:`MetricsCollector` (doc 51 §5) — no export."""

    def __init__(self, *, redactor: Redactor | None = None) -> None:
        self._redactor = redactor or FieldNameRedactor()
        self._counters: dict[MetricName, dict[DimKey, int]] = {}
        self._gauges: dict[MetricName, dict[DimKey, float]] = {}
        self._histograms: dict[MetricName, dict[DimKey, list[float]]] = {}

    def increment(
        self, name: MetricName, *, by: int = 1, dims: Mapping[str, str] | None = None
    ) -> None:
        self._require_kind(name, MetricKind.COUNTER)
        key = self._dim_key(name, dims)
        if key is None:
            return
        table = self._counters.setdefault(name, {})
        table[key] = table.get(key, 0) + by

    def set_gauge(
        self, name: MetricName, value: float, *, dims: Mapping[str, str] | None = None
    ) -> None:
        self._require_kind(name, MetricKind.GAUGE)
        key = self._dim_key(name, dims)
        if key is None:
            return
        self._gauges.setdefault(name, {})[key] = value

    def observe(
        self, name: MetricName, value: float, *, dims: Mapping[str, str] | None = None
    ) -> None:
        self._require_kind(name, MetricKind.HISTOGRAM)
        key = self._dim_key(name, dims)
        if key is None:
            return
        self._histograms.setdefault(name, {}).setdefault(key, []).append(value)

    def counters(self) -> list[CounterSnapshot]:
        return [
            CounterSnapshot(name=name, dims=dict(key), value=value)
            for name, table in self._counters.items()
            for key, value in table.items()
        ]

    def gauges(self) -> list[GaugeSnapshot]:
        return [
            GaugeSnapshot(name=name, dims=dict(key), value=value)
            for name, table in self._gauges.items()
            for key, value in table.items()
        ]

    def histograms(self) -> list[HistogramSnapshot]:
        return [
            HistogramSnapshot(
                name=name,
                dims=dict(key),
                count=len(values),
                total=sum(values),
                minimum=min(values),
                maximum=max(values),
            )
            for name, table in self._histograms.items()
            for key, values in table.items()
        ]

    def _dim_key(
        self, name: MetricName, dims: Mapping[str, str] | None
    ) -> DimKey | None:
        safe_dims = self._redactor.redact(dims or {})
        key: DimKey = tuple(sorted((k, str(v)) for k, v in safe_dims.items()))
        existing = self._known_keys(name)
        if key not in existing and len(existing) >= MAX_DIM_COMBINATIONS_PER_METRIC:
            return None  # cardinality cap hit — drop silently (doc 51 §8/§9)
        return key

    def _known_keys(self, name: MetricName) -> set[DimKey]:
        return (
            set(self._counters.get(name, {}))
            | set(self._gauges.get(name, {}))
            | set(self._histograms.get(name, {}))
        )

    @staticmethod
    def _require_kind(name: MetricName, expected: MetricKind) -> None:
        if kind_of(name) is not expected:
            raise ValueError(f"{name} is a {kind_of(name)} metric, not {expected}")
