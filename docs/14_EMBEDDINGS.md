# 14 — Embeddings (Gömme)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `gomme/`
> **Related:** [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) · [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md) · [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) · [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md) · [29_STORAGE](./29_STORAGE.md)

---

## 1. Purpose

Defines **Gömme**: how turkish.code turns text (code, docs, queries, memory) into dense vectors, and how it reranks candidates. Embeddings are the numeric substrate of semantic retrieval ([13](./13_RAG_SYSTEM.md)), memory recall ([11](./11_MEMORY_SYSTEM.md)), graph similarity ([12](./12_KNOWLEDGE_GRAPH.md)), and dedup. This document owns the embedding model contract, dimensions/normalization, batching/caching, the reranker, and the model-versioning/migration story — the concerns that, if wrong, silently corrupt retrieval.

## 2. Scope

Embedding model interface, input preparation (tokenization, Turkish/code handling), dimension/normalization/distance conventions, batching, caching, reranking, offline model management, and re-embedding migrations. Out of scope: the retrieval pipeline ([13](./13_RAG_SYSTEM.md)), vector storage internals ([29](./29_STORAGE.md)), provider transport ([21](./21_PROVIDER_SYSTEM.md)/[22](./22_PROVIDER_INTEGRATIONS.md)).

## 3. Goals

1. **Local, offline-capable** embeddings by default ([P1], PR-6) — no network required to index or retrieve.
2. A **Turkish-and-code-aware** embedding stack (strong on Turkish text and on source code).
3. **Deterministic, versioned** embeddings so the vector store stays coherent (PR-15); model changes trigger controlled re-embedding.
4. **Fast & batched**, GPU-accelerated when available ([22](./22_PROVIDER_INTEGRATIONS.md)), CPU fallback (PR-7).
5. A **reranker** for final-stage precision ([13](./13_RAG_SYSTEM.md) §8).

### Non-Goals
- Not the retrieval logic. Not a cloud-only embedding dependency (cloud is opt-in acceleration, [21](./21_PROVIDER_SYSTEM.md)).

## 4. The Embedding Contract

`gomme/` exposes a provider-backed interface (implemented per [21](./21_PROVIDER_SYSTEM.md)):

```
Embedder {
  id: string                 // model identity, e.g. "nemo-retriever-e5-tr" / "bge-m3-local"
  dim: int                   // vector dimension (fixed per model)
  maxTokens: int             // input truncation limit
  normalize: bool            // L2-normalized outputs (see §6)
  embed(texts, kind) -> [vector]   // kind ∈ {document, query} (asymmetric models)
  tokenCount(text) -> int
}
Reranker {
  id: string
  rerank(query, candidates) -> [scoredCandidate]
}
```

- **Asymmetric models:** many retrieval embedders use different prefixes/encoders for `document` vs `query`; the `kind` argument is mandatory so we never mix them (a classic silent-quality bug). Getirim passes `query` at search time and `document` at index time ([13](./13_RAG_SYSTEM.md)).
- The **same `Embedder.id` must be used to index and to query** a given vector store (§9 versioning).

## 5. Model Selection

- **Provider-selected embedder (default):** the embedder is chosen through the **provider system / router** ([21](./21_PROVIDER_SYSTEM.md)/[45](./45_ROUTING_ORCHESTRATION.md)) like any model — the best embed-capable model across the configured providers (e.g., a Gemini or NVIDIA **NeMo Retriever** embedding model, or an OpenRouter-hosted embedder — [22](./22_PROVIDER_INTEGRATIONS.md)). NVIDIA NeMo Retriever is a strong option here but is **one option among several**, not a mandated/sovereign default.
- **Local/offline embedder (fallback):** a local model (via **Ollama** or a bundled ONNX embedder) serves when providers are unavailable ([32](./32_OFFLINE_FIRST.md)) — reduced quality, still functional (PR-7).
- **Reranker:** a rerank-capable provider model (e.g., NeMo Retriever reranker) or a local cross-encoder; optional, degrades to fusion-only ([13](./13_RAG_SYSTEM.md) §8).
- **Coherence rule stands:** whichever embedder is chosen, the **same `Embedder.id` indexes and queries** a store (§9); switching embedders triggers a re-embed migration.

