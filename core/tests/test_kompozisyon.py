"""Tests for the composition root / DI wiring (doc 09 §7)."""

from __future__ import annotations

import io
import json

from turkish_code.kompozisyon import build_container
from turkish_code.ortak.saat import Clock
from turkish_code.ortak.seviye import LogLevel
from turkish_code.yapilandirma.ayarlar import Settings
from turkish_code.yapilandirma.sabitler import ENV_LOG_LEVEL
from turkish_code.yapilandirma.yukleyici import load_settings


def _settings(level: LogLevel = LogLevel.INFO) -> Settings:
    return load_settings({ENV_LOG_LEVEL: level.name})


def test_container_wires_a_working_logger(fixed_clock: Clock) -> None:
    stream = io.StringIO()
    container = build_container(_settings(), clock=fixed_clock, log_stream=stream)

    assert container.clock is fixed_clock
    assert container.settings.locale == "tr"

    container.logger.info("boot", "ready")
    record = json.loads(stream.getvalue().splitlines()[0])
    assert record["tier"] == "core"
    assert record["msg"] == "ready"


def test_logger_honours_configured_level(fixed_clock: Clock) -> None:
    stream = io.StringIO()
    container = build_container(
        _settings(LogLevel.ERROR), clock=fixed_clock, log_stream=stream
    )
    container.logger.info("mod", "below threshold")
    assert stream.getvalue() == ""


def test_build_container_has_no_shared_state(fixed_clock: Clock) -> None:
    """Each call returns a fresh graph — no singletons/global state (PR-9)."""
    a = build_container(_settings(), clock=fixed_clock, log_stream=io.StringIO())
    b = build_container(_settings(), clock=fixed_clock, log_stream=io.StringIO())
    assert a is not b
    assert a.logger is not b.logger
