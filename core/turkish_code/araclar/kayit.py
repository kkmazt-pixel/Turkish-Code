"""Tool registry (doc 20 §11) — the built-in + plugin tool catalog.

Built once at startup by the composition root; every invocation resolves its
tool here by name (doc 20 §5/§11). Registration is **fail-safe**: a duplicate
name is rejected (doc 20 §11) so two tools can never shadow one capability. The
registry is capability-aware — it can enumerate the tools guarding each
permission class (doc 24 §4) for the permission layer and the model-facing
catalog. It owns no execution; it only stores and looks up :class:`Tool`
contracts.
"""

from __future__ import annotations

from collections.abc import Iterable

from turkish_code.araclar.hata import duplicate_tool, tool_not_found
from turkish_code.araclar.modeller import Capability, ToolMetadata
from turkish_code.araclar.protocol import Tool


class ToolRegistry:
    """An in-memory name→:class:`Tool` catalog (doc 20 §11)."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Add ``tool``; reject a duplicate name (fail-safe, doc 20 §11)."""
        name = tool.metadata.name
        if name in self._tools:
            raise duplicate_tool(name)
        self._tools[name] = tool

    def register_all(self, tools: Iterable[Tool]) -> None:
        """Register each tool in order; the first duplicate aborts (doc 20 §11)."""
        for tool in tools:
            self.register(tool)

    def unregister(self, name: str) -> None:
        """Remove the tool registered as ``name``, or raise ``tool_not_found``.

        The inverse of :meth:`register` — lets a plugin's contributions be
        withdrawn when it is disabled/unloaded (doc 23 §7/§12).
        """
        if name not in self._tools:
            raise tool_not_found(name)
        del self._tools[name]

    def resolve(self, name: str) -> Tool:
        """The tool registered as ``name``, or raise ``tool_not_found`` (doc 20 §11)."""
        tool = self._tools.get(name)
        if tool is None:
            raise tool_not_found(name)
        return tool

    def get(self, name: str) -> Tool | None:
        """The tool registered as ``name``, or ``None`` if absent."""
        return self._tools.get(name)

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    def names(self) -> list[str]:
        """All registered tool names, sorted for stable enumeration."""
        return sorted(self._tools)

    def catalog(self) -> list[ToolMetadata]:
        """Every tool's metadata, name-sorted — the model-facing catalog (doc 20 §7)."""
        return [self._tools[name].metadata for name in sorted(self._tools)]

    def version_of(self, name: str) -> int:
        """The registered version of ``name`` (doc 20 §24), or raise not-found."""
        return self.resolve(name).metadata.version

    def by_capability(self, capability: Capability | None) -> list[Tool]:
        """Tools guarding ``capability`` (doc 24 §4); ``None`` selects local tools."""
        return [
            self._tools[name]
            for name in sorted(self._tools)
            if self._tools[name].metadata.capability is capability
        ]
