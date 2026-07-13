"""Structured logger for the Çekirdek (doc 39 §6).

Emits one JSON object per line to an injected text stream — stderr in
production, **never** stdout (doc 09 §16, doc 39 §7). Records below the
configured minimum level are dropped. ``msg``, ``fields`` and an error's
``detail`` are passed through the redactor before writing (doc 39 §8); an
error's ``code``/``kind`` and cause chain are recorded for diagnostics
(doc 38 §5/§6).
"""

from __future__ import annotations

import json
import sys
from typing import Any, Protocol, TextIO

from turkish_code.gunluk.redaksiyon import Redactor
from turkish_code.hata import AppError
from turkish_code.ortak.saat import Clock
from turkish_code.ortak.seviye import LogLevel

_TIER = "core"


class Logger(Protocol):
    """The logging interface subsystems depend on (injected, never global)."""

    def log(
        self,
        level: LogLevel,
        module: str,
        msg: str,
        *,
        error: AppError | None = None,
        **fields: Any,
    ) -> None:
        """Emit a record at ``level`` for ``module`` (doc 39 §6)."""
        ...

    def trace(self, module: str, msg: str, **fields: Any) -> None: ...
    def debug(self, module: str, msg: str, **fields: Any) -> None: ...
    def info(self, module: str, msg: str, **fields: Any) -> None: ...
    def warn(self, module: str, msg: str, **fields: Any) -> None: ...
    def error(
        self, module: str, msg: str, *, error: AppError | None = None, **fields: Any
    ) -> None: ...


class StructuredLogger:
    """JSON-line logger writing to an injected stream (doc 39 §6/§7)."""

    def __init__(
        self,
        *,
        stream: TextIO,
        clock: Clock,
        min_level: LogLevel,
        redactor: Redactor,
    ) -> None:
        # Guard the fatal mistake at construction: stdout is the IPC channel.
        if stream is sys.stdout:
            raise ValueError(
                "Çekirdek logs must never be written to stdout (doc 09 §16)"
            )
        self._stream = stream
        self._clock = clock
        self._min_level = min_level
        self._redactor = redactor

    def log(
        self,
        level: LogLevel,
        module: str,
        msg: str,
        *,
        error: AppError | None = None,
        **fields: Any,
    ) -> None:
        """Write a structured record if ``level`` meets the minimum (doc 39 §6)."""
        if level < self._min_level:
            return
        record: dict[str, Any] = {
            "ts": self._clock.now().isoformat(),
            "level": level.name,
            "tier": _TIER,
            "module": module,
            "msg": self._redactor.redact_text(msg),
        }
        if error is not None:
            self._attach_error(record, error)
        if fields:
            record.update(self._redactor.redact(fields))
        self._stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _attach_error(self, record: dict[str, Any], error: AppError) -> None:
        """Record a typed error's diagnostics: kind/code, redacted detail, cause chain.

        ``detail`` and the cause chain are the log-only fields doc 38 §5/§6 says
        belong in the log (not the user surface); ``detail`` is redacted since it
        may carry internals (doc 39 §8).
        """
        record["errKind"] = error.kind.value
        record["code"] = error.code
        if error.detail is not None:
            record["detail"] = self._redactor.redact_text(error.detail)
        causes = error.causes()
        if causes:
            record["causes"] = [
                {"kind": cause.kind.value, "code": cause.code} for cause in causes
            ]

    def trace(self, module: str, msg: str, **fields: Any) -> None:
        self.log(LogLevel.TRACE, module, msg, **fields)

    def debug(self, module: str, msg: str, **fields: Any) -> None:
        self.log(LogLevel.DEBUG, module, msg, **fields)

    def info(self, module: str, msg: str, **fields: Any) -> None:
        self.log(LogLevel.INFO, module, msg, **fields)

    def warn(self, module: str, msg: str, **fields: Any) -> None:
        self.log(LogLevel.WARN, module, msg, **fields)

    def error(
        self, module: str, msg: str, *, error: AppError | None = None, **fields: Any
    ) -> None:
        self.log(LogLevel.ERROR, module, msg, error=error, **fields)
