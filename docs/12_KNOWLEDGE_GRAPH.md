# 12 — Knowledge Graph (Bilgi Grafı)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `graf/`
> **Related:** [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) · [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) · [14_EMBEDDINGS](./14_EMBEDDINGS.md) · [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md) · [29_STORAGE](./29_STORAGE.md)

---

## 1. Purpose

Defines the **Bilgi Grafı**: a structured graph of **entities** (code symbols, files, modules, concepts, people, decisions) and typed **relations** between them, extracted from the workspace's code, docs, and conversations. It gives the agent *structured* understanding to complement *semantic* retrieval ([13](./13_RAG_SYSTEM.md)) — enabling questions like "who calls this function," "what depends on this module," "which decision led to this design." It is a core enabler of codebase understanding ([00](./00_PROJECT_VISION.md) §6).

## 2. Scope

The graph schema (node/edge types), extraction pipeline, storage/query model, graph-augmented retrieval, incremental updates, and its relationship to memory/RAG. Out of scope: vector retrieval ([13](./13_RAG_SYSTEM.md)), embedding generation ([14](./14_EMBEDDINGS.md)), curated memory ([11](./11_MEMORY_SYSTEM.md), which *links* to graph entities).

## 3. Goals

1. Capture the **structure** of a codebase and project (symbols, deps, ownership, decisions) as a queryable graph.
2. Power **precise, relational** retrieval that pure vector search can't (call graphs, dependency chains, impact analysis).
3. Stay **local, incremental, and fast** — update as files change, never a slow full reparse (PR-14).
4. Be **language-aware but degradable**: rich extraction where a parser exists, heuristic/embedding-based fallback elsewhere (PR-7).
5. Ground memory ([11](./11_MEMORY_SYSTEM.md)) and reasoning ([15](./15_REASONING_ENGINE.md)) in stable entity identities.

### Non-Goals
- Not a general-purpose external graph database service (it's embedded, [29](./29_STORAGE.md)). Not a replacement for RAG — a *complement*.

## 4. Graph Schema

**Node (Varlık) types** (extensible):
- `File`, `Module/Package`, `Function/Method`, `Class/Type`, `Variable/Constant`, `Interface`, `Test`
- `Concept` (domain idea), `Decision` (an architectural choice, e.g., linked to a doc/ADR), `Requirement`, `Person` (author/owner), `ExternalDep` (library), `Config`, `Endpoint/Route`, `Doc` (a docs file).

**Edge (İlişki) types** (typed, directional):
- Code: `defines`, `calls`, `imports`, `depends_on`, `implements`, `extends`, `references`, `tests`, `defined_in`, `member_of`.
- Project: `owns`, `authored`, `decided`, `motivates`, `supersedes`, `documents`, `relates_to`.

**Node properties:** stable `id` (see §5 identity), `name`, `kind`, `location` (file+span), `language`, `signature` (for callables), `summary` (optional model-generated), `embeddingRef` ([14](./14_EMBEDDINGS.md)), `salience`, provenance (`source` into [26](./26_TIMELINE.md)), timestamps.

**Storage:** as relational tables in the Workspace DB ([29](./29_STORAGE.md)) — `nodes`, `edges`, with indexes for traversal; sqlite is sufficient for embedded graph queries (recursive CTEs for traversal). Rationale: no external graph DB → offline, single-file, simple ([P1]). Rejected: Neo4j/embedded graph engines (heavier, weaker offline story).

## 5. Entity Identity (Critical)

Stable identity across edits is what makes the graph (and memory links) durable:
- A symbol's `id` is a deterministic hash of a **qualified, location-independent key** (e.g., `language + normalized-qualified-name + arity`), not its byte offset. Renames/moves are handled as identity-preserving updates where detectable (heuristics: same signature+body hash moving files → move, not delete+add).
- Files identified by workspace-relative path; content changes update `contentHash` (BLAKE3, [29](./29_STORAGE.md)) not identity.
- This determinism (PR-15) lets memory ([11](./11_MEMORY_SYSTEM.md)) and the Timeline reference entities reliably over time.

## 6. Extraction Pipeline

```
file change (workspace watcher, doc 25)
  → language detect
  → PARSE:
       tree-sitter / language parser  → precise symbols & edges (calls/imports/defs)
       (fallback) heuristic + embedding clustering for unsupported languages
  → RESOLVE: link references to definitions; cross-file dep edges
  → SUMMARIZE (optional, budgeted): model-generated node summaries for large/complex nodes
  → EMBED: node embeddings for hybrid retrieval (doc 14)
  → UPSERT: incremental node/edge upsert with identity preservation (§5)
  → EMIT: timeline event; invalidate affected retrieval caches (doc 13)
```

- **Parsing:** tree-sitter grammars (offline, fast, incremental) for the primary supported languages; a pluggable parser interface allows adding languages ([23](./23_PLUGIN_SYSTEM.md)). Where no grammar exists, degrade to import/reference heuristics + embedding-based concept nodes (PR-7).
- **Conversation/decision extraction:** significant decisions and concepts from sessions become `Decision`/`Concept` nodes linked to code and docs (grounding "why" in the graph, complementing memory).
- **Incremental:** only changed files are re-extracted; a dependency-aware invalidation updates affected edges. Full rebuild is always possible from source (§16).

## 7. Graph-Augmented Retrieval

Bilgi Grafı participates in retrieval ([13](./13_RAG_SYSTEM.md) hybrid retrieval):
- **Expansion:** given seed nodes from a vector/keyword hit, traverse edges (calls, depends_on, tests) to pull *structurally* related context the query didn't lexically mention (e.g., include the callee's definition).
- **Impact/scoping queries:** "what breaks if I change X" → reverse `depends_on`/`calls` traversal.
- **Grounding:** provide the reasoning engine with the precise definition + signature of referenced symbols (reduces hallucination).
- **Ranking signal:** graph centrality/proximity is a feature in the reranker ([14](./14_EMBEDDINGS.md) rerank) mix.

