"""Tests for the agent session lifecycle (doc 18 §9/§14)."""

from __future__ import annotations

import pytest
from turkish_code.ajanlar.durum import RunState
from turkish_code.ajanlar.modeller import SessionState
from turkish_code.ajanlar.yasam import (
    AGENT_INVALID_TRANSITION_CODE,
    AGENT_SESSION_DUPLICATE_CODE,
    AGENT_SESSION_NOT_FOUND_CODE,
    SessionLifecycle,
)
from turkish_code.hata import AppError, ErrorKind


def _started() -> tuple[SessionLifecycle, str]:
    lifecycle = SessionLifecycle()
    lifecycle.create("s1", "yonetici")
    lifecycle.start("s1")
    return lifecycle, "s1"


def test_create_makes_a_created_session() -> None:
    lifecycle = SessionLifecycle()
    session = lifecycle.create("s1", "yonetici")
    assert session.state is SessionState.CREATED
    assert "s1" in lifecycle and len(lifecycle) == 1


def test_duplicate_session_is_rejected() -> None:
    lifecycle = SessionLifecycle()
    lifecycle.create("s1", "a")
    with pytest.raises(AppError) as exc_info:
        lifecycle.create("s1", "a")
    assert exc_info.value.code == AGENT_SESSION_DUPLICATE_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_resolve_missing_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        SessionLifecycle().resolve("absent")
    assert exc_info.value.code == AGENT_SESSION_NOT_FOUND_CODE
    assert exc_info.value.kind is ErrorKind.NOT_FOUND


def test_get_returns_none_for_missing() -> None:
    assert SessionLifecycle().get("absent") is None


def test_start_transitions_created_to_running() -> None:
    lifecycle = SessionLifecycle()
    lifecycle.create("s1", "a")
    lifecycle.start("s1")
    assert lifecycle.resolve("s1").state is SessionState.RUNNING


def test_suspend_and_resume_round_trip() -> None:
    lifecycle, sid = _started()
    lifecycle.suspend(sid)
    assert lifecycle.resolve(sid).state is SessionState.SUSPENDED
    lifecycle.resume(sid)
    assert lifecycle.resolve(sid).state is SessionState.RUNNING


def test_stop_cancels_active_runs() -> None:
    lifecycle, sid = _started()
    session = lifecycle.resolve(sid)
    session.open_run("r1", "m")  # active run in flight
    lifecycle.stop(sid)
    assert session.state is SessionState.STOPPED
    assert session.run("r1").state is RunState.CANCELLED


def test_stopped_session_can_restart() -> None:
    lifecycle, sid = _started()
    lifecycle.stop(sid)
    lifecycle.start(sid)  # STOPPED → RUNNING
    assert lifecycle.resolve(sid).state is SessionState.RUNNING


def test_shutdown_is_terminal_and_cancels_runs() -> None:
    lifecycle, sid = _started()
    session = lifecycle.resolve(sid)
    session.open_run("r1", "m")
    lifecycle.shutdown(sid)
    assert session.state is SessionState.SHUTDOWN
    assert session.run("r1").state is RunState.CANCELLED


def test_shutdown_is_idempotent() -> None:
    lifecycle, sid = _started()
    lifecycle.shutdown(sid)
    lifecycle.shutdown(sid)  # no raise
    assert lifecycle.resolve(sid).state is SessionState.SHUTDOWN


@pytest.mark.parametrize(
    "operation",
    ["suspend", "resume", "stop"],
)
def test_illegal_transition_from_created_is_rejected(operation: str) -> None:
    lifecycle = SessionLifecycle()
    lifecycle.create("s1", "a")  # CREATED: cannot suspend/resume/stop
    with pytest.raises(AppError) as exc_info:
        getattr(lifecycle, operation)("s1")
    assert exc_info.value.code == AGENT_INVALID_TRANSITION_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_start_from_running_is_illegal() -> None:
    lifecycle, sid = _started()
    with pytest.raises(AppError) as exc_info:
        lifecycle.start(sid)
    assert exc_info.value.code == AGENT_INVALID_TRANSITION_CODE


def test_resume_from_running_is_illegal() -> None:
    lifecycle, sid = _started()
    with pytest.raises(AppError) as exc_info:
        lifecycle.resume(sid)
    assert exc_info.value.code == AGENT_INVALID_TRANSITION_CODE


def test_operations_after_shutdown_are_illegal() -> None:
    lifecycle, sid = _started()
    lifecycle.shutdown(sid)
    for operation in ("start", "suspend", "resume", "stop"):
        with pytest.raises(AppError):
            getattr(lifecycle, operation)(sid)


def test_full_lifecycle_flow() -> None:
    lifecycle = SessionLifecycle()
    lifecycle.create("s1", "a")
    lifecycle.start("s1")
    lifecycle.suspend("s1")
    lifecycle.resume("s1")
    lifecycle.stop("s1")
    lifecycle.shutdown("s1")
    assert lifecycle.resolve("s1").state is SessionState.SHUTDOWN
    assert lifecycle.session_ids() == ["s1"]
