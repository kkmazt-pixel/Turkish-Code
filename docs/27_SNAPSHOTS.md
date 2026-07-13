# 27 — Snapshots (Anlık Görüntüler)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `anlik/` + Kabuk `broker/` (capture hook)
> **Related:** [26_TIMELINE](./26_TIMELINE.md) · [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) · [29_STORAGE](./29_STORAGE.md) · [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md)

---

## 1. Purpose

Defines **Anlık Görüntüler** (Snapshots): content-addressed, point-in-time captures of workspace **file state** that make every agent file mutation **perfectly reversible**. Snapshots are the structural guarantee behind "reversible by default" (PR-4) and Pillar P4 — the user can always undo what the agent did. This document specifies when snapshots are taken (before every mutation, non-bypassably), how they're stored (content-addressed, deduplicated), and how restore/rollback works.

## 2. Scope

Snapshot triggers, the capture hook in the broker, content-addressed storage/dedup, snapshot grouping (per tool call / per run / checkpoints), restore/rollback semantics, retention, and integration with the Timeline. Out of scope: the full event log ([26](./26_TIMELINE.md), which *references* snapshots), storage engine ([29](./29_STORAGE.md)), session resume ([28](./28_CRASH_RECOVERY.md)).

## 3. Goals

1. **Every file mutation is preceded by a snapshot** — non-bypassable (PR-2/PR-4), enforced at the broker choke point ([08](./08_TAURI_ARCHITECTURE.md) §11).
2. **Perfect, one-click undo** of any agent edit (single file, a tool call, or an entire run).
3. **Cheap**: content-addressed dedup so unchanged content isn't re-stored; only *changed* files are captured (not whole-project copies).
4. **Durable & crash-safe**: a partially-completed mutation is always recoverable to a consistent state ([28](./28_CRASH_RECOVERY.md)).
5. **Local & private** ([P1]).

### Non-Goals
- Not a version control system (no branches/history semantics beyond undo); not a backup of the whole project; not the event log ([26](./26_TIMELINE.md)). Distinct from **Checkpoints** (session *state*, [28](./28_CRASH_RECOVERY.md)) — a Snapshot is *files*, a Checkpoint is *reasoning/session state* ([44](./44_GLOSSARY.md) §12 forbids conflating them).

## 4. When Snapshots Are Taken

- **Before every mutating tool call** ([20](./20_TOOL_SYSTEM.md): `fs.write`, `fs.edit`, delete, and any `sideEffect: mutate` tool). The broker takes the snapshot of the *target file(s)* **before** applying the change — mandatory, in one place ([08](./08_TAURI_ARCHITECTURE.md) §11). No mutation path skips it.
- **Grouping:** snapshots are grouped by `runId`/`toolCallId` so a whole run's changes can be reverted atomically, and by pre-run baseline so "undo everything this session did" is possible.
- **Capture scope:** only files that are about to change (and new-file creations recorded as "did not exist") — never the whole workspace (cheap, [07](./07_DESKTOP_ARCHITECTURE.md) §5 invariant).

## 5. Content-Addressed Storage (CAS)

- Each captured file version is stored as a blob keyed by its **BLAKE3 content hash** in the workspace Blob Store ([29](./29_STORAGE.md) `blobs/`). Identical content (unchanged files, repeated content) is stored **once** (dedup) — snapshots are effectively free for unchanged bytes.
- A `Snapshot` record ties a hash-set to a moment:

```
Snapshot {
  id: uuid
  runId, toolCallId?          // grouping (20/15)
  ts, seq                      // ordering (aligned to timeline 26)
  entries: [                   // per affected path
     { path, beforeHash|∅(new), afterHash|∅(deleted), mode }
  ]
  eventRef: eventId            // linked in the Timeline (26)
}
```

- **Before/after:** the snapshot records the state *before* the mutation; the *after* is the actual write. Restore = write the `beforeHash` content back (or delete a created file / recreate a deleted one).

