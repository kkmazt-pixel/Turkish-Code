"""Tests for the shared kernel: Clock and LogLevel."""

from __future__ import annotations

from datetime import UTC

import pytest
from turkish_code.ortak.saat import Clock, SystemClock
from turkish_code.ortak.seviye import LogLevel


def test_system_clock_returns_aware_utc() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == UTC.utcoffset(None)


def test_system_clock_satisfies_clock_protocol() -> None:
    assert isinstance(SystemClock(), Clock)


def test_log_levels_are_ordered() -> None:
    assert (
        LogLevel.TRACE < LogLevel.DEBUG < LogLevel.INFO < LogLevel.WARN < LogLevel.ERROR
    )


def test_from_name_is_case_insensitive() -> None:
    assert LogLevel.from_name("info") is LogLevel.INFO
    assert LogLevel.from_name("  Warn ") is LogLevel.WARN


def test_from_name_rejects_unknown() -> None:
    with pytest.raises(ValueError):
        LogLevel.from_name("chatty")
