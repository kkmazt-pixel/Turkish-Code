"""Tests for the tool registry (doc 20 §11, doc 24 §4)."""

from __future__ import annotations

import pytest
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.hata import TOOL_DUPLICATE_CODE, TOOL_NOT_FOUND_CODE
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.modeller import (
    Capability,
    SideEffect,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from turkish_code.araclar.protocol import Tool
from turkish_code.hata import AppError, ErrorKind


class _StubTool:
    """A structural :class:`Tool` whose metadata is fully controllable."""

    def __init__(self, metadata: ToolMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output=None)


def _tool(
    name: str,
    *,
    capability: Capability | None = Capability.FS_READ,
    side_effect: SideEffect = SideEffect.READ,
    version: int = 1,
) -> Tool:
    return _StubTool(
        ToolMetadata(
            name=name,
            summary=f"{name} aracı",
            capability=capability,
            side_effect=side_effect,
            brokered=capability is not None,
            reversible=side_effect is SideEffect.MUTATE,
            idempotent=True,
            timeout_ms=1000,
            version=version,
        )
    )


def test_register_then_resolve_returns_same_tool() -> None:
    registry = ToolRegistry()
    tool = _tool("fs.read")
    registry.register(tool)
    assert registry.resolve("fs.read") is tool


def test_resolve_missing_raises_not_found() -> None:
    registry = ToolRegistry()
    with pytest.raises(AppError) as exc_info:
        registry.resolve("absent")
    assert exc_info.value.code == TOOL_NOT_FOUND_CODE
    assert exc_info.value.kind is ErrorKind.NOT_FOUND


def test_duplicate_registration_is_rejected() -> None:
    registry = ToolRegistry()
    registry.register(_tool("fs.read"))
    with pytest.raises(AppError) as exc_info:
        registry.register(_tool("fs.read"))
    assert exc_info.value.code == TOOL_DUPLICATE_CODE
    assert exc_info.value.kind is ErrorKind.CONFLICT


def test_register_all_adds_each_tool() -> None:
    registry = ToolRegistry()
    registry.register_all([_tool("a"), _tool("b"), _tool("c")])
    assert len(registry) == 3
    assert registry.names() == ["a", "b", "c"]


def test_register_all_aborts_on_first_duplicate() -> None:
    registry = ToolRegistry()
    with pytest.raises(AppError):
        registry.register_all([_tool("a"), _tool("b"), _tool("a")])
    # "a" and "b" were added before the abort; the second "a" is what failed.
    assert registry.names() == ["a", "b"]


def test_get_returns_none_for_missing() -> None:
    registry = ToolRegistry()
    assert registry.get("absent") is None


def test_contains_and_len() -> None:
    registry = ToolRegistry()
    registry.register(_tool("fs.read"))
    assert "fs.read" in registry
    assert "absent" not in registry
    assert 123 not in registry  # non-str never contained
    assert len(registry) == 1


def test_names_are_sorted() -> None:
    registry = ToolRegistry()
    registry.register_all([_tool("z"), _tool("a"), _tool("m")])
    assert registry.names() == ["a", "m", "z"]


def test_catalog_returns_metadata_sorted_by_name() -> None:
    registry = ToolRegistry()
    registry.register_all([_tool("b", version=3), _tool("a", version=2)])
    catalog = registry.catalog()
    assert [m.name for m in catalog] == ["a", "b"]
    assert [m.version for m in catalog] == [2, 3]


def test_version_of_returns_registered_version() -> None:
    registry = ToolRegistry()
    registry.register(_tool("fs.read", version=7))
    assert registry.version_of("fs.read") == 7


def test_version_of_missing_raises_not_found() -> None:
    registry = ToolRegistry()
    with pytest.raises(AppError) as exc_info:
        registry.version_of("absent")
    assert exc_info.value.code == TOOL_NOT_FOUND_CODE


def test_by_capability_groups_tools() -> None:
    registry = ToolRegistry()
    registry.register_all(
        [
            _tool("fs.read", capability=Capability.FS_READ),
            _tool(
                "fs.write",
                capability=Capability.FS_WRITE,
                side_effect=SideEffect.MUTATE,
            ),
            _tool("fs.stat", capability=Capability.FS_READ),
        ]
    )
    reads = registry.by_capability(Capability.FS_READ)
    assert [t.metadata.name for t in reads] == ["fs.read", "fs.stat"]


def test_by_capability_none_selects_local_tools() -> None:
    registry = ToolRegistry()
    registry.register_all(
        [
            _tool("memory.search", capability=None),
            _tool("fs.read", capability=Capability.FS_READ),
        ]
    )
    local = registry.by_capability(None)
    assert [t.metadata.name for t in local] == ["memory.search"]
