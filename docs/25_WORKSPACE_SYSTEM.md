# 25 — Workspace System (Çalışma Alanı)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `calisma_alani/` + Kabuk (fs access)
> **Related:** [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md) · [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) · [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) · [29_STORAGE](./29_STORAGE.md) · [26_TIMELINE](./26_TIMELINE.md) · [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md)

---

## 1. Purpose

Defines **Çalışma Alanı**, the workspace model: a project root the agent operates on, together with its **isolated** derived state — index ([13](./13_RAG_SYSTEM.md)), knowledge graph ([12](./12_KNOWLEDGE_GRAPH.md)), memory scope ([11](./11_MEMORY_SYSTEM.md)), timeline ([26](./26_TIMELINE.md)), snapshots ([27](./27_SNAPSHOTS.md)), config, and permission grants ([24](./24_PERMISSION_SYSTEM.md)). The workspace is the unit of isolation that keeps one project's data, memory, and grants from bleeding into another, and it owns file discovery/watching/ignore rules that feed every knowledge subsystem.

## 2. Scope

The workspace identity/lifecycle, the per-workspace data layout, file discovery + ignore rules + watching, the workspace↔session↔process mapping, multi-workspace isolation, and indexing coordination. Out of scope: how each derived store works internally (their docs), storage formats ([29](./29_STORAGE.md)).

## 3. Goals

1. **Strong isolation** between projects: data, memory, grants, and index are per-workspace by default (privacy + correctness, PR-3/PR-12 spirit).
2. A single, authoritative **file discovery + ignore** policy feeding index/graph/RAG (one source of truth).
3. **Incremental awareness**: watch the project for changes and keep derived state fresh ([12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)).
4. **Non-invasive**: never move/copy the user's project into app-data; store only derived metadata elsewhere ([07](./07_DESKTOP_ARCHITECTURE.md) §5 invariant).
5. Clear **workspace↔session↔process** semantics for multi-window use.

