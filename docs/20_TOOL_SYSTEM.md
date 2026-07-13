# 20 — Tool System (Araçlar)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `araclar/` + Kabuk `broker/`
> **Related:** [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) · [27_SNAPSHOTS](./27_SNAPSHOTS.md) · [26_TIMELINE](./26_TIMELINE.md) · [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) · [10_IPC](./10_IPC.md)

---

## 1. Purpose

Defines **Araçlar** (Tools): the executable capabilities the agent uses to *act on the world* — read/write files, run shell commands, search, edit code, access the web, query subsystems. Tools are how reasoning ([15](./15_REASONING_ENGINE.md)) becomes effect. This document specifies the tool schema/contract, the invocation flow through the permission choke point ([24](./24_PERMISSION_SYSTEM.md)/[08](./08_TAURI_ARCHITECTURE.md)), the built-in tool catalog, sandboxing, and the mandatory snapshot/timeline hooks that make every effect reversible and auditable (P4/P5).

## 2. Scope

Tool definition/schema, the invocation lifecycle (validate → permission → execute → snapshot → observe), the built-in catalog, the split between Çekirdek-side and Kabuk-brokered tools, sandboxing, and extension. Out of scope: permission *policy* ([24](./24_PERMISSION_SYSTEM.md)), snapshot mechanics ([27](./27_SNAPSHOTS.md)), reasoning ([15](./15_REASONING_ENGINE.md)), plugin-provided tools' packaging ([23](./23_PLUGIN_SYSTEM.md)).

## 3. Goals

1. A **uniform, typed, declarative** tool contract the model can call and an AI operator can read (PR-11).
2. **Every side effect a tool** — there is no other way for reasoning to affect the world (PR-2, one path).
3. **Permission-gated & reversible & audited by construction**: invocation *always* passes the Kabuk permission engine, snapshots before mutation, and appends a Timeline event ([08](./08_TAURI_ARCHITECTURE.md) §11).
4. **Safe & bounded**: validated arguments, sandboxed execution, budgeted call counts ([17](./17_EFFORT_MODES.md)).
5. **Extensible** via first-party additions and plugins ([23](./23_PLUGIN_SYSTEM.md)) without weakening the guarantees.

### Non-Goals
- Tools don't decide permission policy (they *request*; [24](./24_PERMISSION_SYSTEM.md) decides). Tools aren't skills ([19](./19_SKILLS_SYSTEM.md), knowledge) or agents ([18](./18_AGENT_SYSTEM.md), orchestration).

## 4. Tool Contract / Schema

A tool is a declarative definition + an implementation:

```
ToolDef {
  name: string                 // "fs.write", "shell.exec", "code.search", ...
  description: string          // for the model (when/why to use) — tr
  params: JSONSchema           // typed, validated arguments
  returns: JSONSchema          // typed result
  capability: Capability       // the permission required (24): fs.read/fs.write/shell.exec/net.egress/...
  sideEffect: none|read|mutate|exec|egress   // classification (drives snapshot/consent)
  brokered: bool               // true = executed by Kabuk broker (08); false = Çekirdek-local
  reversible: bool             // mutate tools MUST be snapshot-backed (27)
  idempotent: bool
  timeoutMs: int
}
```

- The schema is the source of truth for what the model may call and what the engine validates ([15](./15_REASONING_ENGINE.md) §6). It is codegen-friendly and inspectable ([AGENTS.md](./AGENTS.md)).
- `capability` links each tool to exactly one permission class ([24](./24_PERMISSION_SYSTEM.md)).

## 5. Invocation Lifecycle (The Critical Path)

