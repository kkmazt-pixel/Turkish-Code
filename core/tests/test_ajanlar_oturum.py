"""Tests for the agent session — conversation, run state, resume, cancel (doc 18 §9)."""

from __future__ import annotations

import pytest
from turkish_code.ajanlar.durum import ConversationState, RunRecord, RunState
from turkish_code.ajanlar.modeller import ConversationTurn, SessionState, TurnRole
from turkish_code.ajanlar.oturum import (
    AGENT_RUN_DUPLICATE_CODE,
    AGENT_RUN_NOT_FOUND_CODE,
    AgentSession,
)
from turkish_code.hata import AppError, ErrorKind


def _session() -> AgentSession:
    return AgentSession(session_id="s1", agent_id="yonetici")


# --- run state model ----------------------------------------------------------


def test_run_record_active_and_terminal() -> None:
    pending = RunRecord(run_id="r1", agent_id="a", message="m")
    assert pending.state is RunState.PENDING
    assert pending.is_active
    assert not pending.is_terminal

    for terminal in (RunState.COMPLETED, RunState.CANCELLED, RunState.FAILED):
        record = RunRecord(run_id="r", agent_id="a", message="m", state=terminal)
        assert record.is_terminal
        assert not record.is_active


def test_conversation_state_appends_and_snapshots() -> None:
    conversation = ConversationState("s1")
    conversation.add_turn(ConversationTurn(role=TurnRole.USER, content="hi"))
    assert len(conversation) == 1
    snapshot = conversation.turns()
    conversation.add_turn(ConversationTurn(role=TurnRole.AGENT, content="yo"))
    assert len(snapshot) == 1  # snapshot is immutable
    assert len(conversation) == 2


# --- session identity + conversation -----------------------------------------


def test_session_starts_created() -> None:
    session = _session()
    assert session.state is SessionState.CREATED
    assert session.session_id == "s1" and session.agent_id == "yonetici"


def test_open_run_records_user_turn() -> None:
    session = _session()
    record = session.open_run("r1", "özellik ekle")
    assert record.state is RunState.PENDING
    turns = session.turns()
    assert [(t.role, t.content) for t in turns] == [(TurnRole.USER, "özellik ekle")]


def test_complete_run_records_agent_turn_and_output() -> None:
    session = _session()
    session.open_run("r1", "soru")
    session.start_run("r1")
    session.complete_run("r1", "cevap")
    record = session.run("r1")
    assert record.state is RunState.COMPLETED and record.output == "cevap"
    assert [t.content for t in session.turns()] == ["soru", "cevap"]


def test_conversation_context_reflects_session_turns() -> None:
    session = _session()
    session.open_run("r1", "soru")
    session.complete_run("r1", "cevap")
    ctx = session.conversation_context()
    assert ctx.session_id == "s1"
    assert ctx.turn_count == 2
    assert ctx.last_user_message() == "soru"


# --- run lifecycle edges -----------------------------------------------------


def test_duplicate_run_id_is_rejected() -> None:
    session = _session()
    session.open_run("r1", "m")
    with pytest.raises(AppError) as exc_info:
        session.open_run("r1", "again")
    assert exc_info.value.code == AGENT_RUN_DUPLICATE_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_unknown_run_raises_not_found() -> None:
    with pytest.raises(AppError) as exc_info:
        _session().run("absent")
    assert exc_info.value.code == AGENT_RUN_NOT_FOUND_CODE
    assert exc_info.value.kind is ErrorKind.NOT_FOUND


def test_fail_run_records_error_code() -> None:
    session = _session()
    session.open_run("r1", "m")
    session.fail_run("r1", "tool.timeout")
    record = session.run("r1")
    assert record.state is RunState.FAILED and record.error_code == "tool.timeout"


def test_runs_returns_open_order() -> None:
    session = _session()
    session.open_run("r2", "b")
    session.open_run("r1", "a")
    assert [r.run_id for r in session.runs()] == ["r2", "r1"]


# --- resume ------------------------------------------------------------------


def test_active_runs_are_the_resumable_set() -> None:
    session = _session()
    session.open_run("done", "a")
    session.complete_run("done", "x")
    session.open_run("pending", "b")
    session.open_run("running", "c")
    session.start_run("running")
    assert [r.run_id for r in session.active_runs()] == ["pending", "running"]


# --- cancel ------------------------------------------------------------------


def test_cancel_run_marks_only_active() -> None:
    session = _session()
    session.open_run("r1", "a")
    session.complete_run("r1", "x")
    session.cancel_run("r1")  # already terminal → unchanged
    assert session.run("r1").state is RunState.COMPLETED

    session.open_run("r2", "b")
    session.cancel_run("r2")
    assert session.run("r2").state is RunState.CANCELLED


def test_cancel_active_runs_cancels_all_in_progress() -> None:
    session = _session()
    session.open_run("done", "a")
    session.complete_run("done", "x")
    session.open_run("r1", "b")
    session.open_run("r2", "c")
    session.start_run("r2")
    session.cancel_active_runs()
    states = {r.run_id: r.state for r in session.runs()}
    assert states == {
        "done": RunState.COMPLETED,
        "r1": RunState.CANCELLED,
        "r2": RunState.CANCELLED,
    }


def test_set_state_updates_session_state() -> None:
    session = _session()
    session.set_state(SessionState.RUNNING)
    assert session.state is SessionState.RUNNING
