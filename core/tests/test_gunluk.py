"""Tests for the structured logger and redaction (doc 39)."""

from __future__ import annotations

import io
import json
import sys
from datetime import datetime
from typing import Any

import pytest
from turkish_code.gunluk.kayitci import StructuredLogger
from turkish_code.gunluk.redaksiyon import FieldNameRedactor
from turkish_code.hata import AppError, ErrorKind
from turkish_code.ortak.saat import Clock
from turkish_code.ortak.seviye import LogLevel


def _logger(
    stream: io.StringIO, clock: Clock, min_level: LogLevel = LogLevel.INFO
) -> StructuredLogger:
    return StructuredLogger(
        stream=stream, clock=clock, min_level=min_level, redactor=FieldNameRedactor()
    )


def _one_record(stream: io.StringIO) -> dict[str, Any]:
    lines = stream.getvalue().splitlines()
    assert len(lines) == 1
    record: dict[str, Any] = json.loads(lines[0])
    return record


def test_emits_structured_json_line(fixed_clock: Clock, fixed_moment: datetime) -> None:
    stream = io.StringIO()
    _logger(stream, fixed_clock).info("boot", "starting")
    record = _one_record(stream)
    assert record == {
        "ts": fixed_moment.isoformat(),
        "level": "INFO",
        "tier": "core",
        "module": "boot",
        "msg": "starting",
    }


def test_drops_records_below_min_level(fixed_clock: Clock) -> None:
    stream = io.StringIO()
    logger = _logger(stream, fixed_clock, min_level=LogLevel.WARN)
    logger.info("mod", "ignored")
    logger.debug("mod", "ignored too")
    assert stream.getvalue() == ""


def test_error_record_includes_kind_and_code(fixed_clock: Clock) -> None:
    stream = io.StringIO()
    err = AppError(
        kind=ErrorKind.PROVIDER,
        code="provider.timeout",
        message_key="hata.provider.timeout",
        retryable=True,
    )
    _logger(stream, fixed_clock).error("router", "call failed", error=err)
    record = _one_record(stream)
    assert record["level"] == "ERROR"
    assert record["errKind"] == "Provider"
    assert record["code"] == "provider.timeout"


def test_sensitive_fields_are_redacted(fixed_clock: Clock) -> None:
    stream = io.StringIO()
    _logger(stream, fixed_clock).info(
        "auth", "configured", api_key="sk-secret-123", provider="groq"
    )
    record = _one_record(stream)
    assert record["api_key"] == "***"
    assert record["provider"] == "groq"
    assert "sk-secret-123" not in stream.getvalue()


def test_construction_rejects_stdout(fixed_clock: Clock) -> None:
    with pytest.raises(ValueError):
        _logger(sys.stdout, fixed_clock)  # type: ignore[arg-type]


def test_field_name_redactor_masks_only_sensitive_names() -> None:
    result = FieldNameRedactor().redact(
        {"password": "p", "authorization": "Bearer x", "count": 3, "path": "/tmp"}
    )
    assert result == {
        "password": "***",
        "authorization": "***",
        "count": 3,
        "path": "/tmp",
    }


def test_secret_shaped_value_in_innocent_field_is_scrubbed(fixed_clock: Clock) -> None:
    """A1: secrets masked by value pattern even when the field name is innocent."""
    stream = io.StringIO()
    _logger(stream, fixed_clock).info(
        "cfg", "loaded", note="using sk-ABCDEF0123456789TOKEN for provider"
    )
    record = _one_record(stream)
    assert "sk-ABCDEF0123456789TOKEN" not in stream.getvalue()
    assert "***" in record["note"]


def test_secret_in_msg_is_scrubbed(fixed_clock: Clock) -> None:
    """A1: the msg string is redacted too, not just fields (doc 39 §8)."""
    stream = io.StringIO()
    _logger(stream, fixed_clock).warn("auth", "header was Bearer abc.def.ghi")
    record = _one_record(stream)
    assert "abc.def.ghi" not in stream.getvalue()
    assert "***" in record["msg"]


def test_redact_text_masks_known_shapes_and_keeps_plain_text() -> None:
    redactor = FieldNameRedactor()
    assert redactor.redact_text("plain /tmp path 42") == "plain /tmp path 42"
    assert "AIza" not in redactor.redact_text("key=AIzaSyABCDEF0123456789xyz")


def test_error_detail_is_logged_and_redacted(fixed_clock: Clock) -> None:
    """A2: detail reaches the log (doc 38 §5/§6) but is redacted (doc 39 §8)."""
    stream = io.StringIO()
    err = AppError(
        kind=ErrorKind.PROVIDER,
        code="provider.auth",
        message_key="hata.provider.auth",
        retryable=False,
        detail="rejected token sk-ABCDEF0123456789LEAK at api.example.com",
    )
    _logger(stream, fixed_clock).error("router", "call failed", error=err)
    record = _one_record(stream)
    assert "detail" in record
    assert (
        "api.example.com" in record["detail"]
    )  # non-secret internal kept for diagnostics
    assert "sk-ABCDEF0123456789LEAK" not in stream.getvalue()  # secret scrubbed


def test_error_cause_chain_is_logged(fixed_clock: Clock) -> None:
    """A2: the cause chain is preserved in the log, nearest-first (doc 38 §6)."""
    root = AppError(
        kind=ErrorKind.EGRESS,
        code="egress.offline",
        message_key="hata.egress.offline",
        retryable=False,
    )
    err = AppError(
        kind=ErrorKind.PROVIDER,
        code="provider.unreachable",
        message_key="hata.provider.unreachable",
        retryable=True,
        cause=root,
    )
    stream = io.StringIO()
    _logger(stream, fixed_clock).error("router", "failed", error=err)
    record = _one_record(stream)
    assert record["causes"] == [{"kind": "Egress", "code": "egress.offline"}]


def test_error_without_detail_or_cause_omits_those_keys(fixed_clock: Clock) -> None:
    stream = io.StringIO()
    err = AppError(
        kind=ErrorKind.INTERNAL,
        code="internal.bug",
        message_key="hata.internal",
        retryable=False,
    )
    _logger(stream, fixed_clock).error("mod", "boom", error=err)
    record = _one_record(stream)
    assert "detail" not in record
    assert "causes" not in record
