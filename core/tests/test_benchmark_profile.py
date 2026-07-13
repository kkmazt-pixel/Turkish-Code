"""Tests for performance-profile latency classification (doc 50 §6)."""

from __future__ import annotations

from turkish_code.yonlendirme.benchmark.profile import classify_latency
from turkish_code.yonlendirme.capability import LatencyClass


def test_fast_below_threshold() -> None:
    assert classify_latency(0.2) is LatencyClass.FAST


def test_fast_at_threshold_boundary() -> None:
    assert classify_latency(0.5) is LatencyClass.FAST


def test_normal_between_thresholds() -> None:
    assert classify_latency(1.0) is LatencyClass.NORMAL


def test_slow_above_normal_threshold() -> None:
    assert classify_latency(5.0) is LatencyClass.SLOW


def test_custom_thresholds_are_honored() -> None:
    assert (
        classify_latency(0.3, fast_threshold=0.1, normal_threshold=0.4)
        is LatencyClass.NORMAL
    )
