"""Tests for the tool contract value objects + error taxonomy (doc 20 §4, doc 38)."""

from __future__ import annotations

import pytest
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.hata import (
    TOOL_CANCELLED_CODE,
    TOOL_DENIED_CODE,
    TOOL_DUPLICATE_CODE,
    TOOL_FAILED_CODE,
    TOOL_INVALID_ARGS_CODE,
    TOOL_NOT_FOUND_CODE,
    TOOL_TIMEOUT_CODE,
    duplicate_tool,
    invalid_tool_args,
    tool_cancelled,
    tool_denied,
    tool_failed,
    tool_not_found,
    tool_timeout,
)
from turkish_code.araclar.modeller import (
    Capability,
    SideEffect,
    ToolMetadata,
    ToolRequest,
    ToolResult,
)
from turkish_code.araclar.protocol import Tool
from turkish_code.hata import AppError, ErrorKind
from turkish_code.ortak.kimlik import RunId


def _meta(**overrides: object) -> ToolMetadata:
    base: dict[str, object] = {
        "name": "fs.read",
        "summary": "kullanıcı dosyasını okur",
        "capability": Capability.FS_READ,
        "side_effect": SideEffect.READ,
        "brokered": True,
        "reversible": False,
        "idempotent": True,
        "timeout_ms": 5000,
    }
    base.update(overrides)
    return ToolMetadata(**base)  # type: ignore[arg-type]


def test_metadata_wire_values_match_docs() -> None:
    assert SideEffect.MUTATE.value == "mutate"
    assert Capability.FS_WRITE.value == "fs.write"
    assert Capability.NET_EGRESS.value == "net.egress"


def test_metadata_defaults_version_to_one() -> None:
    assert _meta().version == 1


def test_local_tool_has_no_capability() -> None:
    meta = _meta(name="memory.search", capability=None, brokered=False)
    assert meta.capability is None


def test_empty_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        _meta(name="")


def test_non_positive_timeout_is_rejected() -> None:
    with pytest.raises(ValueError, match="timeout_ms must be positive"):
        _meta(timeout_ms=0)


def test_version_below_one_is_rejected() -> None:
    with pytest.raises(ValueError, match="version must be"):
        _meta(version=0)


def test_mutating_tool_must_be_reversible() -> None:
    with pytest.raises(ValueError, match="must be reversible"):
        _meta(
            name="fs.write",
            capability=Capability.FS_WRITE,
            side_effect=SideEffect.MUTATE,
            reversible=False,
        )


def test_mutating_reversible_tool_is_accepted() -> None:
    meta = _meta(
        name="fs.write",
        capability=Capability.FS_WRITE,
        side_effect=SideEffect.MUTATE,
        reversible=True,
    )
    assert meta.side_effect is SideEffect.MUTATE and meta.reversible


def test_metadata_is_immutable() -> None:
    meta = _meta()
    with pytest.raises(AttributeError):
        meta.name = "other"  # type: ignore[misc]


def test_request_and_result_correlate_by_call_id() -> None:
    req = ToolRequest(
        name="fs.read",
        arguments={"path": "src/app.ts"},
        call_id="c1",
        run_id=RunId("r1"),
    )
    result = ToolResult(call_id=req.call_id, output={"bytes": 12})
    assert result.call_id == "c1"
    assert req.run_id == RunId("r1")


def test_request_run_id_defaults_to_none() -> None:
    req = ToolRequest(name="memory.search", arguments={}, call_id="c2")
    assert req.run_id is None


def test_context_holds_correlation_ids() -> None:
    ctx = ToolContext(call_id="c3", run_id=RunId("r3"))
    assert ctx.call_id == "c3" and ctx.run_id == RunId("r3")


class _DummyTool:
    """A minimal structural :class:`Tool` — proves the Protocol is satisfiable."""

    def __init__(self, metadata: ToolMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> ToolMetadata:
        return self._metadata

    async def execute(self, request: ToolRequest, context: ToolContext) -> ToolResult:
        return ToolResult(call_id=request.call_id, output=None)


def test_concrete_tool_satisfies_protocol() -> None:
    assert isinstance(_DummyTool(_meta()), Tool)


def test_plain_object_is_not_a_tool() -> None:
    assert not isinstance(object(), Tool)


@pytest.mark.parametrize(
    ("factory", "kind", "code", "retryable"),
    [
        (lambda: tool_not_found("x"), ErrorKind.NOT_FOUND, TOOL_NOT_FOUND_CODE, False),
        (
            lambda: invalid_tool_args("x", "bad"),
            ErrorKind.VALIDATION,
            TOOL_INVALID_ARGS_CODE,
            False,
        ),
        (
            lambda: tool_denied("x", Capability.FS_WRITE),
            ErrorKind.PERMISSION,
            TOOL_DENIED_CODE,
            False,
        ),
        (lambda: tool_timeout("x", 1000), ErrorKind.TIMEOUT, TOOL_TIMEOUT_CODE, True),
        (lambda: tool_cancelled("x"), ErrorKind.CANCELLED, TOOL_CANCELLED_CODE, False),
        (
            lambda: tool_failed("x", detail="boom"),
            ErrorKind.INTERNAL,
            TOOL_FAILED_CODE,
            False,
        ),
        (lambda: duplicate_tool("x"), ErrorKind.CONFLICT, TOOL_DUPLICATE_CODE, False),
    ],
)
def test_error_factories_carry_expected_kind_and_code(
    factory: object, kind: ErrorKind, code: str, retryable: bool
) -> None:
    err = factory()  # type: ignore[operator]
    assert isinstance(err, AppError)
    assert err.kind is kind
    assert err.code == code
    assert err.retryable is retryable
    assert err.message_key == f"hata.{code}"


def test_tool_failed_preserves_cause_chain() -> None:
    root = tool_timeout("inner", 500)
    err = tool_failed("outer", detail="wrapped", cause=root)
    assert err.causes() == [root]


def test_denied_error_surfaces_tool_and_capability_context() -> None:
    err = tool_denied("fs.write", Capability.FS_WRITE)
    data = err.to_error_data()
    assert data["context"] == {"tool": "fs.write", "capability": Capability.FS_WRITE}