```
1. Model requests tool call (native or structured-output, 15 §6)
2. VALIDATE args against params schema — reject malformed (no execution)
3. Çekirdek sends tool.invoke over Core Channel (10) with permission ctx
      (for brokered tools; Çekirdek-local read tools may run in-process)
4. Kabuk PERMISSION ENGINE (24/08): evaluate mode + grants + target
      → deny  → typed denial returned; model adapts (never bypass)
      → ask   → raise permission.request → user decides → respond
      → allow → proceed
5. If sideEffect == mutate: SNAPSHOT the target(s) BEFORE writing (27)
6. EXECUTE (Kabuk broker for brokered; Çekirdek for local) with timeout/sandbox
7. APPEND Timeline event (26): tool, args (redacted), result/err, snapshot ref
8. RETURN typed result → model OBSERVEs → reasoning continues (15)
```

Steps 4, 5, and 7 are **mandatory and non-bypassable** — they are the structural guarantees behind P4/P5 and are enforced in the broker ([08](./08_TAURI_ARCHITECTURE.md) §11), not left to each tool.

## 6. Çekirdek-local vs Kabuk-brokered Tools

- **Kabuk-brokered** (`brokered: true`): anything touching the **user's world** or requiring privilege — `fs.read`/`fs.write` on the project, `shell.exec`, `net.*` egress, `open.external`. These execute in the Kabuk broker under permission ([08](./08_TAURI_ARCHITECTURE.md), [09](./09_PYTHON_BACKEND.md) §9). This is the one-path rule (PR-2).
- **Çekirdek-local** (`brokered: false`): tools that only touch the Çekirdek's own derived state — `memory.search`/`memory.write` ([11](./11_MEMORY_SYSTEM.md)), `graph.query` ([12](./12_KNOWLEDGE_GRAPH.md)), `retrieve` ([13](./13_RAG_SYSTEM.md)), `code.search` (index-based). These have no ambient privilege and no user-world effect, so they run in-process (still validated, budgeted, and traced).

## 7. Built-in Tool Catalog

Grouped by capability (representative; full schemas in `araclar/`):

| Tool | capability | sideEffect | brokered | Notes |
|---|---|---|---|---|
| `fs.read` | fs.read | read | yes | reads user files; respects ignore rules |
| `fs.write` | fs.write | mutate | yes | **snapshot-backed** (27); creates/edits files |
| `fs.edit` | fs.write | mutate | yes | targeted edit (diff-apply), snapshot-backed |
| `fs.list` / `fs.stat` | fs.read | read | yes | directory/metadata |
| `shell.exec` | shell.exec | exec | yes | run a command in the workspace; sandboxed (§9); permission per command |
| `code.search` | (local) | read | no | index/graph search ([13](./13_RAG_SYSTEM.md)/[12](./12_KNOWLEDGE_GRAPH.md)) |
| `retrieve` | (local) | read | no | RAG retrieval ([13](./13_RAG_SYSTEM.md)) |
| `graph.query` | (local) | read | no | KG queries ([12](./12_KNOWLEDGE_GRAPH.md)) |
| `memory.*` | (local) | read/mutate | no | memory ops ([11](./11_MEMORY_SYSTEM.md)) |
| `net.fetch` | net.egress | egress | yes | HTTP GET; **egress → consent** ([30](./30_SECURITY.md)/[34](./34_API_KEYS.md)); off by default |
| `web.search` | net.egress | egress | yes | optional; consent-gated |
| `open.external` | open.external | exec | yes | open a URL/file in OS; permissioned |
| `run.tests` | shell.exec | exec | yes | convenience wrapper over shell.exec |

- **Egress tools** (`net.*`, `web.*`) are **disabled by default** and require explicit consent (offline-first, PR-6/PR-16). Their availability is a visible state ([06](./06_COMPONENT_LIBRARY.md) §6.8).
- **Mutating tools** are always `reversible: true` and snapshot-backed (§5.5).

## 8. Argument Validation

- Every call is validated against the tool's `params` JSON Schema **before** anything happens (step 2). Malformed args → typed error, no execution ([38](./38_ERROR_HANDLING.md)). This blocks a whole class of injection/malformed-call bugs.
- Path arguments are canonicalized and confined to the workspace (or explicitly-granted paths) — no `../` escapes (§9, [24](./24_PERMISSION_SYSTEM.md)).

