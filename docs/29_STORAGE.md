# 29 — Storage (Depolama)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `depo/`
> **Related:** [26_TIMELINE](./26_TIMELINE.md) · [27_SNAPSHOTS](./27_SNAPSHOTS.md) · [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md) · [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) · [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) · [34_API_KEYS](./34_API_KEYS.md)

---

## 1. Purpose

Defines the **Depolama** layer: the on-disk persistence substrate for all durable state — structured data (SQLite), vectors (sqlite-vec), content-addressed blobs (snapshots/artifacts), and the append-only event journal. It specifies the databases, schemas ownership, the blob store, the journal, transactional/durability guarantees, and the hard rules (secrets never here; user code never copied here). It is the foundation every stateful subsystem builds on, and the reason recovery ([28](./28_CRASH_RECOVERY.md)) and reversibility ([27](./27_SNAPSHOTS.md)) are possible.

## 2. Scope

The storage engines and layout, the database taxonomy (App vs Workspace), the content-addressed blob store, the event journal, transactions/durability (WAL), migrations, and backup/portability. Out of scope: what each subsystem stores (their docs), secret storage ([34_API_KEYS](./34_API_KEYS.md) — OS keychain, not here), config file resolution ([33_CONFIGURATION](./33_CONFIGURATION.md)).

## 3. Goals

1. **Embedded, offline, single-file-per-store** persistence — no external DB server (PR-6).
2. **One place, clear ownership**: App DB (global) vs Workspace DB (per project), plus blob store + journal (per workspace).
3. **Durable & transactional** (WAL, fsync where it matters) so crashes don't corrupt ([28](./28_CRASH_RECOVERY.md)).
4. **Deterministic & reproducible** (PR-15): stable IDs, BLAKE3 content addressing, forward-only migrations.
5. **Rebuildable derived state**: indexes/graphs are derived from source and can be dropped/rebuilt; only user files + journal + snapshots + memory are irreplaceable.
6. **Never store secrets or copy the user's whole project** here (hard invariants).

