"""Tests for JSON-RPC frame validation (doc 10 §17)."""

from __future__ import annotations

import json

import pytest
from turkish_code.hata import AppError
from turkish_code.kanal.dogrulama import MALFORMED_FRAME_CODE, parse_frame
from turkish_code.kanal.mesaj import (
    ErrorResponse,
    Notification,
    Request,
    SuccessResponse,
)


def _frame(obj: object) -> bytes:
    return json.dumps(obj).encode("utf-8")


def test_parses_a_request() -> None:
    parsed = parse_frame(
        _frame({"jsonrpc": "2.0", "id": 1, "method": "app.ping", "params": {"a": 1}})
    )
    assert isinstance(parsed, Request)
    assert parsed.id == 1
    assert parsed.method == "app.ping"
    assert parsed.params == {"a": 1}


def test_parses_a_request_with_meta() -> None:
    parsed = parse_frame(
        _frame({"jsonrpc": "2.0", "id": 1, "method": "x", "meta": {"deadlineMs": 100}})
    )
    assert isinstance(parsed, Request)
    assert parsed.deadline_ms == 100.0


def test_parses_a_notification() -> None:
    parsed = parse_frame(_frame({"jsonrpc": "2.0", "method": "run.step"}))
    assert isinstance(parsed, Notification)
    assert parsed.method == "run.step"


def test_parses_a_success_response() -> None:
    parsed = parse_frame(_frame({"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}))
    assert isinstance(parsed, SuccessResponse)
    assert parsed.result == {"ok": True}


def test_parses_an_error_response() -> None:
    parsed = parse_frame(
        _frame(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "error": {
                    "code": -32050,
                    "message": "timeout",
                    "data": {"kind": "Timeout"},
                },
            }
        )
    )
    assert isinstance(parsed, ErrorResponse)
    assert parsed.error.code == -32050
    assert parsed.error.data == {"kind": "Timeout"}


def test_invalid_utf8_is_a_typed_validation_error() -> None:
    with pytest.raises(AppError) as excinfo:
        parse_frame(b"\xff\xfe\xfd")
    assert excinfo.value.code == MALFORMED_FRAME_CODE
    assert excinfo.value.retryable is False


def test_invalid_json_is_a_typed_validation_error() -> None:
    with pytest.raises(AppError) as excinfo:
        parse_frame(b"{not json")
    assert excinfo.value.code == MALFORMED_FRAME_CODE


def test_non_object_json_is_rejected() -> None:
    with pytest.raises(AppError):
        parse_frame(_frame([1, 2, 3]))


def test_wrong_jsonrpc_version_is_rejected() -> None:
    with pytest.raises(AppError):
        parse_frame(_frame({"jsonrpc": "1.0", "method": "x"}))


def test_method_must_be_a_string() -> None:
    with pytest.raises(AppError):
        parse_frame(_frame({"jsonrpc": "2.0", "method": 42}))


def test_unrecognized_shape_is_rejected() -> None:
    with pytest.raises(AppError):
        parse_frame(_frame({"jsonrpc": "2.0", "foo": "bar"}))


def test_malformed_error_object_is_rejected() -> None:
    bad = {"jsonrpc": "2.0", "id": 1, "error": {"message": "no code"}}
    with pytest.raises(AppError):
        parse_frame(_frame(bad))
