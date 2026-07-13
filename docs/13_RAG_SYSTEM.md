# 13 — Retrieval System / RAG (Getirim)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `getirim/`
> **Related:** [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) · [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md) · [14_EMBEDDINGS](./14_EMBEDDINGS.md) · [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) · [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md) · [29_STORAGE](./29_STORAGE.md)

---

## 1. Purpose

Defines **Getirim**, the retrieval-augmented pipeline that finds the right pieces of the workspace (code, docs) and memory and assembles them into the reasoning context under a budget. It is what lets the agent answer about a codebase it can't fit in a context window ([00](./00_PROJECT_VISION.md) §6). Getirim is **hybrid**: it fuses vector similarity ([14](./14_EMBEDDINGS.md)), keyword/lexical search, and graph structure ([12](./12_KNOWLEDGE_GRAPH.md)).

## 2. Scope

Ingestion/chunking, indexing, the hybrid retrieval pipeline (retrieve → fuse → rerank → assemble), context assembly under budget, incremental index maintenance, and offline operation. Out of scope: embedding model mechanics ([14](./14_EMBEDDINGS.md)), the graph itself ([12](./12_KNOWLEDGE_GRAPH.md)), curated memory ([11](./11_MEMORY_SYSTEM.md), a *consumer* and *source* of Getirim).

## 3. Goals

