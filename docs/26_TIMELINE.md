# 26 — Timeline (Zaman Çizelgesi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `zaman/`
> **Related:** [27_SNAPSHOTS](./27_SNAPSHOTS.md) · [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md) · [29_STORAGE](./29_STORAGE.md) · [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) · [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md)

---

## 1. Purpose

Defines the **Zaman Çizelgesi**, the append-only, ordered event log of *everything* the system perceives and does — messages, reasoning steps, tool calls, edits, permission decisions, provider calls, errors. It is the backbone of Pillar P4 (memory & auditability): the complete, immutable record from which the UI reconstructs sessions, crash recovery replays state, and the user answers "what happened, when, and why." It complements (does not duplicate) curated memory ([11](./11_MEMORY_SYSTEM.md), the *editorialized* store) — the Timeline is the *exhaustive* record.

## 2. Scope

The event model, the append-only journal + queryable projection, ordering/sequencing, provenance, retention, and querying/replay. Out of scope: file-content capture ([27_SNAPSHOTS](./27_SNAPSHOTS.md) — the Timeline *references* snapshots), resume orchestration ([28](./28_CRASH_RECOVERY.md) uses the journal), storage engine details ([29](./29_STORAGE.md)), curated memory ([11](./11_MEMORY_SYSTEM.md)).

## 3. Goals

1. **Record everything important, immutably** (PR-5): perception + action as ordered events.
2. **Reconstruct** any session/UI state from events (event-sourcing bias) — enabling reload, resume, and replay.
3. **Explain**: every agent action is traceable to its cause (reasoning step, user request) and effect (snapshot, result).
4. **Durable & crash-safe**: a write-ahead journal so nothing in flight is lost ([28](./28_CRASH_RECOVERY.md)).
5. **Private & local** ([P1]): the Timeline is sensitive (it mirrors your work); it never egresses without consent and redacts secrets.

### Non-Goals
- Not curated long-term memory ([11](./11_MEMORY_SYSTEM.md)). Not file storage ([27](./27_SNAPSHOTS.md)). Not analytics/telemetry (that would be egress, [30](./30_SECURITY.md)).

## 4. Event Model (Olay)

Every event is immutable and append-only:

```
Event {
  id: uuid
  seq: monotonic per (workspace, session)   // total order within a session
  ts: timestamp (monotonic + wall)
  workspaceId, sessionId, runId?, agentId?  // context (18/25)
  traceId                                    // ties related events (15)
  kind: message|reasoning_step|tool_call|tool_result|file_edit|
        permission_decision|provider_call|snapshot|error|memory_write|
        council|session_state|effort
  actor: user|agent:<id>|system
  payload: {...}          // kind-specific, schema-versioned
  refs: { snapshotId?, blobRef?, memoryId?, causedBy?: eventId }  // provenance links
  redacted: bool          // secrets/sensitive removed (30)
}
```

- **Causality:** `refs.causedBy` links effects to causes (a `file_edit` caused by a `tool_call` caused by a `reasoning_step`), enabling full "why" traversal.
- **Large payloads** (file contents, big outputs) are **not** inlined — they're `blobRef`/`snapshotId` references ([10](./10_IPC.md) §11, [27](./27_SNAPSHOTS.md)/[29](./29_STORAGE.md)).

## 5. Architecture: Journal + Projection

Two representations of the same truth:

```
WRITE PATH:  event → APPEND to Event Journal (write-ahead, fsync'd) → ACK
             → asynchronously PROJECT into queryable tables (SQLite, 29)
READ PATH:   UI/queries hit the projection (indexed); replay/recovery reads the journal
```

- **Event Journal** (`journal/`, [29](./29_STORAGE.md)): the append-only, durable source of truth (write-ahead). Ordered, fsync-guaranteed for durability ([28](./28_CRASH_RECOVERY.md)).
- **Projection** (Workspace DB tables): a derived, indexed view for fast queries/filtering by the `ZamanCizelgesi` UI ([06](./06_COMPONENT_LIBRARY.md) §6.6). The projection is **rebuildable from the journal** (PR-15) — if it's corrupt, replay the journal.
- This separation gives durability (journal) + queryability (projection) without compromising either.

