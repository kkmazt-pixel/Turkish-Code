"""Agent run + conversation state (doc 18 §9) — the mutable session interior.

:class:`RunState` is the lifecycle of one agent run/turn; :class:`RunRecord`
tracks that run's identity, inputs, and outcome; :class:`ConversationState` is
the ordered, append-only turn history a session accumulates. These are the
*mutable* containers a session owns (doc 18 §9) — the read-only
:class:`~turkish_code.ajanlar.baglam.ConversationContext` handed to an agent is a
snapshot of them. No behavior beyond bookkeeping.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from turkish_code.ajanlar.modeller import ConversationTurn


class RunState(StrEnum):
    """The lifecycle of a single agent run (doc 18 §9).

    ``PENDING`` (opened, not started) → ``RUNNING`` → one terminal outcome:
    ``COMPLETED``, ``CANCELLED``, or ``FAILED``.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(slots=True)
class RunRecord:
    """The mutable record of one agent run (doc 18 §9).

    Attributes:
        run_id: Unique id of this run.
        agent_id: The agent the run is for.
        message: The user input that opened the run.
        state: The run's current lifecycle state.
        output: The run's result text once completed, else ``None``.
        error_code: The failure code if the run failed, else ``None``.
    """

    run_id: str
    agent_id: str
    message: str
    state: RunState = RunState.PENDING
    output: str | None = None
    error_code: str | None = None

    @property
    def is_active(self) -> bool:
        """Whether the run is still in progress (resumable) — pending or running."""
        return self.state in (RunState.PENDING, RunState.RUNNING)

    @property
    def is_terminal(self) -> bool:
        """Whether the run has reached a terminal outcome."""
        return not self.is_active


class ConversationState:
    """An ordered, append-only turn history for one session (doc 18 §9)."""

    def __init__(self, session_id: str | None) -> None:
        self._session_id = session_id
        self._turns: list[ConversationTurn] = []

    @property
    def session_id(self) -> str | None:
        return self._session_id

    def add_turn(self, turn: ConversationTurn) -> None:
        """Append a turn to the conversation."""
        self._turns.append(turn)

    def turns(self) -> tuple[ConversationTurn, ...]:
        """An immutable snapshot of the turns so far."""
        return tuple(self._turns)

    def __len__(self) -> int:
        return len(self._turns)
