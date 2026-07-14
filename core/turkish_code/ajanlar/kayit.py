"""Agent registry (doc 18 §10) — the available agents, selectable by role.

Holds every registered agent keyed by its metadata id, plus an optional
**default** agent the dispatcher falls back to. Registration is fail-safe: a
duplicate id is rejected (doc 18 §10). Agents are selectable by **role** — the
orchestrator picks an agent by role for a sub-task (doc 18 §5/§10). The registry
owns storage and lookup only; it runs nothing.
"""

from __future__ import annotations

from turkish_code.ajanlar.protocol import Agent
from turkish_code.hata import AppError, ErrorKind

AGENT_DUPLICATE_CODE = "agent.duplicate"
AGENT_NOT_FOUND_CODE = "agent.not_found"
AGENT_NO_DEFAULT_CODE = "agent.no_default"


class AgentRegistry:
    """An in-memory id→:class:`Agent` registry with a default (doc 18 §10)."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._default_id: str | None = None

    def register(self, agent: Agent, *, default: bool = False) -> None:
        """Add ``agent``; reject a duplicate id (fail-safe, doc 18 §10).

        ``default=True`` marks it the registry default (last such wins).
        """
        agent_id = agent.metadata.id
        if agent_id in self._agents:
            raise _duplicate(agent_id)
        self._agents[agent_id] = agent
        if default:
            self._default_id = agent_id

    def resolve(self, agent_id: str) -> Agent:
        """The agent registered as ``agent_id``, or raise ``agent.not_found``."""
        agent = self._agents.get(agent_id)
        if agent is None:
            raise _not_found(agent_id)
        return agent

    def get(self, agent_id: str) -> Agent | None:
        """The agent registered as ``agent_id``, or ``None`` if absent."""
        return self._agents.get(agent_id)

    def __contains__(self, agent_id: object) -> bool:
        return isinstance(agent_id, str) and agent_id in self._agents

    def __len__(self) -> int:
        return len(self._agents)

    def ids(self) -> list[str]:
        """All registered agent ids, sorted."""
        return sorted(self._agents)

    def by_role(self, role: str) -> list[Agent]:
        """Every agent with ``role``, id-sorted (doc 18 §5/§10)."""
        return [
            self._agents[agent_id]
            for agent_id in sorted(self._agents)
            if self._agents[agent_id].metadata.role == role
        ]

    def roles(self) -> list[str]:
        """The distinct roles present, sorted."""
        return sorted({agent.metadata.role for agent in self._agents.values()})

    def set_default(self, agent_id: str) -> None:
        """Designate ``agent_id`` the default; it must be registered (doc 18 §10)."""
        if agent_id not in self._agents:
            raise _not_found(agent_id)
        self._default_id = agent_id

    def default_id(self) -> str | None:
        """The default agent's id, or ``None`` if none is set."""
        return self._default_id

    def default(self) -> Agent | None:
        """The default agent, or ``None`` if none is set."""
        return self._agents.get(self._default_id) if self._default_id else None

    def resolve_default(self) -> Agent:
        """The default agent, or raise ``agent.no_default`` if none is set."""
        if self._default_id is None:
            raise _no_default()
        return self._agents[self._default_id]


def _duplicate(agent_id: str) -> AppError:
    return _err(
        ErrorKind.CONFLICT,
        AGENT_DUPLICATE_CODE,
        f"an agent is already registered as {agent_id!r}",
        agent_id,
    )


def _not_found(agent_id: str) -> AppError:
    return _err(
        ErrorKind.NOT_FOUND,
        AGENT_NOT_FOUND_CODE,
        f"no agent registered as {agent_id!r}",
        agent_id,
    )


def _no_default() -> AppError:
    return _err(
        ErrorKind.NOT_FOUND,
        AGENT_NO_DEFAULT_CODE,
        "no default agent is set",
        None,
    )


def _err(kind: ErrorKind, code: str, detail: str, agent_id: str | None) -> AppError:
    context = {"agent": agent_id} if agent_id is not None else None
    return AppError(
        kind=kind,
        code=code,
        message_key=f"hata.{code}",
        retryable=False,
        detail=detail,
        context=context,
    )
