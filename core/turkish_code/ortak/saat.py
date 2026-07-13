"""Time source abstraction (doc 39 §6 — the ``ts`` field).

The current time is obtained through an injected :class:`Clock` rather than
calling ``datetime.now()`` directly, so timestamps are deterministic in tests
and no module reaches for hidden global state (PR-9, doc 36 §3).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Provides the current instant. Injected wherever time is needed."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware ``datetime``."""
        ...


class SystemClock:
    """The real wall clock, in UTC.

    UTC keeps log timestamps unambiguous across machines and DST changes
    (doc 39 §6); presentation-layer localization is a separate concern.
    """

    def now(self) -> datetime:
        """Return the current UTC time (timezone-aware)."""
        return datetime.now(UTC)
