"""Araçlar — the Tool Execution Runtime (doc 20).

The one path by which reasoning acts on the world: every side effect is a tool
(PR-2). This package defines the tool contract (:class:`Tool`), its declarative
metadata, the request/result value objects, and the typed error taxonomy; the
registry, permission gate, and dispatcher build on top of them across later
increments. Concrete tools and privileged execution (Kabuk broker, doc 08) live
elsewhere — the runtime depends only on the :class:`Tool` Protocol (DIP).
"""

from turkish_code.araclar.akis import (
    CollectingProgressSink,
    NullProgressSink,
    ProgressSink,
)
from turkish_code.araclar.baglam import ToolContext
from turkish_code.araclar.dagitici import ToolDispatcher
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
from turkish_code.araclar.iptal import CancellationRegistry, CancellationToken
from turkish_code.araclar.izin import (
    Allow,
    Decision,
    Deny,
    Grant,
    PermissionGate,
    PermissionMode,
    PermissionPolicy,
    PermissionRequest,
    PolicyPermissionGate,
    PromptRequired,
)
from turkish_code.araclar.kayit import ToolRegistry
from turkish_code.araclar.kompozisyon import ToolRuntime, build_tool_runtime
from turkish_code.araclar.modeller import (
    Capability,
    SideEffect,
    ToolMetadata,
    ToolProgress,
    ToolRequest,
    ToolResult,
)
from turkish_code.araclar.protocol import Tool

__all__ = [
    "Tool",
    "ToolContext",
    "ToolRegistry",
    "ToolDispatcher",
    "ToolRuntime",
    "build_tool_runtime",
    "CancellationToken",
    "CancellationRegistry",
    "ToolMetadata",
    "ToolRequest",
    "ToolResult",
    "ToolProgress",
    "ProgressSink",
    "NullProgressSink",
    "CollectingProgressSink",
    "Capability",
    "SideEffect",
    "PermissionMode",
    "PermissionPolicy",
    "PermissionRequest",
    "PermissionGate",
    "PolicyPermissionGate",
    "Grant",
    "Decision",
    "Allow",
    "Deny",
    "PromptRequired",
    "TOOL_NOT_FOUND_CODE",
    "TOOL_INVALID_ARGS_CODE",
    "TOOL_DENIED_CODE",
    "TOOL_TIMEOUT_CODE",
    "TOOL_CANCELLED_CODE",
    "TOOL_FAILED_CODE",
    "TOOL_DUPLICATE_CODE",
    "tool_not_found",
    "invalid_tool_args",
    "tool_denied",
    "tool_timeout",
    "tool_cancelled",
    "tool_failed",
    "duplicate_tool",
]