## 6. Ordering & Sequencing

- `seq` is a per-session monotonic counter assigned at append (single writer, [09](./09_PYTHON_BACKEND.md) §6) → a total order within a session. Cross-session order uses `ts` + `seq`.
- `seq` also drives **stream resume** ([10](./10_IPC.md) §8): the UI tracks the last seq it rendered; on reload/reconnect it requests events since that seq. This is why streaming and the Timeline share the same sequence space.

## 7. What Gets Recorded (and by Whom)

- **Reasoning** ([15](./15_REASONING_ENGINE.md)): each plan/act/observe/reflect step, council steps ([16](./16_COUNCIL_MODE.md)).
- **Tools** ([20](./20_TOOL_SYSTEM.md)): every call + result (args redacted where sensitive), with snapshot refs for mutations.
- **Permissions** ([24](./24_PERMISSION_SYSTEM.md)): every decision (allow/ask/deny) and user response.
- **Provider calls** ([21](./21_PROVIDER_SYSTEM.md)): which model/provider, tokens, local/cloud (egress marker), latency.
- **Edits** ([27](./27_SNAPSHOTS.md)): file mutations with before/after snapshot refs.
- **Errors** ([38](./38_ERROR_HANDLING.md)), **memory writes** ([11](./11_MEMORY_SYSTEM.md)), **session/effort state** ([17](./17_EFFORT_MODES.md)).
- The Kabuk broker appends effect events at the choke point ([08](./08_TAURI_ARCHITECTURE.md) §11) so no side effect can occur unrecorded — a structural guarantee, not a convention.

## 8. Querying & Replay

- **Query API** (`timeline.query`, [10](./10_IPC.md)): filter by kind/actor/time/run/trace; paginate; follow causality links. Powers the `ZamanCizelgesi` viewer ([06](./06_COMPONENT_LIBRARY.md) §6.6): scrub, filter (edits/tools/messages/reasoning), jump to a snapshot ([27](./27_SNAPSHOTS.md)).
- **Replay:** reconstruct session/UI state up to any `seq` (for resume [28] and for "show me the state at step N").
- **Provenance queries:** "why did this edit happen?" walks `causedBy` back to the originating user request/reasoning.

## 9. Retention & Privacy

- **Retention policy** (configurable, [33](./33_CONFIGURATION.md)): keep full detail for a recent window, then optionally compact older events (summarize, drop verbose token-level detail) while preserving the audit-critical spine (edits, permissions, tool calls). Compaction is deterministic and itself logged.
- **User control:** the user can export (local file), or purge session/timeline history (privacy) — purge removes journal + projection + associated blobs/snapshots consistently.
- **Redaction:** secrets/sensitive values are redacted before persistence ([30](./30_SECURITY.md)); the Timeline never stores raw secrets.
- **No egress** without explicit consent ([P1]).

## 10. Lifecycle & State

```
event produced → append(journal, fsync) → ack → project(async) → queryable
session close → mark; journal remains for history/recovery
retention pass → compact old events (deterministic)
purge → consistent delete across journal/projection/blobs
```

## 11. Directory Structure

```
zaman/
  event.py        # event model + kinds (schema-versioned)
  journal.py      # append-only write-ahead journal (fsync)  → storage 29
  project.py      # projection into queryable tables (rebuildable)
  query.py        # timeline.query API (10)
  retention.py    # compaction/retention/purge
```

## 12. Configuration

- Retention window/compaction policy, redaction rules, projection indexes, and fsync durability level are configurable ([33](./33_CONFIGURATION.md)), defaulting to strong durability + privacy.

## 13. Dependencies

- [29_STORAGE](./29_STORAGE.md) (journal + projection + blobs), [27_SNAPSHOTS](./27_SNAPSHOTS.md) (edit refs), [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md) (replay), [10_IPC](./10_IPC.md) (query + seq/stream), [30_SECURITY](./30_SECURITY.md) (redaction), all producing subsystems (15/16/20/21/24/11).

## 14. Edge Cases

