"""Tests for agent models, metadata, and the Agent Protocol (doc 18 §4/§6/§9)."""

from __future__ import annotations

import pytest
from turkish_code.ajanlar.baglam import AgentContext
from turkish_code.ajanlar.modeller import (
    AgentMetadata,
    AgentRequest,
    AgentResponse,
    MemoryScope,
    SessionState,
)
from turkish_code.ajanlar.protocol import Agent


def _meta(**overrides: object) -> AgentMetadata:
    base: dict[str, object] = {
        "id": "yonetici",
        "name": "Yönetici",
        "role": "orchestrator",
        "summary": "görevi böler ve devreder",
    }
    base.update(overrides)
    return AgentMetadata(**base)  # type: ignore[arg-type]


def test_state_and_scope_wire_values() -> None:
    assert SessionState.RUNNING.value == "running"
    assert SessionState.SHUTDOWN.value == "shutdown"
    assert MemoryScope.ISOLATED.value == "isolated"
    assert MemoryScope.WORKSPACE.value == "workspace"


def test_metadata_defaults_are_least_privilege() -> None:
    meta = _meta()
    assert meta.tool_grants == frozenset()
    assert meta.memory_scope is MemoryScope.ISOLATED
    assert meta.version == 1


def test_metadata_grants_tool() -> None:
    meta = _meta(tool_grants=frozenset({"fs.read", "code.search"}))
    assert meta.grants_tool("fs.read")
    assert not meta.grants_tool("fs.write")


@pytest.mark.parametrize("label", ["id", "name", "role"])
def test_metadata_rejects_empty_required_fields(label: str) -> None:
    with pytest.raises(ValueError, match=f"{label} must be non-empty"):
        _meta(**{label: ""})


def test_metadata_rejects_bad_version() -> None:
    with pytest.raises(ValueError, match="version must be"):
        _meta(version=0)


def test_metadata_is_immutable() -> None:
    meta = _meta()
    with pytest.raises(AttributeError):
        meta.role = "kodlayici"  # type: ignore[misc]


def test_request_and_response_correlate_by_run_id() -> None:
    req = AgentRequest(
        agent_id="yonetici", message="özellik ekle", run_id="r1", session_id="s1"
    )
    resp = AgentResponse(run_id=req.run_id, output="tamam")
    assert resp.run_id == "r1"
    assert req.session_id == "s1"


def test_request_session_id_defaults_to_none() -> None:
    req = AgentRequest(agent_id="a", message="m", run_id="r")
    assert req.session_id is None


def test_context_holds_correlation_ids() -> None:
    ctx = AgentContext(run_id="r2", session_id="s2")
    assert ctx.run_id == "r2" and ctx.session_id == "s2"


class _StubAgent:
    """A minimal structural :class:`Agent` — proves the Protocol is satisfiable."""

    def __init__(self, metadata: AgentMetadata) -> None:
        self._metadata = metadata

    @property
    def metadata(self) -> AgentMetadata:
        return self._metadata

    async def run(self, request: AgentRequest, context: AgentContext) -> AgentResponse:
        return AgentResponse(run_id=request.run_id, output="ok")


def test_concrete_agent_satisfies_protocol() -> None:
    assert isinstance(_StubAgent(_meta()), Agent)


def test_plain_object_is_not_an_agent() -> None:
    assert not isinstance(object(), Agent)
