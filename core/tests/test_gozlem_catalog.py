"""Tests for the metric catalog (doc 51 §4)."""

from __future__ import annotations

from turkish_code.gozlem.catalog import MetricKind, MetricName, kind_of


def test_every_metric_name_has_a_kind() -> None:
    for name in MetricName:
        assert kind_of(name) in MetricKind


def test_provider_reliability_is_a_gauge() -> None:
    assert kind_of(MetricName.PROVIDER_RELIABILITY) is MetricKind.GAUGE


def test_route_requests_is_a_counter() -> None:
    assert kind_of(MetricName.ROUTE_REQUESTS) is MetricKind.COUNTER


def test_provider_latency_is_a_histogram() -> None:
    assert kind_of(MetricName.PROVIDER_LATENCY) is MetricKind.HISTOGRAM