### Non-Goals
- Not version control (it *reads* VCS ignore rules but isn't a VCS). Not remote/cloud project hosting.

## 4. Workspace Identity & Data Layout

- A workspace = a **project root path** + a stable **workspace id** (derived from a canonical path hash; survives reopen). If the project moves, the id can be re-bound to the new path (a tracked rebind).
- **Derived state layout** (in app DATA_DIR, not in the project — [07](./07_DESKTOP_ARCHITECTURE.md) §5):

```
DATA_DIR/alanlar/<workspace-id>/
   workspace.db     # index (13) + graph (12) + workspace memory (11) + grants (24)
   blobs/           # content-addressed snapshots (27) & large artifacts (29)
   journal/         # event journal → timeline (26) + crash recovery (28)
   config.toml      # workspace-level config overrides (33)
```

- The **user's project files stay in place**; only derived data lives here. This is a hard invariant ([00](./00_PROJECT_VISION.md), [07](./07_DESKTOP_ARCHITECTURE.md)).

## 5. File Discovery & Ignore Rules (One Source of Truth)

- A single discovery module enumerates workspace files and applies a layered **ignore policy** consumed by index/graph/RAG/tools alike (no subsystem re-implements ignoring):
  1. VCS ignores (`.gitignore` etc.).
  2. A project `.turkishcodeignore` (optional).
  3. Built-in defaults: binaries, `node_modules`, build outputs, large media, and — importantly — **secret-bearing files** (`.env`, key files) excluded from indexing by default ([13](./13_RAG_SYSTEM.md) §16, [34](./34_API_KEYS.md)).
- Ignore rules are **security-relevant** (they keep secrets out of the index/graph) and are surfaced/configurable so users can verify what's indexed ([30](./30_SECURITY.md)).

## 6. File Watching & Incremental Updates

- A file watcher observes the project and emits change events (create/modify/delete/rename) that drive incremental re-extraction in the graph ([12](./12_KNOWLEDGE_GRAPH.md) §6) and re-indexing in RAG ([13](./13_RAG_SYSTEM.md) §10), keyed by content hash to avoid redundant work.
- Watching is debounced/batched (editors write rapidly); large bulk changes (branch switch) trigger a batched reconcile rather than per-file thrash (PR-14).
- Reads of user files (by the watcher/discovery) are **brokered/permissioned** like any fs access ([24](./24_PERMISSION_SYSTEM.md)/[20](./20_TOOL_SYSTEM.md)) — the workspace scope grants `fs.read` within the root by default.

## 7. Workspace ↔ Session ↔ Process Mapping

- **Window ↔ Workspace:** each open workspace has its own window ([07](./07_DESKTOP_ARCHITECTURE.md) §7).
- **Workspace ↔ Session:** a workspace hosts one active session (conversation + reasoning + edits) at a time (with history); sessions are workspace-scoped ([15](./15_REASONING_ENGINE.md)/[28](./28_CRASH_RECOVERY.md)).
- **Process model (canonical decision):** **one Çekirdek process** serves all open workspaces, with **strict per-workspace isolation** — separate DBs, journals, memory scope, and grants; a session's `meta.workspaceId` ([10](./10_IPC.md)) selects the isolated context. An **optional** one-process-per-workspace mode exists for heavy isolation needs (enterprise/air-gapped multi-project), configurable ([33](./33_CONFIGURATION.md)). Rationale: shared process saves memory/model-load; isolation is enforced at the data layer, not the process layer, and validated by tests (§16). (Referenced from [01](./01_ARCHITECTURE.md) §14, [07](./07_DESKTOP_ARCHITECTURE.md) §7.)

## 8. Isolation Guarantees

- **Data:** workspace DBs/journals/blobs are separate files; no shared tables across workspaces.
- **Memory:** `workspace`-scoped memory ([11](./11_MEMORY_SYSTEM.md)) is confined; only `global` memory is shared — enforced by scope filters and tested.
- **Grants:** permission grants ([24](./24_PERMISSION_SYSTEM.md)) are per-workspace (except explicit `global` grants).
- **Index/graph:** never cross-referenced across workspaces.
- This isolation is a correctness + privacy property (a fintech and a hobby project must not share memory/index).

## 9. Lifecycle & State Machine

```
[Closed] --open(path)--> [Opening] --(discover+bind id+open DBs)--> [Indexing] --initial build done--> [Ready]
   ▲                                                                     │ (watcher keeps it fresh)
   │                                                                     ▼
   └──────────────────── close (flush/checkpoint) ───────────────── [Ready] ⇄ (steady state)
On open with a recoverable session → offer resume (28).
```

- **Open:** validate path, bind id, open workspace.db/journal, start watcher, kick off background initial index/graph build (usable immediately, improves as it fills — [12](./12_KNOWLEDGE_GRAPH.md) §10, [13](./13_RAG_SYSTEM.md) §14).
- **Close:** stop watcher, flush/checkpoint journals ([28](./28_CRASH_RECOVERY.md)), close DBs.

## 10. Directory Structure

```
calisma_alani/
  workspace.py    # identity, lifecycle, open/close, id binding
  discover.py     # file enumeration + ignore policy (one source of truth)
  watch.py        # file watcher + debounce/batch
  scope.py        # isolation: DB/memory/grant scoping per workspace
  index_coord.py  # coordinates graph (12) + rag (13) (re)build on changes
```

## 11. Configuration

- Per-workspace config overrides ([33](./33_CONFIGURATION.md)): ignore additions, indexing scope/limits, effort defaults, provider/model pins, permission defaults, and process-isolation mode. Global config provides defaults.

## 12. Dependencies

- [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md)/[13_RAG_SYSTEM](./13_RAG_SYSTEM.md) (consumers of file events), [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) (scope), [29_STORAGE](./29_STORAGE.md) (per-workspace DBs/blobs/journal), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md) (grants), [26_TIMELINE](./26_TIMELINE.md)/[28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md), [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md) (brokered fs).

## 13. Edge Cases

