"""Shared kernel for the Çekirdek (doc 09 §10).

Cross-cutting value types with no internal dependencies — the leaf every other
subsystem may depend on. Currently: the injectable ``Clock`` (``saat``), the
``LogLevel`` (``seviye``) vocabulary, and the ``RunId``/``EventId``/
``ProvenanceRef`` Timeline-reference types (``kimlik``).
"""

from turkish_code.ortak.kimlik import EventId, ProvenanceRef, RunId
from turkish_code.ortak.saat import Clock, SystemClock
from turkish_code.ortak.seviye import LogLevel

__all__ = [
    "Clock",
    "SystemClock",
    "LogLevel",
    "RunId",
    "EventId",
    "ProvenanceRef",
]
