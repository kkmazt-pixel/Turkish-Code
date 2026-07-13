"""Metrics & observability (doc 51) — Gözlem.

Named, structured measurements of the provider/routing layer's live behavior
(distinct from benchmark *probing*, doc 50). Local-only, secret-free, no
auto-egress (doc 51 §3/§5).
"""

from turkish_code.gozlem.catalog import MetricKind, MetricName
from turkish_code.gozlem.collect import InMemoryMetricsCollector, MetricsCollector
from turkish_code.gozlem.rollup import CounterSnapshot, GaugeSnapshot, HistogramSnapshot

__all__ = [
    "MetricName",
    "MetricKind",
    "MetricsCollector",
    "InMemoryMetricsCollector",
    "CounterSnapshot",
    "GaugeSnapshot",
    "HistogramSnapshot",
]