## 8. Query Interface (Internal API)

The graph exposes (over the Çekirdek DI, and selectively over the Core Channel for the UI):
- `getNode(id)`, `neighbors(id, edgeTypes, depth, direction)`, `path(a,b)`, `subgraph(seedIds, hops)`.
- `search(text)` → seed nodes (name/keyword) combined with embedding search.
- `impact(id)` → reverse-dependency closure (bounded depth — PR-14).
- Traversals are **bounded** (max depth/breadth) to stay fast and avoid runaway expansion.

## 9. Architecture

```
Workspace files/docs/sessions
   → Extraction pipeline (§6) → nodes/edges (Storage 29) + embeddings (14)
                                     │
 Getirim (13) ◀──── graph expansion/ranking ────┤
 Muhakeme (15) ◀──── grounded symbol lookups ───┤
 Bellek (11) ◀──── entity links / provenance ───┘
 Arayüz (graph explorer, future) ◀── query API
```

## 10. Lifecycle

- **Index build:** on workspace open, an initial extraction runs in the background (progress via events, [10](./10_IPC.md)); the agent is usable with partial graph and improves as it fills.
- **Steady state:** file watcher drives incremental updates ([25](./25_WORKSPACE_SYSTEM.md)).
- **Rebuild:** on schema/parser upgrade or corruption, rebuild from source (§16).

## 11. Configuration

- Supported languages/parsers, summary-generation budget, traversal depth/breadth caps, and whether to extract decisions/concepts are configurable ([33](./33_CONFIGURATION.md)) per effort mode ([17](./17_EFFORT_MODES.md)).

## 12. Dependencies

- tree-sitter (bundled grammars), [14_EMBEDDINGS](./14_EMBEDDINGS.md), [29_STORAGE](./29_STORAGE.md), [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md) (file watching), [26_TIMELINE](./26_TIMELINE.md) (provenance).

## 13. Edge Cases