- **Project moved/renamed on disk:** detect stale binding; offer rebind (preserve derived state) or reindex.
- **Huge monorepo:** bounded initial indexing + lazy cold-area extraction ([12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)); configurable scope.
- **Symlinks / files outside the root:** confined to the root by default; following out-of-root symlinks requires an explicit grant ([24](./24_PERMISSION_SYSTEM.md)).
- **Same project opened twice:** single-instance/workspace guard focuses the existing window ([07](./07_DESKTOP_ARCHITECTURE.md)).
- **Spaces/Unicode in path** (recall the dev root "Turkish Code"): path handling is space/Unicode-safe ([37](./37_REPOSITORY_STRUCTURE.md)).
- **`.env`/secret files present:** excluded from indexing by default (§5); user is informed.
- **Rapid mass file changes (git checkout):** batched reconcile, not per-file storms.
- **Deleted project directory while open:** graceful degrade to read-only of derived state + a clear notice; never lose the journal/snapshots.

## 14. Failure Recovery

- Workspace DBs/journals are the crash-recovery substrate ([28](./28_CRASH_RECOVERY.md)); derived index/graph are rebuildable from source if corrupt ([12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)) — no user-code loss. Snapshots ([27](./27_SNAPSHOTS.md)) protect any agent edits.

## 15. Security

- Ignore policy keeps secrets out of the index/graph (§5, [30](./30_SECURITY.md)). fs access is confined to the workspace root and brokered/permissioned ([24](./24_PERMISSION_SYSTEM.md)). Cross-workspace isolation prevents data bleed (§8). No project data egresses ([P1]).

## 16. Testing Strategy

- **Isolation tests:** memory/index/grants never leak across workspaces (the marquee test).
- **Ignore-policy tests:** secrets/binaries/build outputs excluded; one policy honored by all consumers.
- **Incremental-freshness tests:** edits reflected in graph/RAG; hash-diff avoids redundant work.
- **Rebind tests:** moved project preserves derived state.
- **Confinement tests:** out-of-root access denied without grant. See [35_TESTING](./35_TESTING.md).

## 17. Performance

- Backgrounded initial index; debounced watching; hash-diff incrementalism; bounded scope on huge repos ([31](./31_PERFORMANCE.md)). Shared-process model saves model memory across workspaces (§7).

## 18. Future Extensions

- Multi-root workspaces; workspace templates; per-workspace agent presets ([18](./18_AGENT_SYSTEM.md)); optional VCS-aware features (branch-scoped memory/snapshots); remote workspace mounts (LAN) preserving isolation + consent.

## 19. Examples

- Opening `~/proje/fintech` binds workspace id, opens its isolated `workspace.db`, indexes it (excluding `.env`, `dist/`), and starts watching. Opening `~/proje/hobi` in another window gets a *completely separate* memory/index/grant set — no bleed.

## 20. Anti-Patterns

- Copying the project into app-data.
- Re-implementing ignore logic per subsystem (must be one source).
- Sharing memory/index/grants across workspaces.
- Following symlinks out of the root without a grant.
- Per-file re-index storms on bulk changes.

## 21. Things That Must Never Happen

1. A workspace's memory/index/grants leak into another workspace.
2. Secret-bearing files are indexed by default.
3. The user's project files are moved/copied into app-data.
4. fs access escapes the workspace root without an explicit grant.
5. Derived-state corruption causes loss of the user's source or journaled history.

## 22. Relationship With Other Subsystems

Feeds [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md)/[13_RAG_SYSTEM](./13_RAG_SYSTEM.md) with files+events; scopes [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) and [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); persists via [29_STORAGE](./29_STORAGE.md) into per-workspace DBs/journals; hosts sessions for [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)/[28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md); fs brokered by [08_TAURI_ARCHITECTURE](./08_TAURI_ARCHITECTURE.md); windows per [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md).

## 23. Migration Considerations

- Workspace data-layout is versioned; a layout change ships a per-workspace migrator ([29](./29_STORAGE.md)). Changing the process-isolation mode is a config change (no data migration). Ignore-policy defaults evolve additively; tightening (excluding more) is safe, loosening requires care ([30](./30_SECURITY.md)).