## 9. Sandboxing & Confinement

- **Filesystem confinement:** `fs.*` tools are confined to the workspace root (and any explicitly-granted paths); path traversal outside is denied by the permission engine ([24](./24_PERMISSION_SYSTEM.md)).
- **Shell sandboxing:** `shell.exec` runs in the workspace working directory with a constrained environment (no secret env vars — [34](./34_API_KEYS.md)), a timeout, output size caps (bulk plane [10](./10_IPC.md) §11 for large output), and — where the OS supports it — reduced privileges. Each command (or command class) is permission-prompted per mode ([24](./24_PERMISSION_SYSTEM.md)).
- **Network confinement:** egress tools go through the single Kabuk `net.rs` path ([08](./08_TAURI_ARCHITECTURE.md)), consent-gated, with the destination shown to the user.
- **Resource caps:** timeouts, output caps, and per-run call budgets ([17](./17_EFFORT_MODES.md)) bound every tool.

## 10. Architecture / Directory

```
araclar/
  registry.py     # ToolDef registry (built-in + plugin 23)
  schema.py       # param/return validation
  invoke.py       # lifecycle orchestration (validate→request→observe)
  local/          # Çekirdek-local tools (memory, retrieve, graph, code.search)
  brokered/       # thin clients that request Kabuk broker ops (fs/shell/net)
# actual privileged execution lives in Kabuk broker/ (08)
```

## 11. Lifecycle & State

- Tools are **stateless** invocations; all durable effect is via snapshots ([27](./27_SNAPSHOTS.md))/storage ([29](./29_STORAGE.md))/timeline ([26](./26_TIMELINE.md)). A tool call's state machine is `Requested → Validated → Permissioned → Executing → (Done|Denied|Failed|Cancelled)`, each transition traced.
- Registry built at startup (built-in + plugin tools [23]); invalid tool defs are rejected (fail-safe).

## 12. Configuration

- Which tools are enabled, per-workspace tool sets, default-off egress tools, shell command allow/deny lists, timeouts, and output caps are configurable ([33](./33_CONFIGURATION.md)/[24](./24_PERMISSION_SYSTEM.md)).

## 13. Dependencies

- [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) (gating), [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) (broker execution), [27_SNAPSHOTS](./27_SNAPSHOTS.md) (reversibility), [26_TIMELINE](./26_TIMELINE.md) (audit), [10_IPC](./10_IPC.md) (transport), [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) (caller), [17_EFFORT_MODES](./17_EFFORT_MODES.md) (budgets), [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md) (extension).

## 14. Edge Cases

- **Malformed model tool call:** schema validation rejects; engine re-prompts (bounded, [15](./15_REASONING_ENGINE.md) §14).
- **Permission denied:** typed denial; model adapts; never a bypass path.
- **Mutating tool on a huge file / partial write:** pre-write snapshot ([27](./27_SNAPSHOTS.md)) guarantees rollback; write is atomic-ish (temp + rename) where possible.
- **shell.exec long-running / hangs:** timeout + cancellation ([10](./10_IPC.md)); output capped to the bulk plane; process killed cleanly (no orphans, [08](./08_TAURI_ARCHITECTURE.md)).
- **Path traversal / symlink escape:** canonicalization + confinement denies it.
- **Egress tool used while offline / no consent:** unavailable; the engine routes around it (PR-6).
- **Tool result too large for JSON frame:** forced onto the bulk plane ([10](./10_IPC.md) §11).
- **Plugin tool misbehaves:** sandbox + permission contain it; repeated failure → disable ([23](./23_PLUGIN_SYSTEM.md)).

## 15. Failure Recovery

- A failed tool returns a typed error ([38](./38_ERROR_HANDLING.md)); the reasoning loop observes and adapts (retry/alternative/ask) (PR-7/PR-10). A crash mid-mutation is recoverable via the pre-write snapshot ([27](./27_SNAPSHOTS.md)) and journal ([28](./28_CRASH_RECOVERY.md)) — the file is either the old snapshot or the completed new content, never corrupt.

