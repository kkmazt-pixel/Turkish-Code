# 28 — Crash Recovery (Kurtarma)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `kurtarma/` + Kabuk supervisor
> **Related:** [26_TIMELINE](./26_TIMELINE.md) · [27_SNAPSHOTS](./27_SNAPSHOTS.md) · [29_STORAGE](./29_STORAGE.md) · [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) · [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)

---

## 1. Purpose

Defines **Kurtarma**, how turkish.code survives crashes (of any tier or the whole app) and **resumes in-flight work exactly where it left off** — the reliability promise of Pillar P5 and success criterion #4 ([00](./00_PROJECT_VISION.md) §8). It ties together the durable substrates — the Event Journal ([26](./26_TIMELINE.md)), Snapshots ([27](./27_SNAPSHOTS.md)), and session **Checkpoints** — into a coherent recovery story so a power loss or process crash never destroys work.

## 2. Scope

The checkpoint model (distinct from snapshots), crash detection & supervised restart, session resume, consistency reconciliation after interrupted side effects, and the recovery UX. Out of scope: the journal itself ([26](./26_TIMELINE.md)), file snapshots ([27](./27_SNAPSHOTS.md)), storage durability mechanics ([29](./29_STORAGE.md)), supervisor mechanics ([08](./08_TAURI_ARCHITECTURE.md) §8).

## 3. Goals

1. **No lost work**: any in-flight session/run is resumable after a crash (P5).
2. **No corruption**: interrupted mutations leave files consistent (old-or-new, via [27](./27_SNAPSHOTS.md)); interrupted DB writes are transactional ([29](./29_STORAGE.md)).
3. **Automatic where safe, user-confirmed where judgment is needed**: resume seamlessly for pure reasoning; ask before re-running side-effecting steps.
4. **Fast, bounded recovery** — no long rebuild on every launch.
5. Recovery works **offline** ([P1]) — everything needed is local.