1. High-precision retrieval so the reasoning context is relevant, not noisy (garbage-in-garbage-out is the #1 RAG failure).
2. **Hybrid** retrieval: combine semantic (vector), lexical (BM25/keyword — essential for exact identifiers/paths), and structural (graph) signals.
3. **Fully offline** ([P1]): local embeddings + local index; no external retrieval service (PR-6).
4. **Incremental & fast**: update the index as files change; sub-second retrieval (PR-14, [31](./31_PERFORMANCE.md)).
5. **Budget-aware assembly**: fit the most valuable context into the effort budget ([17](./17_EFFORT_MODES.md)).
6. **Turkish-aware** lexical processing (correct tokenization/casing/stemming) alongside code-aware chunking.

### Non-Goals
- Not a cloud vector DB. Not the reasoning loop itself ([15](./15_REASONING_ENGINE.md)). Not memory curation ([11](./11_MEMORY_SYSTEM.md)).

## 4. Pipeline Overview

```
INGEST:  files/docs/memory → chunk → embed (14) → index (vector + lexical) + link (graph 12)
RETRIEVE (per query):
   query → [vector search] ┐
           [lexical/BM25]  ├─▶ FUSE (RRF/weighted) → candidate set
           [graph expand]  ┘
   → RERANK (cross-encoder, doc 14) → top-N
   → ASSEMBLE context (dedupe, order, budget, cite) → to Muhakeme (15)
```

## 5. Ingestion & Chunking

- **Code-aware chunking:** split by syntactic units (functions, classes, blocks) using tree-sitter boundaries from [12](./12_KNOWLEDGE_GRAPH.md), not blind fixed-size windows — a chunk should be a coherent unit. Fallback to sized windows with overlap for unsupported files.
- **Doc/prose chunking:** by headings/paragraphs with overlap; Turkish-aware sentence segmentation.
- **Chunk metadata (Parça):** `id`, `source` (file+span or memory id), `language`, `symbol` (linked graph node id, [12](./12_KNOWLEDGE_GRAPH.md)), `contentHash` (BLAKE3), `tokens`, `embeddingRef` ([14](./14_EMBEDDINGS.md)).
- **What gets indexed:** workspace source + docs, respecting ignore rules ([25](./25_WORKSPACE_SYSTEM.md)); excludes generated/vendored/binary by default. Memory items ([11](./11_MEMORY_SYSTEM.md)) are indexed for semantic recall too.
- **Dedup:** identical `contentHash` chunks are stored once (CAS-aligned, [29](./29_STORAGE.md)).

## 6. Indexing

- **Vector index:** embeddings stored in **sqlite-vec** ([29](./29_STORAGE.md)) for ANN search — embedded, offline, single-file. For very large workspaces, an HNSW index (hnswlib/faiss) is an alternative backend behind the same interface (PR-8, degradation/scaling choice, [31](./31_PERFORMANCE.md)).
- **Lexical index:** SQLite FTS5 (BM25) with a **Turkish-aware analyzer** (correct casing/diacritics/stemming) plus a code-identifier tokenizer (split camelCase/snake_case, keep exact tokens) — critical for finding exact symbols/paths that vectors miss.
- **Graph links:** each chunk references its graph node(s) ([12](./12_KNOWLEDGE_GRAPH.md)) for expansion.
- Indexes live in the **Workspace DB** ([29](./29_STORAGE.md)), per-workspace isolated ([25](./25_WORKSPACE_SYSTEM.md)).

## 7. Retrieval & Fusion

- Run **vector**, **lexical**, and **graph-seed** retrievals in parallel; each returns scored candidates.
- **Fuse** with Reciprocal Rank Fusion (or weighted score fusion) into one candidate set — robust to score-scale differences across retrievers. Weights are effort-mode-tunable ([17](./17_EFFORT_MODES.md)).
- **Graph expansion:** for top candidates, pull structurally-adjacent chunks (callee defs, imported modules) via [12](./12_KNOWLEDGE_GRAPH.md) §7 — recovers context the query didn't name lexically.
- **Filters:** scope (workspace/file/language), recency, and permission/ignore constraints applied here.

## 8. Reranking

- A **cross-encoder reranker** ([14](./14_EMBEDDINGS.md), e.g., NeMo Retriever reranker or a local reranker) re-scores the fused candidates against the exact query for final precision. This step is the biggest precision lever.
- Reranking is **budget-gated**: skipped or shrunk under `Hızlı` effort; full under `Derin/Maksimum` ([17](./17_EFFORT_MODES.md)). Degrades to fusion-only ordering if no reranker is available (PR-7).

## 9. Context Assembly (Bağlam Kurulumu)

The final, crucial step that builds what the model actually sees:
- **Dedupe & merge** overlapping chunks; collapse adjacent chunks from the same file into contiguous spans.
- **Order** for the model: most-relevant and structurally-foundational first; group by file for coherence.
- **Budget:** fit within the retrieval slice of the effort budget ([17](./17_EFFORT_MODES.md)) — token-count each chunk ([14](./14_EMBEDDINGS.md) tokenizer) and greedily pack by value/token.
- **Cite:** every included chunk carries its `source` so the reasoning trace ([15](./15_REASONING_ENGINE.md)) and UI can show provenance ("bu yanıt şu dosyalara dayanıyor") — supports P4 auditability and reduces hallucination.
- **Combine sources:** assembled context interleaves retrieved code/docs with recalled memory ([11](./11_MEMORY_SYSTEM.md)) and graph facts ([12](./12_KNOWLEDGE_GRAPH.md)), each labeled by origin.

## 10. Incremental Maintenance

- The workspace watcher ([25](./25_WORKSPACE_SYSTEM.md)) drives re-chunk + re-embed + re-index of only changed files (by `contentHash` diff); unchanged chunks (same hash) are reused (no wasted embedding — [14](./14_EMBEDDINGS.md) cache).
- A background reconciler repairs drift; a full rebuild is always available from source (§14).

## 11. Architecture / Directory

```
getirim/
  ingest/     chunkers (code via tree-sitter, prose), ignore rules
  index/      vector (sqlite-vec/hnsw backend iface), lexical (FTS5 tr+code analyzer)
  retrieve/   vector, lexical, graph-seed retrievers + fusion
  rerank/     reranker adapter (provider, doc 21/22)
  assemble/   dedupe, order, budget-pack, cite
  cache/      embedding + result caches
```

## 12. Configuration

- Chunk sizes/overlap, fusion weights, top-K per retriever, rerank depth, assembly budget, index backend (sqlite-vec vs hnsw), and language analyzers are configurable ([33](./33_CONFIGURATION.md)) and effort-mode-scaled ([17](./17_EFFORT_MODES.md)).

## 13. Dependencies

- [14_EMBEDDINGS](./14_EMBEDDINGS.md) (embed + rerank models), [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md) (chunk boundaries + expansion), [29_STORAGE](./29_STORAGE.md) (sqlite-vec + FTS5), [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md) (watch + ignore), [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)/[22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md) (model backends).

## 14. Edge Cases

- **Exact-identifier queries** (a function name, a path): lexical retriever must catch these even when vectors don't — the hybrid design exists for this.
- **Very large files / monorepos:** chunk lazily; cap per-file chunks; prioritize by graph salience/recency.
- **Binary/minified/generated files:** excluded by default.
- **Query in mixed Turkish/English/code:** analyzers handle each; the code tokenizer preserves identifiers verbatim.
- **Empty/cold index** (fresh workspace): retrieval degrades to whatever is indexed so far while the background build progresses ([12](./12_KNOWLEDGE_GRAPH.md) §10) — usable immediately, better over time.
- **No reranker / low effort:** fusion-only ordering (PR-7).
- **Corrupt vector store:** rebuild from source; lexical + graph still serve in the meantime.
- **Stale chunks after edit:** hash-diff invalidation prevents serving outdated code.

## 15. Failure Recovery

- Index build is journaled/idempotent; resumes after crash ([28](./28_CRASH_RECOVERY.md)).
- Any index is **derived and rebuildable from the user's source** — never a source of user-data loss ([01](./01_ARCHITECTURE.md) §15).

## 16. Security

- Fully local; retrieved content (code) never egresses without consent ([30](./30_SECURITY.md)). Ignore rules keep secrets/`.env`/excluded paths **out** of the index by default ([25](./25_WORKSPACE_SYSTEM.md), [34](./34_API_KEYS.md)). Indexed content is data, never executed. When a cloud provider is used for embeddings/rerank, that egress is consent-gated and made explicit ([21](./21_PROVIDER_SYSTEM.md), [32](./32_OFFLINE_FIRST.md)) — the default local embedder avoids it entirely.

## 17. Performance

- Parallel retrievers, ANN vector search, FTS5 lexical, bounded top-K, cached embeddings/results. Target sub-second retrieval on typical workspaces ([31](./31_PERFORMANCE.md)). Reranking is the main latency knob, gated by effort mode.

## 18. Testing Strategy

- **Retrieval quality** on labeled fixtures (relevant chunk in top-K) across semantic, exact-identifier, and structural queries.
- **Hybrid-fusion tests** (exact-match queries must surface via lexical even when vectors fail).
- **Incremental parity** (edit → same result as rebuild).
- **Budget/assembly tests** (never exceed budget; citations present).
- **Offline test** (full pipeline with local embedder + no network). See [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- Learned fusion weights; query rewriting/HyDE (budgeted); multi-vector/late-interaction retrieval; retrieval over external docs the user explicitly imports; per-language specialized chunkers via plugins ([23](./23_PLUGIN_SYSTEM.md)).

## 20. Examples

- Query "auth token nasıl doğrulanıyor?": lexical finds `verifyToken`, vector finds semantically-related middleware, graph expands to callers and the config that sets the secret → assembled, cited context → grounded answer.

## 21. Anti-Patterns

- Vector-only retrieval (misses exact identifiers).
- Blind fixed-size chunking that splits functions mid-body.
- Flooding the context with low-value chunks (kills precision + budget).
- Re-embedding unchanged content (must cache by hash).
- Indexing secrets/ignored paths.
- Assembling context without citations/provenance.

## 22. Things That Must Never Happen

1. Retrieval requires a network service to function (must be fully local by default).
2. Ignored/secret files are indexed and surfaced.
3. Assembled context exceeds the effort budget.
4. An index becomes a source of user-data loss (it must be rebuildable from source).
5. Included context lacks provenance for auditability.

## 23. Relationship With Other Subsystems

Consumes [14_EMBEDDINGS](./14_EMBEDDINGS.md) and [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md); serves [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) context and [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) recall; fed by [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md); persisted by [29_STORAGE](./29_STORAGE.md); budgeted by [17_EFFORT_MODES](./17_EFFORT_MODES.md); model backends via [21](./21_PROVIDER_SYSTEM.md)/[22](./22_PROVIDER_INTEGRATIONS.md).

## 24. Migration Considerations

- Chunking strategy or embedding-model changes require a re-index migration ([14](./14_EMBEDDINGS.md)); done in background from source. Index backend swaps (sqlite-vec ↔ hnsw) are behind the retriever interface (PR-8) and are a rebuild, not a data-loss event.
