"""Log severity levels (doc 39 §5).

A shared vocabulary used by both the logger (``gunluk``) and configuration
(``yapilandirma``); it lives in the shared kernel so neither subsystem depends
on the other.
"""

from __future__ import annotations

from enum import IntEnum


class LogLevel(IntEnum):
    """Ordered log severities: ``TRACE < DEBUG < INFO < WARN < ERROR`` (doc 39 §5).

    The integer ordering is the semantics: a record is emitted when its level
    is ``>=`` the logger's configured minimum. Member names are the wire/display
    spelling. The numeric values mirror the stdlib ``logging`` scheme (with an
    added ``TRACE``) for familiarity, but are not part of any external contract.
    """

    TRACE = 5
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40

    @classmethod
    def from_name(cls, name: str) -> LogLevel:
        """Parse a case-insensitive level name.

        Raises:
            ValueError: if ``name`` is not a known level. Callers that read
                untrusted config catch this and fall back to a default
                (doc 33 §13 — never crash on bad config).
        """
        try:
            return cls[name.strip().upper()]
        except KeyError as exc:
            raise ValueError(f"unknown log level: {name!r}") from exc
