"""The agent contract (doc 18 §4) — interface only.

:class:`Agent` is the one interface every runnable agent implements: a
declarative :class:`~turkish_code.ajanlar.modeller.AgentMetadata` plus an async
:meth:`Agent.run`. The runtime (registry/session/dispatcher) depends only on this
Protocol, never on concrete agents — so first-party and (future) plugin agents
plug in without the runtime changing (doc 18 §10, DIP). This models how an agent
*runs*, not how it reasons (doc 15 is out of scope for this phase).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from turkish_code.ajanlar.baglam import AgentContext
from turkish_code.ajanlar.modeller import AgentMetadata, AgentRequest, AgentResponse


@runtime_checkable
class Agent(Protocol):
    """A single runnable agent (doc 18 §4)."""

    @property
    def metadata(self) -> AgentMetadata:
        """The agent's declarative contract (doc 18 §4)."""
        ...

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        """Execute one run for ``request`` and return its result (doc 18 §6).

        Implementations work only through ``context`` — the scoped runtime
        handles, cancellation, and streaming (doc 18 §7/§16) — never touching
        Storage/Provider/Tool subsystems directly. Failure is raised as a typed
        :class:`~turkish_code.hata.AppError` (doc 38 §7) which the dispatcher
        surfaces; a returned :class:`AgentResponse` always denotes success.
        """
        ...
