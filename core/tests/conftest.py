"""Shared test fixtures.

A deterministic clock so log-timestamp assertions are stable (mirrors the
injectable-time discipline of the production code, doc 39 §6).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest


class FixedClock:
    """A deterministic :class:`~turkish_code.ortak.saat.Clock` for tests."""

    def __init__(self, moment: datetime) -> None:
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


@pytest.fixture
def fixed_moment() -> datetime:
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def fixed_clock(fixed_moment: datetime) -> FixedClock:
    return FixedClock(fixed_moment)