### Non-Goals
- Not a networked/cloud database. Not secret storage. Not a general ORM discussion (that's [36](./36_CODING_STANDARDS.md)).

## 4. Storage Engines

| Engine | Used for | Why |
|---|---|---|
| **SQLite** (WAL mode) | all structured data (App/Workspace DBs, Timeline projection, memory, graph, grants) | embedded, robust, transactional, single-file, offline |
| **sqlite-vec** (extension) | vector store ([14](./14_EMBEDDINGS.md)/[13](./13_RAG_SYSTEM.md)) | vectors *inside* SQLite → one file, offline, no server; hnsw/faiss optional backend for scale ([13](./13_RAG_SYSTEM.md) §6) |
| **SQLite FTS5** | lexical index (Turkish + code analyzers) ([13](./13_RAG_SYSTEM.md) §6) | BM25 keyword search in the same DB |
| **Content-addressed blob store** (filesystem) | snapshots ([27](./27_SNAPSHOTS.md)), large artifacts/outputs | dedup, cheap, streamable; keyed by BLAKE3 |
| **Append-only Event Journal** (files) | timeline write-ahead + recovery ([26](./26_TIMELINE.md)/[28](./28_CRASH_RECOVERY.md)) | durable ordered log, fsync'd |

Rationale for SQLite-centric design: maximal embedded-storage simplicity — everything is local files the user owns, no daemon, trivially backed up. This is a storage-layer property, independent of provider routing (which is cloud-primary with a local offline fallback, [52](./52_ADR_LOG.md) ADR-0010). Rejected: client-server DBs (Postgres) — violates embedded-storage simplicity; a dedicated vector DB service — same.

## 5. Database Taxonomy

- **App DB** (`DATA_DIR/app.db`): global, non-workspace state — settings ([33](./33_CONFIGURATION.md)), provider registry ([21](./21_PROVIDER_SYSTEM.md)), plugin registry + grants ([23](./23_PLUGIN_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md) global grants), `global`-scoped memory ([11](./11_MEMORY_SYSTEM.md)), profile memory. **No secrets** (keychain, [34](./34_API_KEYS.md)).
- **Workspace DB** (`DATA_DIR/alanlar/<id>/workspace.db`): per-project — the vector + lexical index ([13](./13_RAG_SYSTEM.md)), knowledge graph nodes/edges ([12](./12_KNOWLEDGE_GRAPH.md)), workspace-scoped memory ([11](./11_MEMORY_SYSTEM.md)), the Timeline projection ([26](./26_TIMELINE.md)), snapshot records ([27](./27_SNAPSHOTS.md)), workspace permission grants ([24](./24_PERMISSION_SYSTEM.md)).
- **Per-workspace files:** `blobs/` (CAS) and `journal/` (event journal) alongside `workspace.db`.

Isolation between workspaces is physical (separate files) — the storage-layer realization of [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md) §8.

## 6. Content-Addressed Blob Store (CAS)

- Blobs keyed by **BLAKE3** hash (fixed project-wide). Layout: sharded by hash prefix (`blobs/ab/cd/<hash>`). Writing is idempotent (same content → same key, stored once) → dedup ([27](./27_SNAPSHOTS.md) §5).
- **Refcounting:** a small table tracks references (snapshot records, timeline blobRefs); GC deletes a blob only at refcount 0 ([27](./27_SNAPSHOTS.md) §9, [26](./26_TIMELINE.md) §9).
- **Large blobs:** optional chunking/delta storage to bound cost for big files; streamed via the bulk plane ([10](./10_IPC.md) §11), not inlined in JSON.
- Used by the bulk plane as the preferred large-payload transfer mechanism ([01](./01_ARCHITECTURE.md) §6, [10](./10_IPC.md) §11).

## 7. Event Journal

- Append-only, ordered, **fsync'd** write-ahead log ([26_TIMELINE](./26_TIMELINE.md) §5) — the durability substrate for the Timeline and recovery. Segmented files with a durable head pointer; corruption of a tail segment is detectable and truncated to the last valid record (no silent data loss). The SQLite Timeline projection is *derived* from this and rebuildable.

## 8. Transactions & Durability

- **WAL mode** on all SQLite DBs → concurrent reads during writes, atomic commits, crash-safe.
- **Transactions:** multi-row/multi-table changes are wrapped in transactions; a crash yields all-or-nothing ([28](./28_CRASH_RECOVERY.md)).
- **Durability ordering (the critical discipline):** for a side effect, the order is **snapshot(durable) → apply → journal event(durable)**; DB projection updates are async/derived. This ordering (owned by the broker [08]/timeline [26]) is what makes recovery consistent.
- **fsync policy:** fsync on journal appends and snapshot writes (durability-critical); relaxed for the rebuildable projection/indexes (performance) — a deliberate, documented trade ([31](./31_PERFORMANCE.md)).

## 9. Schema Ownership & Access

- Each subsystem owns its tables (namespaced) but **all DB access goes through the `depo/` layer** (repositories/adapters) — no subsystem opens raw SQLite handles or writes SQL scattered around (PR-2/PR-13, one access path). This centralizes migrations, transactions, and the "no secrets" rule.
- Schemas are versioned; the authoritative DDL + migration scripts live in `depo/schema/` (source of truth), aligned with the contract-versioning discipline ([01](./01_ARCHITECTURE.md) §12).

## 10. Migrations

- **Forward-only, versioned, transactional** migrations run at startup when a DB's `schema_version` is behind the app ([33](./33_CONFIGURATION.md)/[07](./07_DESKTOP_ARCHITECTURE.md) §8). Each migration is atomic; a failed migration rolls back and blocks startup with a clear error rather than running on a half-migrated DB (fail-safe).
- **Derived stores** (index/graph/vectors) may be **rebuilt** instead of migrated when the transformation is complex (cheaper + safer than in-place migration, since they're re-derivable — [12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)/[14](./14_EMBEDDINGS.md)).
- Migrations never touch the user's project files and preserve journal/snapshots.

## 11. Directory Structure

```
depo/
  db.py           # SQLite connection mgmt (WAL), repository base
  schema/         # versioned DDL + migration scripts (source of truth)
  repos/          # per-subsystem repositories (memory, graph, index, timeline, grants...)
  vec.py          # sqlite-vec backend (+ hnsw/faiss alt behind an interface, 13)
  fts.py          # FTS5 tr+code analyzers
  blobs.py        # content-addressed store (BLAKE3) + refcount GC
  journal.py      # append-only event journal (fsync) [shared with zaman/ 26]
  migrate.py      # startup migration runner
```
(On-disk layout: [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md) §5, [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md) §4.)

## 12. Configuration

- DB paths (derived from OS dirs, [07](./07_DESKTOP_ARCHITECTURE.md)/[33](./33_CONFIGURATION.md)), WAL/fsync levels, vector backend choice, blob GC policy, and retention hooks ([26](./26_TIMELINE.md)/[27](./27_SNAPSHOTS.md)) are configurable with durable-by-default settings.

## 13. Dependencies

- SQLite + sqlite-vec + FTS5 (bundled, [09](./09_PYTHON_BACKEND.md)), BLAKE3, the OS filesystem. Consumed by essentially every stateful subsystem. Secrets are **not** a dependency here (keychain, [34](./34_API_KEYS.md)).

## 14. Edge Cases

- **Disk full:** writes fail with typed errors *before* claiming success ([38](./38_ERROR_HANDLING.md)); durability ordering (§8) means no corruption; the app degrades to read-only with a clear notice.
- **DB locked/contention:** WAL + a single-writer discipline per DB ([09](./09_PYTHON_BACKEND.md)) minimizes locks; busy-timeout + retry for transient locks.
- **Corrupt projection/index/vector store:** rebuild from source/journal (derived) — no user-data loss.
- **Corrupt journal tail:** truncate to last valid record (detectable via per-record checksums).
- **Blob store orphan/leak:** periodic refcount GC reconciles.
- **Path with spaces/Unicode** (dev root "Turkish Code"): all paths quoted/handled safely ([37](./37_REPOSITORY_STRUCTURE.md)).
- **Multiple processes on the same DB** (multi-window, one-process-per-workspace mode [25]): coordinated by workspace ownership; the single-instance guard prevents competing writers ([07](./07_DESKTOP_ARCHITECTURE.md)).
- **Schema downgrade** (older app opens newer DB): refuse with a clear message (forward-only).

## 15. Failure Recovery

- WAL + transactions + fsync'd journal/snapshots = crash-safe by construction; recovery ([28](./28_CRASH_RECOVERY.md)) relies entirely on these guarantees. Derived stores rebuild; irreplaceable stores (journal, snapshots, memory) are durably written. Safe-mode boot ([07](./07_DESKTOP_ARCHITECTURE.md)/[28](./28_CRASH_RECOVERY.md)) preserves all data for inspection on unrecoverable corruption.

## 16. Security

- **Hard rules:** (1) **no secrets in any DB/blob/journal** — secrets live only in the OS keychain ([34](./34_API_KEYS.md)); a secret scanner + redaction ([26](./26_TIMELINE.md)/[11](./11_MEMORY_SYSTEM.md)) enforce it. (2) **The user's whole project is never copied here** — only derived metadata + *changed*-file snapshots ([07](./07_DESKTOP_ARCHITECTURE.md) §5 invariant). All storage is **local**; optional at-rest encryption of the workspace data dir (OS/user-provided) for extra-sensitive environments. Purge is honored completely (consistent multi-store delete). See [30_SECURITY](./30_SECURITY.md).

## 17. Performance

- WAL for concurrency; indexed projections/queries; batched writes; async projection off the hot path; relaxed fsync for rebuildable stores vs strict for durable ones (§8). Vector search via sqlite-vec ANN (or hnsw for scale). Blob dedup avoids redundant writes. Metrics/budgets in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 18. Testing Strategy

- **Crash/durability tests:** kill during transactions/journal/snapshot writes → no corruption; recovery consistent ([28](./28_CRASH_RECOVERY.md)).
- **Migration tests:** forward migrations atomic; failed migration blocks startup cleanly; rebuild-vs-migrate paths verified.
- **No-secrets test:** scanners assert no secret material in any DB/blob/journal.
- **Isolation test:** workspace DBs are physically separate; no cross-access.
- **GC/refcount correctness.** **Determinism:** same inputs → same IDs/hashes (PR-15). See [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- Optional transparent at-rest encryption; alternative vector backends for very large corpora (hnsw/faiss) behind the existing interface; export/import of a workspace's derived state; compaction tooling; portable single-file workspace archives.

## 20. Examples

- A `fs.write` produces: a durable snapshot blob (BLAKE3) + snapshot record (Workspace DB, txn) → the file write → a fsync'd journal event referencing the snapshot → an async projection row for the Timeline UI. A crash at any point leaves a consistent, recoverable state.

## 21. Anti-Patterns

- Storing secrets/API keys in any DB, blob, or journal.
- Copying the user's whole project into app-data.
- Opening raw SQLite handles / scattering SQL outside `depo/`.
- Trusting a derived projection/index over its source/journal after corruption.
- Backward/destructive migrations.
- Relaxing fsync on the journal/snapshots for speed.

## 22. Things That Must Never Happen

1. A secret is persisted in any DB/blob/journal (keychain only).
2. The user's entire project is copied into app-data.
3. A crash corrupts durable data (transactions/WAL/fsync must prevent it).
4. A migration runs partially/destructively on user-irreplaceable data.
5. Raw DB access bypasses the `depo/` layer and its invariants.

## 23. Relationship With Other Subsystems

Persists for [11](./11_MEMORY_SYSTEM.md)/[12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)/[14](./14_EMBEDDINGS.md)/[24](./24_PERMISSION_SYSTEM.md); provides the journal for [26_TIMELINE](./26_TIMELINE.md) and the CAS for [27_SNAPSHOTS](./27_SNAPSHOTS.md); underpins [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md); realizes [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md) isolation; excludes secrets per [34_API_KEYS](./34_API_KEYS.md); paths per [07_DESKTOP_ARCHITECTURE](./07_DESKTOP_ARCHITECTURE.md); constrained by [30_SECURITY](./30_SECURITY.md).

## 24. Migration Considerations

- Schema versions are per-DB; forward-only, atomic, startup migrations (§10). BLAKE3 CAS and the ID derivation are fixed project-wide (changing them is a major re-hash/re-key migration). Vector-backend swaps are rebuilds behind the interface (PR-8). All migrations preserve user files, journal, and snapshots.