- **Projection corrupt:** rebuild from the journal (source of truth).
- **Journal write fails (disk full):** the *effect that would produce the event* must not be considered committed — the broker orders "snapshot → effect → event append"; if the event can't be durably recorded, surface a typed error and avoid claiming success ([38](./38_ERROR_HANDLING.md)). (Durability of the audit trail is a P4 requirement.)
- **Crash between append and projection:** on restart, re-project from the journal (idempotent) — no lost events ([28](./28_CRASH_RECOVERY.md)).
- **Huge sessions:** projection is indexed + paginated; retention compaction bounds growth.
- **Clock skew:** ordering relies on monotonic `seq`, not wall time.
- **Secret slips into a payload:** redaction pass + a secret scanner; if detected post-hoc, a redaction event supersedes (originals purgeable).

## 15. Failure Recovery

- The journal *is* the recovery substrate ([28](./28_CRASH_RECOVERY.md)): fsync'd, append-only, replayable. The projection is disposable/rebuildable. This division makes the Timeline itself crash-safe.

## 16. Security

- Sensitive by nature; **local, redacted, no egress** without consent ([30](./30_SECURITY.md), [P1]). Immutability (append-only) means the audit trail can't be silently rewritten — corrections are new events superseding old, preserving history (aligns with [11](./11_MEMORY_SYSTEM.md) supersede semantics). Purge is honored completely (consistent multi-store delete).

## 17. Performance

- Append is O(1) + a bounded fsync; projection is async off the hot path; queries are indexed/paginated; large payloads are references, not inline ([10](./10_IPC.md) §11). Streaming reuses the seq space (no extra bookkeeping). Budgets/metrics in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 18. Testing Strategy

- **Reconstruction test:** replay journal → identical projection/state (PR-15).
- **Durability/crash test:** kill mid-append/mid-project → no lost/duplicated events after recovery.
- **Causality test:** provenance links let you walk any effect to its cause.
- **Redaction test:** no raw secrets persisted; purge is complete.
- **Resume test:** seq-based stream resume yields no gaps/dupes ([10](./10_IPC.md)). See [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- Rich Timeline visual analytics; "time-travel" to any point with snapshot restore ([27](./27_SNAPSHOTS.md)); diff-of-diffs across runs; exportable audit reports for compliance; signed/tamper-evident journals for high-assurance environments.

## 20. Examples

- The `ZamanCizelgesi` shows: user message → reasoning steps → `tool_call fs.write src/app.ts` (with a snapshot ref) → `permission_decision allow` → result → done. Clicking the edit jumps to the snapshot; "neden?" walks `causedBy` to the user's original request.

## 21. Anti-Patterns

- Mutating or deleting past events in place (must be append-only; corrections supersede).
- Inlining large blobs/secrets into events.
- Treating the projection as source of truth (it's derived).
- Claiming a side effect succeeded when its event couldn't be durably recorded.
- Egressing timeline data as "telemetry."

## 22. Things That Must Never Happen

1. A side effect occurs without a corresponding durable Timeline event.
2. Past events are silently rewritten/deleted (immutability broken).
3. Raw secrets are persisted in events.
4. Timeline data egresses without consent.
5. The projection is trusted over the journal after corruption.

## 23. Relationship With Other Subsystems

Records events from [15](./15_REASONING_ENGINE.md)/[16](./16_COUNCIL_MODE.md)/[20](./20_TOOL_SYSTEM.md)/[21](./21_PROVIDER_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)/[11](./11_MEMORY_SYSTEM.md); references [27_SNAPSHOTS](./27_SNAPSHOTS.md); is the substrate for [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md); persisted by [29_STORAGE](./29_STORAGE.md); provides provenance to [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md); queried via [10_IPC](./10_IPC.md); visualized by [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md); scoped by [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md); redacted per [30_SECURITY](./30_SECURITY.md).

## 24. Migration Considerations

- Event `kind`/payload schemas are versioned; new kinds/fields are additive (PR-18); readers ignore unknown kinds gracefully. The journal format is forward-only; a format change ships a re-projection migration (journal replayed into the new projection). Compaction/retention changes are deterministic and documented.
