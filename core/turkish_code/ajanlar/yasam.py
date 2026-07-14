"""Agent session lifecycle (doc 18 §9) — create + drive session state.

:class:`SessionLifecycle` owns the session store and the validated
:class:`SessionState` transitions: create → start ⇄ (suspend/resume) → stop →
shutdown. Illegal transitions are rejected (fail-safe, doc 18 §9); stopping or
shutting a session down cancels its in-flight runs (doc 18 §14). It manages
session *state*, not agent execution — running is the dispatcher's job (Inc 5).
"""

from __future__ import annotations

from collections.abc import Iterable

from turkish_code.ajanlar.modeller import SessionState
from turkish_code.ajanlar.oturum import AgentSession
from turkish_code.hata import AppError, ErrorKind

AGENT_SESSION_NOT_FOUND_CODE = "agent.session_not_found"
AGENT_SESSION_DUPLICATE_CODE = "agent.session_duplicate"
AGENT_INVALID_TRANSITION_CODE = "agent.invalid_transition"


class SessionLifecycle:
    """Creates sessions and drives their lifecycle state (doc 18 §9)."""

    def __init__(self) -> None:
        self._sessions: dict[str, AgentSession] = {}

    def create(self, session_id: str, agent_id: str) -> AgentSession:
        """Create a fresh CREATED session; reject a duplicate id (doc 18 §9)."""
        if session_id in self._sessions:
            raise _duplicate(session_id)
        session = AgentSession(session_id=session_id, agent_id=agent_id)
        self._sessions[session_id] = session
        return session

    def start(self, session_id: str) -> None:
        """Start (or restart) a session: CREATED/STOPPED → RUNNING (doc 18 §9)."""
        session = self.resolve(session_id)
        self._require(session, (SessionState.CREATED, SessionState.STOPPED))
        session.set_state(SessionState.RUNNING)

    def suspend(self, session_id: str) -> None:
        """Pause a running session: RUNNING → SUSPENDED (doc 18 §9)."""
        session = self.resolve(session_id)
        self._require(session, (SessionState.RUNNING,))
        session.set_state(SessionState.SUSPENDED)

    def resume(self, session_id: str) -> None:
        """Resume a suspended session: SUSPENDED → RUNNING (doc 18 §9)."""
        session = self.resolve(session_id)
        self._require(session, (SessionState.SUSPENDED,))
        session.set_state(SessionState.RUNNING)

    def stop(self, session_id: str) -> None:
        """Stop a session: RUNNING/SUSPENDED → STOPPED, cancelling runs (doc 18 §14)."""
        session = self.resolve(session_id)
        self._require(session, (SessionState.RUNNING, SessionState.SUSPENDED))
        session.cancel_active_runs()
        session.set_state(SessionState.STOPPED)

    def shutdown(self, session_id: str) -> None:
        """Terminally shut a session down; cancels runs. Idempotent (doc 18 §9)."""
        session = self.resolve(session_id)
        if session.state is SessionState.SHUTDOWN:
            return
        session.cancel_active_runs()
        session.set_state(SessionState.SHUTDOWN)

    def get(self, session_id: str) -> AgentSession | None:
        """The session, or ``None`` if absent."""
        return self._sessions.get(session_id)

    def resolve(self, session_id: str) -> AgentSession:
        """The session, or raise ``agent.session_not_found``."""
        session = self._sessions.get(session_id)
        if session is None:
            raise _not_found(session_id)
        return session

    def __contains__(self, session_id: object) -> bool:
        return isinstance(session_id, str) and session_id in self._sessions

    def __len__(self) -> int:
        return len(self._sessions)

    def session_ids(self) -> list[str]:
        """All session ids, sorted."""
        return sorted(self._sessions)

    def _require(self, session: AgentSession, allowed: Iterable[SessionState]) -> None:
        if session.state not in allowed:
            raise _invalid_transition(session.session_id, session.state)


def _not_found(session_id: str) -> AppError:
    return _err(
        ErrorKind.NOT_FOUND,
        AGENT_SESSION_NOT_FOUND_CODE,
        f"no session {session_id!r}",
    )


def _duplicate(session_id: str) -> AppError:
    return _err(
        ErrorKind.CONFLICT,
        AGENT_SESSION_DUPLICATE_CODE,
        f"a session already exists as {session_id!r}",
    )


def _invalid_transition(session_id: str, state: SessionState) -> AppError:
    return _err(
        ErrorKind.CONFLICT,
        AGENT_INVALID_TRANSITION_CODE,
        f"illegal lifecycle transition for {session_id!r} in state {state.value!r}",
    )


def _err(kind: ErrorKind, code: str, detail: str) -> AppError:
    return AppError(
        kind=kind,
        code=code,
        message_key=f"hata.{code}",
        retryable=False,
        detail=detail,
    )