### Non-Goals
- Not undo of user actions ([27](./27_SNAPSHOTS.md)). Not backup/DR of the whole machine. Not preventing model errors (that's reasoning/permissions).

## 4. The Three Durable Substrates (Recap of the Division)

Recovery composes three things, each owned elsewhere:

| Substrate | Captures | Owner |
|---|---|---|
| **Event Journal** | everything that happened (ordered, fsync'd) | [26_TIMELINE](./26_TIMELINE.md) |
| **Snapshots** | file state before each mutation (undo) | [27_SNAPSHOTS](./27_SNAPSHOTS.md) |
| **Checkpoints** | resumable *session/run state* (plan, loop position, budget, agent tree) | this doc |

A **Checkpoint** is session/reasoning state; a **Snapshot** is files. Never conflate them ([44](./44_GLOSSARY.md) §12).

## 5. Checkpoint Model

```
Checkpoint {
  id, sessionId, runId, ts, seq(aligned to timeline 26)
  reasoningState: { loopPhase, plan, pendingToolCall?, reflectionCount }  // 15
  agentTree?: {...}          // 18 (orchestrator + sub-agent states)
  budgetRemaining: {...}     // 17 effort meter
  contextRef                 // assembled context ref (rebuildable) 13
  status: active|awaiting_tool|awaiting_permission|done|failed|cancelled
}
```

- Checkpoints are written at every reasoning transition ([15](./15_REASONING_ENGINE.md) §9) and before/after each tool call, into the durable journal ([29](./29_STORAGE.md)). They are small (state, not data — big context is a rebuildable ref).
- The **last checkpoint + the journal tail** fully determine how to resume.

## 6. Crash Detection & Restart

- **Çekirdek crash:** the Kabuk supervisor detects it (missed heartbeat / pipe EOF, [08](./08_TAURI_ARCHITECTURE.md) §8) → restarts with backoff → the restarted Çekirdek reads the journal/checkpoints and enters recovery.
- **Kabuk/whole-app crash or power loss:** on next launch, the app scans workspaces for sessions whose last checkpoint status is non-terminal (`active`/`awaiting_*`) → offers recovery.
- **WebView crash/reload:** not a real crash — the Arayüz just rehydrates and resumes streaming from last `seq` ([03](./03_UI_SYSTEM.md) §6.3, [10](./10_IPC.md) §8); Çekirdek state was never lost.

## 7. Resume Algorithm

```
on recovery for a session:
 1. Load last Checkpoint + replay journal tail (26) to reconstruct in-memory state.
 2. RECONCILE interrupted side effects:
      • last op was a mutating tool that snapshotted but maybe didn't finish (27):
          - inspect file vs snapshot before/after → file is old OR new (never corrupt)
          - if old: the write didn't commit → the step is "not done" → safe to retry
          - if new: the write committed but the result/event may be missing → re-link, mark done
      • last op was awaiting_permission → re-raise the permission prompt (24)
      • last op was a provider call (21) → it's idempotent to re-issue (model call) → retry
 3. Decide resume vs confirm:
      • pure reasoning/read steps → resume automatically
      • a side-effecting step that may or may not have applied → CONFIRM with the user
        (show what will be re-done; never silently re-run a destructive action)
 4. Continue the reasoning loop (15) from the reconstructed state, with remaining budget (17).
```

- **Idempotency & safety:** the reconciliation exploits that (a) mutations are snapshot-bracketed and atomic ([27](./27_SNAPSHOTS.md)), (b) DB writes are transactional ([29](./29_STORAGE.md)), and (c) the journal records intent before effect ([26](./26_TIMELINE.md) §14). So there's always a consistent point to resume from, and ambiguous side effects are surfaced, not blindly repeated (PR-4).

## 8. Recovery UX

- On launch with recoverable sessions, the `KurtarmaEkrani` ([06](./06_COMPONENT_LIBRARY.md) §6.10) shows: which workspace/session, what was in flight (from the trace [15]/[26]), and options: **Devam et** (resume), **İncele** (inspect the trace/edits first), **Yoksay** (discard, keeping the audit trail). Nothing is auto-executed for side-effecting steps without a choice.
- For a mid-run Çekirdek restart (no whole-app crash), resume is seamless and the user just sees a brief "beyin yeniden başlatıldı, devam ediliyor" state.

## 9. State Machine (Recovery)

```
[Detect] → [LoadCheckpoint+ReplayJournal] → [Reconcile] →
    ├─ pure/safe → [AutoResume] → (back into 15's loop)
    └─ ambiguous side effect → [AwaitUserConfirm] → [Resume|Discard]
Failure to reconstruct → [SafeMode] (surface diagnostics; never destroy data)
```

## 10. Directory Structure

```
kurtarma/
  checkpoint.py   # checkpoint model + write at transitions (15)
  detect.py       # scan for recoverable sessions on boot
  reconcile.py    # reconcile interrupted side effects (27/29/26)
  resume.py       # rebuild state + continue the loop (15)
```

## 11. Configuration

- Checkpoint frequency (default: every transition), auto-resume policy for safe steps, and recovery prompt behavior are configurable ([33](./33_CONFIGURATION.md)); defaults favor safety (confirm side-effecting resumes).

## 12. Dependencies

- [26_TIMELINE](./26_TIMELINE.md) (journal), [27_SNAPSHOTS](./27_SNAPSHOTS.md) (file consistency), [29_STORAGE](./29_STORAGE.md) (transactional durability), [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) (supervisor), [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)/[18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) (state to checkpoint), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) (re-prompt), [17_EFFORT_MODES](./17_EFFORT_MODES.md) (remaining budget).

## 13. Edge Cases

- **Crash during a multi-file agent run ([18](./18_AGENT_SYSTEM.md)):** the agent-tree checkpoint + per-call snapshots let recovery resume incomplete sub-tasks; completed edits are intact and revertible ([27](./27_SNAPSHOTS.md)).
- **Repeated crash on resume (poison run):** after N failed resume attempts, offer discard-with-audit and enter safe mode — never crash-loop the user (bounded, PR-14/PR-7).
- **Journal readable but checkpoint corrupt (or vice versa):** rebuild the missing one from the other where possible; if neither, safe mode with the audit trail preserved.
- **Version upgrade between crash and relaunch:** checkpoint/journal schema migration runs first ([29](./29_STORAGE.md)/[26](./26_TIMELINE.md)); if a checkpoint can't be migrated, resume degrades to "inspect + restart the task" rather than corrupt resume.
- **Interrupted DB write:** SQLite WAL + transactions guarantee atomicity ([29](./29_STORAGE.md)) — no half-written rows.
- **Disk full at crash time:** journal fsync discipline means the last durable state is consistent; recovery works from it.
- **User declines resume:** discard cleanly; audit trail ([26](./26_TIMELINE.md)) and snapshots ([27](./27_SNAPSHOTS.md)) remain for review/undo.

## 14. Failure Recovery (of Recovery Itself)

- Recovery is idempotent and re-runnable. Its worst case is **safe mode**: the app boots, shows diagnostics, and preserves all durable data (journal/snapshots/DBs) untouched so the user (or support) can inspect — it never "fixes" by deleting user-relevant data ([01](./01_ARCHITECTURE.md) §15).

## 15. Security

- Recovery reads only local durable state ([P1]); no egress. Re-raising a permission prompt on resume ensures a crash can't be used to bypass consent ([24](./24_PERMISSION_SYSTEM.md)) — an `awaiting_permission` step re-asks, never auto-allows. Redaction in the journal ([26](./26_TIMELINE.md)) means recovery never surfaces raw secrets. See [30_SECURITY](./30_SECURITY.md).

## 16. Performance

- Checkpoints are small and cheap (state refs, not data); recovery replays only the journal *tail* since the last checkpoint (bounded), not the whole history → fast launch even for long histories. No full re-index on normal recovery (derived stores persist; only corrupt ones rebuild, [13](./13_RAG_SYSTEM.md)). Metrics in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 17. Testing Strategy

- **Fault-injection (marquee):** kill the Çekirdek/app at every phase (before/after snapshot, before/after write, before/after event, mid-tool, mid-agent-tree) → assert consistent recovery, no corruption, correct resume/confirm.
- **Idempotency:** resume twice → same result.
- **Poison-run bound:** repeated resume failure → safe discard, no loop.
- **Consent-on-resume:** `awaiting_permission` re-prompts, never auto-allows.
- **Migration-across-crash test.** See [35_TESTING](./35_TESTING.md).

## 18. Future Extensions

- Continuous background checkpointing for very long runs; cross-device session handoff (explicitly consented, [P1]-respecting); richer recovery diffing; automatic root-cause capture for crash reports (local-only).

## 19. Examples

- Power loss while the agent is on edit 4 of 7: on relaunch, `KurtarmaEkrani` shows the in-flight task; reconciliation finds edits 1–3 committed (snapshots intact), edit 4's write didn't commit (file == before-snapshot) → resume re-attempts edit 4 and continues 5–7, all still revertible.

## 20. Anti-Patterns

- Auto-re-running a destructive/side-effecting step on resume without confirmation.
- Treating a WebView reload as a crash (it isn't — just rehydrate).
- "Fixing" corruption by deleting user-relevant data.
- Replaying the entire journal on every launch (must checkpoint + tail-replay).
- Auto-allowing a permission that was pending at crash time.

## 21. Things That Must Never Happen

1. In-flight work is lost after a crash (must be resumable).
2. An interrupted mutation leaves a file corrupt (must be old-or-new).
3. A pending permission auto-resolves to allow on resume.
4. Recovery deletes/overwrites the user's source or audit trail to "recover."
5. The app crash-loops on an unrecoverable session (must reach safe mode).

## 22. Relationship With Other Subsystems

Composes [26_TIMELINE](./26_TIMELINE.md) (journal), [27_SNAPSHOTS](./27_SNAPSHOTS.md) (files), and [29_STORAGE](./29_STORAGE.md) (transactions); driven by the [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) supervisor; restores [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)/[18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) state with [17_EFFORT_MODES](./17_EFFORT_MODES.md) budget; re-prompts via [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); UX via [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md); scoped per [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md).

## 23. Migration Considerations

- Checkpoint schema is versioned alongside the journal ([26](./26_TIMELINE.md)); migrations run before recovery. Unmigratable checkpoints degrade to inspect-and-restart (never corrupt resume). The reconciliation logic is the most safety-critical code path here and changes require the full fault-injection suite (§17) to pass.