## 6. Dimensions, Normalization & Distance

- Each model has a **fixed `dim`**; the vector store column is sized to it ([29](./29_STORAGE.md)).
- Outputs are **L2-normalized** so **cosine similarity == dot product**; the vector index uses cosine/inner-product accordingly. This convention is fixed project-wide to avoid distance-metric mismatches (a subtle correctness bug).
- Mixed-dimension vectors are never stored in one index; a model change means a new/migrated index (§9).

## 7. Input Preparation (Turkish & Code)

- **Tokenization & truncation:** inputs are token-counted with the model's tokenizer and truncated to `maxTokens` at safe boundaries (don't split a token/word mid-way).
- **Turkish handling:** no lossy ASCII-folding of Turkish text (İ ı ş ğ ç ö ü preserved); locale-correct normalization only (PR-12). Casing normalization, if any, uses Turkish rules ([09](./09_PYTHON_BACKEND.md) `ortak/`).
- **Code handling:** code chunks are embedded as-is (identifiers matter); optional lightweight normalization (strip noise) is model-appropriate and consistent between index and query.
- **Instruction prefixes:** applied per the model's spec for `document`/`query` kinds (§4).

## 8. Batching & Caching

- **Batching:** embedding requests are batched (bounded batch size) and dispatched off the event loop ([09](./09_PYTHON_BACKEND.md) §6) to a GPU/CPU worker; throughput matters most during initial index builds.
- **Content-hash cache:** an embedding is keyed by `(model.id, contentHash)`; unchanged content is never re-embedded ([13](./13_RAG_SYSTEM.md) §10, [29](./29_STORAGE.md) CAS). This makes incremental indexing cheap and re-opening a workspace instant.
- **Query cache:** recent query embeddings are cached (short TTL) for repeated/near-identical queries.

## 9. Model Versioning & Re-Embedding (Critical)

- The vector store records the **`Embedder.id` and `dim`** it was built with. Retrieval **must** use the same embedder; a mismatch is detected and refused (never silently compare vectors from different models — that returns garbage).
- **Changing the embedding model** (user choice or upgrade) triggers a **background re-embedding migration**: re-embed all chunks/memory from source with the new model into a new index, then atomically switch and drop the old (no user-data loss — everything is re-derivable from source, [13](./13_RAG_SYSTEM.md) §15). Progress is surfaced via events ([10](./10_IPC.md)); retrieval keeps using the old index until the new one is ready (PR-7).
- This is the single most important operational concern in this doc — embedding coherence is a correctness property (PR-15).

## 10. Architecture / Directory

```
gomme/
  embedder.py        # Embedder interface + selection
  reranker.py        # Reranker interface
  prepare.py         # tokenization, truncation, tr/code normalization, kind-prefixing
  batch.py           # batching + worker dispatch
  cache.py           # (model.id, contentHash) → vector cache
  migrate.py         # re-embedding migration
  backends/          # local (onnx/torch), nvidia (NIM/NeMo), provider adapters (doc 21/22)
```

## 11. Configuration

- Default embedder/reranker ids, batch size, cache size/TTL, normalization (fixed on), and hardware tier are configurable ([33](./33_CONFIGURATION.md)). Effort mode ([17](./17_EFFORT_MODES.md)) tunes rerank depth and whether rerank runs.

## 12. Dependencies

- Local inference runtime (ONNX Runtime / Torch, GPU via CUDA — [22](./22_PROVIDER_INTEGRATIONS.md)), model weights (fetched/verified, [32](./32_OFFLINE_FIRST.md)), [29_STORAGE](./29_STORAGE.md) (vectors + cache), [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) (backend abstraction).

## 13. Edge Cases