- **Huge repos:** cap initial extraction breadth; prioritize files by recency/relevance; extract lazily on demand for cold areas (PR-7/PR-14).
- **Unsupported/mixed languages:** heuristic fallback; never fail the whole index because one file can't be parsed.
- **Generated/vendored code:** excluded by default (respect ignore rules, [25](./25_WORKSPACE_SYSTEM.md)); configurable.
- **Rename vs delete+add:** identity heuristics (§5); ambiguous cases err toward preserving links with lowered confidence.
- **Cyclic dependencies:** traversal is cycle-safe (visited set, depth cap).
- **Stale edges after edits:** incremental invalidation keeps edges consistent; a background reconciler catches drift.
- **Turkish identifiers/comments:** the parser and summarizer handle Turkish text correctly (locale, [09](./09_PYTHON_BACKEND.md) `ortak/`).

## 14. Failure Recovery

- Extraction is idempotent and journaled; a crash mid-index resumes ([28](./28_CRASH_RECOVERY.md)).
- A corrupt graph is fully **rebuildable from source** — the user's code is the source of truth; the graph is derived (no user-data loss, [01](./01_ARCHITECTURE.md) §15).

## 15. Security

- Local-only; graph content (which reveals code structure) never egresses without consent ([30](./30_SECURITY.md)).
- Extraction treats file content as data, never executes it. Model-generated summaries are stored as untrusted-origin text (no auto-execution).

## 16. Performance

- Incremental, parser-based extraction; bounded traversals; cached subgraphs. Initial build is backgrounded and progressive. Metrics/budgets in [31_PERFORMANCE](./31_PERFORMANCE.md). Recursive-CTE traversals are indexed; hot queries (`neighbors`, `impact`) are optimized and depth-capped.

## 17. Testing Strategy

- **Extraction correctness** per language (fixtures → expected nodes/edges).
- **Identity stability** across edits/renames/moves (same id preserved).
- **Incremental correctness:** editing a file yields the same graph as a full rebuild of that subset.
- **Traversal bounds:** depth/breadth caps enforced; cycles safe.
- **Rebuild-from-source** parity test. See [35_TESTING](./35_TESTING.md).

## 18. Future Extensions

- Interactive graph explorer UI ([06](./06_COMPONENT_LIBRARY.md)); cross-repo graphs; richer decision/ADR linking; temporal graph (how structure evolved via the Timeline); more languages via plugin parsers ([23](./23_PLUGIN_SYSTEM.md)).

## 19. Examples

- "Bu fonksiyonu değiştirirsem ne kırılır?" → `impact(fn_id)` returns reverse `calls`/`depends_on` closure → reasoning grounds its plan and warns about affected tests (`tests` edges).

## 20. Anti-Patterns

- Byte-offset-based identity (breaks on any edit).
- Full reparse on every change (must be incremental).
- Unbounded graph traversal in a query.
- Requiring an external graph DB (breaks offline).
- Failing the whole index because one file won't parse.

## 21. Things That Must Never Happen

1. Graph content egresses without consent.
2. File content is executed during extraction.
3. A single unparseable file aborts the entire index.
4. Entity identity is unstable across trivial edits (breaks memory/timeline links).
5. A traversal runs unbounded.

## 22. Relationship With Other Subsystems

Complements [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) (structure vs semantics) and shares [14_EMBEDDINGS](./14_EMBEDDINGS.md); provides stable entities for [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) links; grounds [15_REASONING_ENGINE](./15_REASONING_ENGINE.md); fed by [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md) file events; persisted by [29_STORAGE](./29_STORAGE.md); provenance via [26_TIMELINE](./26_TIMELINE.md).

## 23. Migration Considerations

- Schema and parser versions are tracked; a parser/schema upgrade triggers a background rebuild-from-source migration (no user-data risk). Node-id derivation changes are the most sensitive migration (they can break memory links) and require a remap step — treat as major ([44](./44_GLOSSARY.md), [11](./11_MEMORY_SYSTEM.md)).
