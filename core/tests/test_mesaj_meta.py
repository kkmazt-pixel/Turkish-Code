"""Tests for the Request ``meta`` envelope + deadline extraction (doc 10 §6.2)."""

from __future__ import annotations

from turkish_code.kanal.mesaj import PROTOCOL_VERSION, Request


def test_meta_is_omitted_when_absent() -> None:
    wire = Request(id=1, method="app.ping").to_wire()
    assert "meta" not in wire


def test_meta_is_serialized_when_present() -> None:
    wire = Request(id=1, method="session.send", meta={"sessionId": "s1"}).to_wire()
    assert wire["meta"] == {"sessionId": "s1"}


def test_deadline_ms_is_none_without_meta() -> None:
    assert Request(id=1, method="app.ping").deadline_ms is None


def test_deadline_ms_is_none_when_meta_lacks_it() -> None:
    request = Request(id=1, method="app.ping", meta={"sessionId": "s1"})
    assert request.deadline_ms is None


def test_deadline_ms_reads_numeric_meta_field() -> None:
    request = Request(id=1, method="app.ping", meta={"deadlineMs": 5000})
    assert request.deadline_ms == 5000.0


def test_deadline_ms_ignores_non_numeric_value() -> None:
    request = Request(id=1, method="app.ping", meta={"deadlineMs": "soon"})
    assert request.deadline_ms is None


def test_protocol_version_is_a_semver_string() -> None:
    assert PROTOCOL_VERSION.count(".") == 2