- **Model/index mismatch:** refuse and trigger re-embed (§9); never compare across models.
- **Truncation of long inputs:** count tokens, truncate safely; very long files are chunked upstream ([13](./13_RAG_SYSTEM.md)).
- **Empty/whitespace input:** return a defined zero/near-zero handling (skip indexing empty chunks).
- **GPU OOM / no GPU:** fall back to CPU or a smaller model (PR-7); reduce batch size adaptively.
- **Asymmetric-model misuse** (query embedded as document): prevented by the mandatory `kind` arg and tests (§16).
- **Non-normalized model:** if a model doesn't output unit vectors, `prepare`/`embed` normalizes so the cosine==dot invariant holds (§6).
- **Turkish text:** never ASCII-folded; verified by tests.

## 14. Failure Recovery

- A failed batch is retried/subdivided; persistent failure yields a typed error and the affected chunks are marked un-embedded (retryable later) — the index stays usable for the rest (PR-7/PR-10).
- Re-embedding migrations are resumable/idempotent ([28](./28_CRASH_RECOVERY.md)); the old index remains authoritative until switchover.

## 15. Security

- Local embedding = **no egress** of code/text ([P1], [30](./30_SECURITY.md)). If a cloud embedder is chosen, embedding sends content off-device → this is consent-gated and made explicit ([21](./21_PROVIDER_SYSTEM.md), [32](./32_OFFLINE_FIRST.md), PR-16); the default avoids it. Model weights are hash-verified on fetch (supply chain, [30](./30_SECURITY.md)).

## 16. Testing Strategy

- **Determinism:** same input + model → same vector (within tolerance) (PR-15).
- **Normalization invariant:** outputs are unit-length; cosine==dot.
- **Asymmetry correctness:** `query`/`document` kinds produce the intended asymmetric behavior; misuse is caught.
- **Cache correctness:** unchanged content isn't re-embedded; changed content is.
- **Migration test:** model swap re-embeds from source and switches atomically without losing retrieval availability.
- **Turkish fidelity:** Turkish inputs are not folded/corrupted. See [35_TESTING](./35_TESTING.md).

## 17. Performance

- Batch aggressively during index builds; cache by hash; GPU when available; adaptive batch sizing under memory pressure. Reranking dominates query latency and is effort-gated. Budgets/metrics in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 18. Future Extensions

- Multi-vector / late-interaction (ColBERT-style) retrieval; domain-adapted/fine-tuned Turkish-code embedders; quantized vectors for memory savings; per-language embedders; hardware-aware auto model selection.

## 19. Examples

```python
# index time (doc kind) vs query time (query kind) — never mix
vecs = embedder.embed(chunk_texts, kind="document")   # stored with embedder.id
qv   = embedder.embed([user_query], kind="query")     # searched against same store
```

## 20. Anti-Patterns

- Comparing vectors from different models/dimensions.
- Embedding queries and documents with the same `kind` for asymmetric models.
- Re-embedding unchanged content (ignoring the hash cache).
- ASCII-folding Turkish before embedding.
- Storing mixed-dimension vectors in one index.
- Silent model change without re-embedding.

## 21. Things That Must Never Happen

1. Retrieval compares vectors produced by different embedders/dimensions.
2. A model change proceeds without a re-embedding migration (index coherence lost).
3. Turkish text is lossy-normalized before embedding.
4. Local-default embedding silently egresses content.
5. The cosine/dot normalization invariant is violated in a stored index.

## 22. Relationship With Other Subsystems

Powers [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) (semantic + rerank), [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) (recall), and [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md) (node similarity). Backed by [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)/[22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md); stored via [29_STORAGE](./29_STORAGE.md); budgeted by [17_EFFORT_MODES](./17_EFFORT_MODES.md); offline model management per [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md).

## 23. Migration Considerations

- Embedding-model changes are the canonical re-embed migration (§9). `dim`/normalization/id are recorded per index; a mismatch forces migration. Reranker swaps are transparent (no stored state). All migrations re-derive from source — never destructive to user data.
