"""Composition root — the one place that wires concrete implementations (doc 09 §7).

Everything else depends on interfaces; only this module knows the concrete
classes, constructing the object graph by explicit constructor injection. There
are no module-level singletons and no import-time side effects (PR-9): building a
container is an ordinary function call that returns a fresh graph.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO

from turkish_code.gunluk.kayitci import Logger, StructuredLogger
from turkish_code.gunluk.redaksiyon import FieldNameRedactor
from turkish_code.ortak.saat import Clock, SystemClock
from turkish_code.yapilandirma.ayarlar import Settings


@dataclass(frozen=True, slots=True)
class Container:
    """The wired Çekirdek services (doc 09 §7).

    Holds fully-constructed dependencies to be passed explicitly to subsystems.
    Extended additively as subsystems come online (YAGNI: only what exists today).
    """

    settings: Settings
    clock: Clock
    logger: Logger


def build_container(
    settings: Settings,
    *,
    clock: Clock | None = None,
    log_stream: TextIO | None = None,
) -> Container:
    """Construct the object graph for ``settings`` (doc 09 §7).

    ``clock`` and ``log_stream`` are injectable to make the graph testable;
    production defaults are the real :class:`SystemClock` and ``stderr`` (stdout
    is reserved for IPC, doc 09 §16).
    """
    resolved_clock: Clock = clock if clock is not None else SystemClock()
    stream: TextIO = log_stream if log_stream is not None else sys.stderr
    logger = StructuredLogger(
        stream=stream,
        clock=resolved_clock,
        min_level=settings.log_level,
        redactor=FieldNameRedactor(),
    )
    return Container(settings=settings, clock=resolved_clock, logger=logger)
