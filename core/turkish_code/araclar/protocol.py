"""The tool implementation contract (doc 20 §4) — interface only.

:class:`Tool` is the one interface every executable capability implements: a
declarative :class:`~turkish_code.araclar.modeller.ToolMetadata` plus an async
:meth:`Tool.execute`. The runtime (registry/permission/dispatcher) depends only
on this Protocol, never on concrete tools — so first-party and (future) plugin
tools plug in without the runtime changing (doc 20 §5, DIP).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.modeller import ToolMetadata, ToolRequest, ToolResult


@runtime_checkable
class Tool(Protocol):
    """A single executable capability the agent can invoke (doc 20 §4)."""

    @property
    def metadata(self) -> ToolMetadata:
        """The tool's declarative contract (doc 20 §4)."""
        ...

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        """Run the tool for ``request`` and return its typed result (doc 20 §5).

        Implementations must be side-effect-honest with their
        :attr:`ToolMetadata.side_effect` and cooperatively observe cancellation
        via ``context`` (doc 20 §5/§14). Failure is raised as a typed
        :class:`~turkish_code.hata.AppError` (doc 38 §7,
        :mod:`turkish_code.araclar.hata`) — malformed args, denial, timeout, or
        an execution error — which the dispatcher surfaces so reasoning adapts
        (doc 20 §15). A returned :class:`ToolResult` therefore always denotes
        success.
        """
        ...
