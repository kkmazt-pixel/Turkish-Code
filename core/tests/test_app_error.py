"""Unit tests for the typed-error subsystem (doc 38 §17).

These assert the guarantees other subsystems will rely on: a failure is a typed
value with ``kind``/``retryable``/``remedy`` (PR-10), and log-only fields
(``detail``, ``cause``) never reach the user-facing surface payload (doc 38 §6).
"""

from __future__ import annotations

import json

import pytest
from turkish_code.hata import AppError, ErrorKind


def _timeout_error(**overrides: object) -> AppError:
    """A representative retryable Provider/Timeout error (doc 38 §19)."""
    kwargs: dict[str, object] = {
        "kind": ErrorKind.TIMEOUT,
        "code": "provider.timeout",
        "message_key": "hata.provider.timeout",
        "retryable": True,
        "remedy_key": "caba.hizli_dene",
    }
    kwargs.update(overrides)
    return AppError(**kwargs)  # type: ignore[arg-type]


def test_is_raisable_typed_value() -> None:
    """An AppError bubbles as a typed exception value (doc 38 §7)."""
    with pytest.raises(AppError) as excinfo:
        raise _timeout_error()

    err = excinfo.value
    assert isinstance(err, Exception)
    assert err.kind is ErrorKind.TIMEOUT
    assert err.retryable is True


def test_surface_payload_shape() -> None:
    """to_error_data() carries exactly the caller-actionable fields (doc 38 §6)."""
    data = _timeout_error().to_error_data()

    assert data == {
        "kind": "Timeout",
        "code": "provider.timeout",
        "messageKey": "hata.provider.timeout",
        "retryable": True,
        "remedy": "caba.hizli_dene",
    }


def test_surface_payload_excludes_detail_and_cause() -> None:
    """Log-only fields never reach the user surface (doc 38 §5/§6)."""
    root = AppError(
        kind=ErrorKind.PROVIDER,
        code="provider.upstream_500",
        message_key="hata.provider.upstream",
        retryable=True,
        detail="upstream returned HTTP 500 from api.example.com",
    )
    err = _timeout_error(detail="socket read timed out after 30s", cause=root)

    data = err.to_error_data()

    assert "detail" not in data
    assert "cause" not in data
    # The detail strings (which may carry internals) must not leak anywhere.
    serialized = json.dumps(data)
    assert "socket read" not in serialized
    assert "upstream returned" not in serialized


def test_kind_serializes_to_stable_wire_value() -> None:
    """ErrorKind members serialize to their contract string (doc 10 §14)."""
    assert json.dumps(ErrorKind.SECURITY) == '"Security"'
    assert ErrorKind("Budget") is ErrorKind.BUDGET


def test_optional_fields_are_omitted_when_absent() -> None:
    """remedy/context appear only when set — no null noise on the wire."""
    data = AppError(
        kind=ErrorKind.VALIDATION,
        code="tool.args.invalid",
        message_key="hata.tool.args",
        retryable=False,
    ).to_error_data()

    assert "remedy" not in data
    assert "context" not in data
    assert data["retryable"] is False


def test_context_is_immutable_snapshot() -> None:
    """Context is defensively copied so the error stays an immutable value."""
    mutable = {"path": "/a/b", "attempt": 1}
    err = AppError(
        kind=ErrorKind.NOT_FOUND,
        code="fs.not_found",
        message_key="hata.fs.not_found",
        retryable=False,
        context=mutable,
    )

    mutable["attempt"] = 999  # mutate the caller's dict after construction
    assert err.context is not None
    assert err.context["attempt"] == 1  # snapshot is unaffected
    with pytest.raises(TypeError):
        err.context["attempt"] = 2  # type: ignore[index]


def test_cause_chain_is_ordered_nearest_first() -> None:
    """causes() walks the chain for logging (doc 38 §6)."""
    deepest = _timeout_error(code="a")
    middle = _timeout_error(code="b", cause=deepest)
    top = _timeout_error(code="c", cause=middle)

    assert [c.code for c in top.causes()] == ["b", "a"]
    assert deepest.causes() == []


def test_empty_code_or_message_key_is_rejected() -> None:
    """A stable code and an i18n key are required (doc 38 §5)."""
    with pytest.raises(ValueError):
        AppError(kind=ErrorKind.INTERNAL, code="", message_key="k", retryable=False)
    with pytest.raises(ValueError):
        AppError(kind=ErrorKind.INTERNAL, code="c", message_key="", retryable=False)
