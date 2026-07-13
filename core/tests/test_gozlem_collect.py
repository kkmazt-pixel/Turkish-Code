"""Tests for the in-memory metrics collector (doc 51 §5/§8/§9)."""

from __future__ import annotations

import pytest
from turkish_code.gozlem.catalog import MetricName
from turkish_code.gozlem.collect import (
    MAX_DIM_COMBINATIONS_PER_METRIC,
    InMemoryMetricsCollector,
)


def test_increment_accumulates_by_dims() -> None:
    collector = InMemoryMetricsCollector()
    collector.increment(MetricName.ROUTE_REQUESTS, dims={"mode": "balanced"})
    collector.increment(MetricName.ROUTE_REQUESTS, dims={"mode": "balanced"})
    collector.increment(MetricName.ROUTE_REQUESTS, dims={"mode": "economy"})

    counters = {c.dims["mode"]: c.value for c in collector.counters()}
    assert counters == {"balanced": 2, "economy": 1}


def test_set_gauge_overwrites() -> None:
    collector = InMemoryMetricsCollector()
    collector.set_gauge(MetricName.QUOTA_HEADROOM, 0.9, dims={"provider": "groq"})
    collector.set_gauge(MetricName.QUOTA_HEADROOM, 0.5, dims={"provider": "groq"})

    gauges = collector.gauges()
    assert len(gauges) == 1
    assert gauges[0].value == 0.5


def test_observe_computes_histogram_stats() -> None:
    collector = InMemoryMetricsCollector()
    for value in (1.0, 2.0, 3.0):
        collector.observe(MetricName.PROVIDER_LATENCY, value, dims={"provider": "groq"})

    histogram = collector.histograms()[0]
    assert histogram.count == 3
    assert histogram.total == 6.0
    assert histogram.minimum == 1.0
    assert histogram.maximum == 3.0
    assert histogram.mean == 2.0


def test_wrong_method_for_metric_kind_raises() -> None:
    collector = InMemoryMetricsCollector()
    with pytest.raises(ValueError):
        collector.increment(MetricName.QUOTA_HEADROOM)  # a gauge, not a counter


def test_secret_looking_dimension_value_is_redacted() -> None:
    collector = InMemoryMetricsCollector()
    collector.increment(
        MetricName.ROUTE_REQUESTS, dims={"api_key": "sk-ABCDEF0123456789LEAK"}
    )
    counters = collector.counters()
    assert counters[0].dims["api_key"] == "***"


def test_cardinality_is_capped() -> None:
    collector = InMemoryMetricsCollector()
    for i in range(MAX_DIM_COMBINATIONS_PER_METRIC + 10):
        collector.increment(MetricName.ROUTE_REQUESTS, dims={"model": f"m{i}"})

    assert len(collector.counters()) == MAX_DIM_COMBINATIONS_PER_METRIC


def test_missing_dims_defaults_to_empty() -> None:
    collector = InMemoryMetricsCollector()
    collector.increment(MetricName.ROUTE_UNROUTABLE)
    assert collector.counters()[0].dims == {}