## 16. Security

- **The tool system is the enforcement surface of the agent's power.** Guarantees (all structural): every effect passes permission ([24](./24_PERMISSION_SYSTEM.md)); egress is consent-gated and single-pathed ([08](./08_TAURI_ARCHITECTURE.md), [30](./30_SECURITY.md)); shell runs without secrets in env and confined; args are validated; mutations are snapshot-backed and audited. Prompt-injected instructions can, at worst, *request* a tool — which is then gated exactly like any other request. Plugin tools inherit all of this and run untrusted ([23](./23_PLUGIN_SYSTEM.md)). See [30_SECURITY](./30_SECURITY.md).

## 17. Performance

- Local read tools are fast (index-backed); brokered tools add an IPC hop (kept thin, [10](./10_IPC.md)); large outputs use the bulk plane to avoid stalling streams. Call counts are budgeted ([17](./17_EFFORT_MODES.md)). Metrics in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 18. Testing Strategy

- **Gating tests:** every mutating/exec/egress tool is provably un-runnable without permission (assert deny path).
- **Snapshot tests:** every `mutate` tool creates a restorable snapshot before writing.
- **Validation tests:** malformed args rejected pre-execution; path traversal denied.
- **Sandbox tests:** shell has no secrets in env, is confined, times out, is killable with no orphans.
- **Timeline tests:** every call appends an (redacted) audit event.
- **Bulk-output tests.** See [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- Richer editor tools (semantic/AST edits via [12](./12_KNOWLEDGE_GRAPH.md)); language-server integration; a dry-run/preview mode for mutations; capability-scoped tool bundles; MCP-style external tool servers (would still route egress/effects through the broker + permission model — never a bypass); plugin tools ([23](./23_PLUGIN_SYSTEM.md)).

## 20. Examples

```jsonc
// Model → engine → Core Channel (10): a snapshot-backed, permissioned write
{ "method":"tool.invoke",
  "params":{"name":"fs.write","args":{"path":"src/app.ts","contentRef":"blake3:…"}} }
// → validate → permission(fs.write, src/app.ts) → snapshot(src/app.ts) →
//   write → timeline event → result → model observes
```

## 21. Anti-Patterns

- A side effect that isn't a tool (a direct fs/shell/net call somewhere in the codebase — PR-2 violation).
- A mutating tool that skips the snapshot hook.
- Executing before validating args or before permission.
- Passing secrets into shell env.
- Egress tools on by default.
- Letting a tool run unbounded (no timeout/output cap/budget).

## 22. Things That Must Never Happen

1. A tool executes a side effect without passing the permission engine.
2. A mutating tool writes without a preceding snapshot + timeline event.
3. A tool escapes workspace confinement or runs shell with secrets in env.
4. Egress happens without consent.
5. Malformed/injection args reach execution unvalidated.

## 23. Relationship With Other Subsystems

Called by [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)/[18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md); gated by [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); executed (for brokered) by [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) `broker/`; made reversible by [27_SNAPSHOTS](./27_SNAPSHOTS.md) and audited by [26_TIMELINE](./26_TIMELINE.md); transported by [10_IPC](./10_IPC.md); budgeted by [17_EFFORT_MODES](./17_EFFORT_MODES.md); referenced by [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md); extended via [23_PLUGIN_SYSTEM](./23_PLUGIN_SYSTEM.md); constrained by [30_SECURITY](./30_SECURITY.md).

## 24. Migration Considerations

- `ToolDef` schema is versioned; new tools/params are additive (PR-18). Renaming a tool or changing its `capability` is a breaking change requiring migration + permission-policy review ([24](./24_PERMISSION_SYSTEM.md)). Plugin tools are validated against the current schema at load; incompatible ones are rejected ([23](./23_PLUGIN_SYSTEM.md)).
