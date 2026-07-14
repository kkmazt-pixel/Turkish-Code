"""Agent session (doc 18 §9) — a stateful conversation with its runs.

An :class:`AgentSession` is the user-initiated container an agent runs within: it
holds the session's :class:`SessionState`, the append-only conversation, and the
record of every run. It builds the conversation from runs — opening a run records
the user turn, completing it records the agent turn — so the history stays
coherent for **resume** (incomplete runs are still active) and **cancel** (mark a
run, or every active run, cancelled). Session-state transitions are left raw here
(:meth:`set_state`); the lifecycle validates them (Increment 6).
"""

from __future__ import annotations

from turkish_code.ajanlar.baglam import ConversationContext
from turkish_code.ajanlar.durum import ConversationState, RunRecord, RunState
from turkish_code.ajanlar.modeller import ConversationTurn, SessionState, TurnRole
from turkish_code.hata import AppError, ErrorKind

AGENT_RUN_NOT_FOUND_CODE = "agent.run_not_found"
AGENT_RUN_DUPLICATE_CODE = "agent.run_duplicate"


class AgentSession:
    """A stateful agent conversation and its runs (doc 18 §9)."""

    def __init__(self, *, session_id: str, agent_id: str) -> None:
        self._session_id = session_id
        self._agent_id = agent_id
        self._state = SessionState.CREATED
        self._conversation = ConversationState(session_id)
        self._runs: dict[str, RunRecord] = {}
        self._order: list[str] = []

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def state(self) -> SessionState:
        return self._state

    def set_state(self, target: SessionState) -> None:
        """Set the session state (raw). The lifecycle validates transitions."""
        self._state = target

    # --- conversation --------------------------------------------------------

    def turns(self) -> tuple[ConversationTurn, ...]:
        """An immutable snapshot of the conversation so far."""
        return self._conversation.turns()

    def conversation_context(self) -> ConversationContext:
        """A read-only view of the conversation for an agent run (doc 18 §7)."""
        return ConversationContext(
            session_id=self._session_id, turns=self._conversation.turns()
        )

    # --- runs ----------------------------------------------------------------

    def open_run(self, run_id: str, message: str) -> RunRecord:
        """Open a PENDING run for ``message`` and record its user turn (doc 18 §9)."""
        if run_id in self._runs:
            raise _run_duplicate(run_id)
        record = RunRecord(run_id=run_id, agent_id=self._agent_id, message=message)
        self._runs[run_id] = record
        self._order.append(run_id)
        self._conversation.add_turn(
            ConversationTurn(role=TurnRole.USER, content=message)
        )
        return record

    def start_run(self, run_id: str) -> None:
        """Mark a run RUNNING."""
        self._run(run_id).state = RunState.RUNNING

    def complete_run(self, run_id: str, output: str) -> None:
        """Mark a run COMPLETED and record the agent's turn (doc 18 §9)."""
        record = self._run(run_id)
        record.state = RunState.COMPLETED
        record.output = output
        self._conversation.add_turn(
            ConversationTurn(role=TurnRole.AGENT, content=output)
        )

    def fail_run(self, run_id: str, error_code: str) -> None:
        """Mark a run FAILED with its error code."""
        record = self._run(run_id)
        record.state = RunState.FAILED
        record.error_code = error_code

    def cancel_run(self, run_id: str) -> None:
        """Cancel a run if it is still active; a no-op if already terminal."""
        record = self._run(run_id)
        if record.is_active:
            record.state = RunState.CANCELLED

    def run(self, run_id: str) -> RunRecord:
        """The run record for ``run_id``, or raise ``agent.run_not_found``."""
        return self._run(run_id)

    def runs(self) -> list[RunRecord]:
        """Every run record, in the order they were opened."""
        return [self._runs[run_id] for run_id in self._order]

    # --- resume / cancel -----------------------------------------------------

    def active_runs(self) -> list[RunRecord]:
        """Runs still in progress (pending/running) — the resumable set (doc 18 §9)."""
        return [record for record in self.runs() if record.is_active]

    def cancel_active_runs(self) -> None:
        """Cancel every active run — the session-cancel path (doc 18 §14)."""
        for record in self.runs():
            if record.is_active:
                record.state = RunState.CANCELLED

    def _run(self, run_id: str) -> RunRecord:
        record = self._runs.get(run_id)
        if record is None:
            raise _run_not_found(run_id)
        return record


def _run_not_found(run_id: str) -> AppError:
    return _err(
        ErrorKind.NOT_FOUND, AGENT_RUN_NOT_FOUND_CODE, f"no run {run_id!r}", run_id
    )


def _run_duplicate(run_id: str) -> AppError:
    return _err(
        ErrorKind.CONFLICT,
        AGENT_RUN_DUPLICATE_CODE,
        f"a run is already open as {run_id!r}",
        run_id,
    )


def _err(kind: ErrorKind, code: str, detail: str, run_id: str) -> AppError:
    return AppError(
        kind=kind,
        code=code,
        message_key=f"hata.{code}",
        retryable=False,
        detail=detail,
        context={"run": run_id},
    )