## 6. Restore / Rollback Semantics

- **Granularity:** restore a single file, a single tool call's changes, a whole run, or roll back to a session's baseline ([06](./06_COMPONENT_LIBRARY.md) `KodFarki`/`ZamanCizelgesi` expose these).
- **Restore is itself a mutation** → it too passes permission ([24](./24_PERMISSION_SYSTEM.md)) and creates a new snapshot (so you can undo an undo) and a Timeline event ([26](./26_TIMELINE.md)). Fully symmetric and auditable.
- **Conflict awareness:** if the file changed *on disk* since the snapshot (user or external edit), restore warns and shows a diff rather than blindly overwriting the user's own newer change (never silently clobber user work — PR-4 spirit).
- **Atomicity:** multi-file restores are applied atomically-ish (all-or-nothing where the OS allows; otherwise journaled so a crash mid-restore is recoverable).

## 7. Architecture / Data Flow

```
mutating tool.invoke (20) → Kabuk broker (08):
   1. permission (24)
   2. SNAPSHOT: hash target(s) → store before-content in CAS (29) → write Snapshot record
   3. apply mutation (write via temp+rename for atomicity)
   4. Timeline event with snapshotId (26)
restore(snapshotId, scope): permission → write before-content back → new snapshot + event
```

## 8. Grouping with Runs & Agents

- A run ([15](./15_REASONING_ENGINE.md)) or agent tree ([18](./18_AGENT_SYSTEM.md)) accumulates a set of snapshots; the orchestrator can present the entire change set as one reviewable, revertible unit ([06](./06_COMPONENT_LIBRARY.md) §6.4) — "the agent made these 7 edits; accept all / undo all / undo file X."
- This is what makes multi-file agentic editing safe: no matter how many files an agent touched, it's one atomic undo away.

## 9. Retention & Cleanup

- **Retention policy** (configurable, [33](./33_CONFIGURATION.md)): keep snapshots for a recent window / recent runs; older ones are garbage-collected when no longer referenced by retained Timeline events or checkpoints, using CAS refcounting (a blob is deleted only when no snapshot/record references it).
- **User control:** the user can pin important restore points and purge history ([26](./26_TIMELINE.md) purge cascades to orphaned blobs).

## 10. Lifecycle & State

```
mutation about to happen → capture (before) → mutation applied → snapshot durable + linked
restore requested → validate (disk-conflict check) → apply before-content → new snapshot
retention → GC unreferenced blobs (CAS refcount)
```

## 11. Directory Structure

```
anlik/
  snapshot.py     # Snapshot record model + grouping
  capture.py      # capture hook (invoked by broker 08 before mutation)
  restore.py      # single/toolcall/run/baseline restore + conflict check
  gc.py           # CAS refcount + retention GC
# blobs stored via depo/ (29) content-addressed store
```

## 12. Configuration

- Retention window/count, atomic-write strategy, disk-conflict behavior (warn/force), and per-workspace snapshot enable (always-on for mutations; the *only* configurable is retention, not whether to snapshot) live in config ([33](./33_CONFIGURATION.md)). **Snapshotting-before-mutation is not disableable** — it's a safety invariant.

## 13. Dependencies

- [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) (capture hook at broker), [29_STORAGE](./29_STORAGE.md) (CAS blob store + records), [26_TIMELINE](./26_TIMELINE.md) (linking/audit), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) (restore gating), [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) (mutations), [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md) (consistency).

## 14. Edge Cases

- **Crash mid-mutation:** because the snapshot is durable *before* the write, and writes use temp+rename, the file is either the old content or the fully-new content — never corrupt; recovery reconciles ([28](./28_CRASH_RECOVERY.md)).
- **Huge file mutation:** snapshot stores the before-content blob (dedup helps for repeated states); very large files may use chunked/delta storage ([29](./29_STORAGE.md)) to bound cost.
- **New file creation:** snapshot records "did not exist"; undo deletes it.
- **File deleted by a tool:** snapshot stores the deleted content; undo recreates it.
- **User edited the file since the snapshot:** conflict warning + diff on restore (no silent clobber).
- **Binary files:** captured as blobs like any content (dedup still applies).
- **Symlinks / permissions / modes:** file mode captured in the entry; restore reapplies it.
- **Disk full during capture:** the mutation is refused with a typed error *before* any change (safety over action, [38](./38_ERROR_HANDLING.md)).

## 15. Failure Recovery

- Snapshots + the journal ([26](./26_TIMELINE.md)/[28](./28_CRASH_RECOVERY.md)) make every mutation recoverable. If the app crashes after snapshot but before write, no harm (file unchanged). If after write but before the Timeline event, recovery re-links from the durable snapshot record. The user's files are the most protected asset in the system ([01](./01_ARCHITECTURE.md) §15).

## 16. Security

- Snapshots are **local** ([P1]); they can contain sensitive file content, so the blob store is within the private workspace data dir and never egresses; purge is honored. Restore is permissioned ([24](./24_PERMISSION_SYSTEM.md)). Content addressing means no path-based tampering. See [30_SECURITY](./30_SECURITY.md).

## 17. Performance

- Capture cost ≈ hash + store *changed* files only, with dedup → near-free for unchanged content and cheap for typical edits. Temp+rename writes are fast and atomic. GC is background. Large-file delta storage bounds worst case. Metrics in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 18. Testing Strategy

- **Mandatory-capture test:** every mutating tool provably creates a restorable snapshot before writing (assert no mutation path skips it).
- **Round-trip test:** mutate → restore → byte-identical original (incl. mode).
- **Granularity tests:** file/toolcall/run/baseline restores.
- **Conflict test:** external edit since snapshot → warn+diff, no clobber.
- **Crash test:** kill mid-mutation → file consistent (old or new, never corrupt).
- **GC/refcount test:** unreferenced blobs collected; referenced ones retained. See [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- Visual timeline "time-travel" (restore to any point, [26](./26_TIMELINE.md)); selective hunk-level undo; snapshot compression/delta chains; optional VCS-aware snapshots (stash integration); export a change set as a patch.

## 20. Examples

- Agent edits 5 files across a run. User reviews the combined diff ([06](./06_COMPONENT_LIBRARY.md) §6.4), dislikes it, clicks "Bu çalışmayı geri al" → all 5 files restored to their pre-run content atomically, a new snapshot + Timeline event recorded (so the undo is itself undoable).

## 21. Anti-Patterns

- A mutation path that doesn't snapshot first (PR-2/PR-4 violation).
- Snapshotting the whole workspace instead of changed files.
- Restore that silently overwrites a user's newer edit.
- Storing snapshot blobs outside the private workspace data dir.
- Making before-mutation snapshotting optional/disableable.

## 22. Things That Must Never Happen

1. A file mutation occurs without a durable pre-mutation snapshot.
2. A crash leaves a mutated file corrupt/half-written (must be old-or-new).
3. Restore silently clobbers a user's newer change without warning.
4. Snapshot content egresses without consent.
5. Snapshotting-before-mutation is disabled.

## 23. Relationship With Other Subsystems

Triggered by [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) mutations at the [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) broker; stored content-addressed by [29_STORAGE](./29_STORAGE.md); linked/audited by [26_TIMELINE](./26_TIMELINE.md); restore gated by [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); consistency with [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md); grouped by [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)/[18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md); surfaced by [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md); scoped by [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md).

## 24. Migration Considerations

- The snapshot record schema is versioned; additive changes preferred (PR-18). The CAS/hash algorithm (BLAKE3) is fixed project-wide ([29](./29_STORAGE.md)); changing it would be a major migration re-hashing blobs. Delta/compression formats can evolve behind the store interface (PR-8) without breaking existing snapshots.
