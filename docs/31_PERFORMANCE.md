# 31 — Performance (Başarım)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** cross-cutting
> **Related:** [01_ARCHITECTURE](./01_ARCHITECTURE.md) · [17_EFFORT_MODES](./17_EFFORT_MODES.md) · [03_UI_SYSTEM](./03_UI_SYSTEM.md) · [10_IPC](./10_IPC.md) · [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md) · [29_STORAGE](./29_STORAGE.md)

---

## 1. Purpose

Defines the **performance model, budgets, and measurement** for turkish.code: the latency/throughput targets per surface, the architectural performance decisions (planes, streaming, backpressure), the hardware scaling story (laptop → GPU workstation), the degradation ladders, and how performance is measured and defended in CI. Performance here means *perceived responsiveness and honest progress* as much as raw speed — a coding companion must feel alive even when doing minutes of deep work.

## 2. Scope

Performance targets/budgets per tier, the cross-cutting techniques (streaming, virtualization, caching, batching, backpressure), hardware tiers + degradation, and measurement/benchmarking. Out of scope: the effort-mode budget *semantics* ([17](./17_EFFORT_MODES.md), which this doc's budgets feed), and subsystem-internal optimizations (their docs).

## 3. Goals

1. **Instant-feeling UI**: first paint fast, interactions <100ms, 60fps during streaming — independent of model speed ([03](./03_UI_SYSTEM.md)).
2. **Honest progress**: long operations stream progress continuously; nothing ever *looks* hung ([05](./05_ANIMATION_SYSTEM.md), [10](./10_IPC.md)).
3. **Scale with hardware**: usable on a modest CPU laptop; fast on a GPU workstation ([22](./22_PROVIDER_INTEGRATIONS.md)) — degradation ladders, not cliffs (PR-7).
4. **Bounded resource use**: memory, GPU VRAM, and disk are managed; nothing grows unbounded (PR-14).
5. **Architectural perf designed in** (PR-17): the planes/streaming/backpressure are structural, not retrofitted; micro-opt comes second and never at the cost of pillars.

### Non-Goals
- Not raw benchmark-chasing at the expense of privacy/offline/clarity (priority order [02](./02_DESIGN_PRINCIPLES.md) §4). Not GPU-mandatory performance.

## 4. Performance Targets (Budgets)

| Surface | Target | Notes |
|---|---|---|
| App cold start → first paint | < 1.0s | independent of Çekirdek/model readiness ([03](./03_UI_SYSTEM.md), [07](./07_DESKTOP_ARCHITECTURE.md)) |
| UI interaction latency | < 100ms | keypress/click to visible response |
| Streaming frame rate | ≥ 55–60fps | during token/reasoning streaming ([05](./05_ANIMATION_SYSTEM.md)) |
| Time-to-first-token (local, GPU) | low (model-dependent) | stream ASAP; don't block on full context ([15](./15_REASONING_ENGINE.md)) |
| Retrieval (typical workspace) | < ~1s | hybrid retrieve+rerank ([13](./13_RAG_SYSTEM.md)) |
| Incremental re-index (one file) | < ~1s | hash-diff incremental ([12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)) |
| Snapshot capture (typical edit) | negligible | changed-file hash+store, dedup ([27](./27_SNAPSHOTS.md)) |
| Crash recovery launch | fast (tail replay) | no full history replay ([28](./28_CRASH_RECOVERY.md)) |
| IPC control round-trip | small | thin control plane ([10](./10_IPC.md)) |

Targets are validated on a defined baseline hardware tier (§8) and tracked in CI (§16). Effort modes ([17](./17_EFFORT_MODES.md)) trade depth for latency deliberately — `Hızlı` must feel snappy; `Maksimum` may take minutes but streams throughout.

## 5. Architectural Performance Decisions (Structural)

- **Three data planes** ([01](./01_ARCHITECTURE.md) §6): control (thin), stream (high-freq deltas), bulk (large payloads off the JSON path) — so a big payload never stalls token streaming. This is the single most important perf decision.
- **Streaming everywhere:** reasoning, tokens, tool activity, indexing progress stream as they happen ([10](./10_IPC.md), [15](./15_REASONING_ENGINE.md)) → perceived speed.
- **Backpressure + coalescing** ([10](./10_IPC.md) §9): bounded queues; deltas coalesced per frame ([03](./03_UI_SYSTEM.md) §9); never drop data, never OOM.
- **Non-blocking loops:** the Çekirdek event loop never blocks; heavy work is off-loop ([09](./09_PYTHON_BACKEND.md) §6). The UI main thread never blocks on tokenization/diff (Web Workers, [03](./03_UI_SYSTEM.md)).
- **Progressive readiness:** UI paints and is usable before the brain/models finish loading ([03](./03_UI_SYSTEM.md), [07](./07_DESKTOP_ARCHITECTURE.md)).

## 6. Cross-Cutting Techniques

- **Virtualization** of long lists (chat, timeline, file tree, diffs) → 60fps regardless of size ([03](./03_UI_SYSTEM.md)/[06](./06_COMPONENT_LIBRARY.md)).
- **Caching with invalidation:** embedding cache by content hash ([14](./14_EMBEDDINGS.md)), retrieval/result caches ([13](./13_RAG_SYSTEM.md)), assembled-context reuse for follow-ups ([15](./15_REASONING_ENGINE.md)), pinned/feedback memory sets ([11](./11_MEMORY_SYSTEM.md)).
- **Batching:** embeddings ([14](./14_EMBEDDINGS.md)), DB writes ([29](./29_STORAGE.md)), file-watch events ([25](./25_WORKSPACE_SYSTEM.md)).
- **Incrementalism:** hash-diff re-index/graph ([12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)); tail-replay recovery ([28](./28_CRASH_RECOVERY.md)); dedup snapshots ([27](./27_SNAPSHOTS.md)).
- **Compositor-only animation** (transform/opacity), reduced-motion + software-render fallbacks ([05](./05_ANIMATION_SYSTEM.md)).
- **Lazy loading:** models loaded on demand + idle-unloaded ([21](./21_PROVIDER_SYSTEM.md)/[22](./22_PROVIDER_INTEGRATIONS.md)); skills progressively disclosed ([19](./19_SKILLS_SYSTEM.md)); features code-split ([03](./03_UI_SYSTEM.md)).

## 7. Resource Management

- **Memory:** bounded queues/caches with eviction; virtualization; Çekirdek worker pool bounded ([09](./09_PYTHON_BACKEND.md)). Memory-store growth bounded by consolidation/retention ([11](./11_MEMORY_SYSTEM.md)/[26](./26_TIMELINE.md)/[27](./27_SNAPSHOTS.md)).
- **GPU VRAM:** detect capacity; size models to fit; keep hot models resident; **idle-unload** under pressure; ladder to smaller/CPU on OOM ([22](./22_PROVIDER_INTEGRATIONS.md)/[21](./21_PROVIDER_SYSTEM.md)).
- **Disk:** WAL + retention/GC bound DB/blob/journal growth ([29](./29_STORAGE.md)/[27](./27_SNAPSHOTS.md)/[26](./26_TIMELINE.md)); indexes rebuildable if space is reclaimed.
- **CPU:** off-loop heavy work; effort-mode caps ([17](./17_EFFORT_MODES.md)) bound total work per run.

## 8. Hardware Tiers & Degradation Ladders

```
Tier A — GPU workstation (NVIDIA): local NIM/TensorRT-LLM, NeMo rerank, large models, deep effort fast (22)
Tier B — capable laptop (GPU/Metal): mid models via llama.cpp/Ollama, rerank on, medium effort smooth
Tier C — CPU-only: small local models, rerank optional, effort capped, still fully functional (P1/PR-6)
```
- The app **detects** the tier ([07](./07_DESKTOP_ARCHITECTURE.md) §10), recommends models (onboarding), and caps effort modes accordingly ([17](./17_EFFORT_MODES.md) §11). Every capability has a **degradation ladder** (smaller model, no rerank, fewer council members, shallower retrieval) so weaker hardware yields *slower/simpler*, never *broken* (PR-7).

## 9. Configuration

- Per-tier effort caps, cache sizes, worker-pool size, VRAM budget, idle-unload timeout, fsync levels ([29](./29_STORAGE.md)), and coalescing windows ([10](./10_IPC.md)) are configurable ([33](./33_CONFIGURATION.md)) with hardware-aware defaults.

## 10. Dependencies

- Interacts with essentially every subsystem; realized notably via [10_IPC](./10_IPC.md) (planes/backpressure), [17_EFFORT_MODES](./17_EFFORT_MODES.md) (budgets), [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md) (GPU), [29_STORAGE](./29_STORAGE.md) (durable-vs-fast trades), [03_UI_SYSTEM](./03_UI_SYSTEM.md)/[05_ANIMATION_SYSTEM](./05_ANIMATION_SYSTEM.md) (frontend perf).

## 11. Edge Cases

- **Huge workspace/monorepo:** bounded/lazy indexing ([12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)); virtualized UI; usable while background build proceeds.
- **Slow model / low-end CPU:** stream progress; cap effort; recommend a smaller model — never a frozen UI.
- **High token throughput:** coalescing prevents render thrash ([05](./05_ANIMATION_SYSTEM.md) §6).
- **GPU OOM mid-run:** ladder down + resume ([21](./21_PROVIDER_SYSTEM.md)/[28](./28_CRASH_RECOVERY.md)).
- **Large single tool output/file:** bulk plane ([10](./10_IPC.md) §11), not inline.
- **Background window:** pause decorative loops ([05](./05_ANIMATION_SYSTEM.md)); throttle non-urgent work.
- **Disk pressure:** GC + retention; degrade to fewer retained snapshots/events (never lose the audit spine).

## 12. Failure Recovery

- Perf failures degrade, not crash (PR-7): a slow/failed provider fails over ([21](./21_PROVIDER_SYSTEM.md)); an over-budget run finalizes gracefully ([17](./17_EFFORT_MODES.md)); a memory-pressure event unloads models. Recovery launch is fast by design (§4, [28](./28_CRASH_RECOVERY.md)).

## 13. Security/Privacy Interaction

- Performance never justifies weakening pillars (priority order, [02](./02_DESIGN_PRINCIPLES.md) §4): e.g., no caching secrets, no second egress path for speed, no relaxing journal/snapshot fsync ([29](./29_STORAGE.md) §8, [30](./30_SECURITY.md)). Local-first is *also* a latency win (no round-trip) — privacy and speed align here.

## 14. Testing Strategy / Measurement

- **Performance CI gates** on the baseline tier: cold-start, interaction latency, streaming fps under high token rate, retrieval latency, incremental re-index, recovery launch — regressions beyond a threshold fail the build.
- **Benchmarks** for retrieval quality-vs-latency, embedding throughput, snapshot capture cost, IPC round-trip.
- **Load/soak tests:** long sessions (memory/disk growth bounded), huge workspaces, high-throughput streaming (backpressure holds, no OOM/drops).
- **Degradation tests:** each ladder yields a valid slower result. See [35_TESTING](./35_TESTING.md).

## 15. Future Extensions

- Speculative decoding / model cascades ([21](./21_PROVIDER_SYSTEM.md)); quantized vectors ([14](./14_EMBEDDINGS.md)); adaptive effort based on live progress ([17](./17_EFFORT_MODES.md)); a perf HUD; per-workspace warm caches; multi-GPU scaling ([22](./22_PROVIDER_INTEGRATIONS.md)).

## 16. Examples

- `Maksimum` deep refactor on Tier A: streams reasoning, runs a council, edits 8 files — visibly progressing throughout, ~minutes, 60fps UI. Same task on Tier C: capped effort + smaller model → still completes correctly, slower, with the same live progress and full reversibility.

## 17. Anti-Patterns

- Blocking the Çekirdek loop or the UI main thread.
- Inlining bulk data into control/stream frames.
- Unbounded caches/queues/loops (PR-14).
- Fake spinners instead of real streamed progress.
- Animating layout-triggering properties on hot paths.
- Re-embedding/re-indexing unchanged content.
- Trading a pillar for a benchmark.

## 18. Things That Must Never Happen

1. The UI freezes/blocks on model or IPC work.
2. A stream drops data or OOMs under load (must coalesce + backpressure).
3. A resource (memory/VRAM/disk) grows unbounded.
4. Weak hardware makes a core capability *break* rather than *degrade*.
5. A performance optimization introduces a second egress path or caches secrets.

## 19. Relationship With Other Subsystems

Feeds/consumes budgets from [17_EFFORT_MODES](./17_EFFORT_MODES.md); realized structurally by [01_ARCHITECTURE](./01_ARCHITECTURE.md)/[10_IPC](./10_IPC.md); scales via [22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md)/[21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md); bounded by [29_STORAGE](./29_STORAGE.md)/[11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md)/[26](./26_TIMELINE.md)/[27](./27_SNAPSHOTS.md); surfaced by [03_UI_SYSTEM](./03_UI_SYSTEM.md)/[05_ANIMATION_SYSTEM](./05_ANIMATION_SYSTEM.md); constrained by [30_SECURITY](./30_SECURITY.md)/[32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md).

## 20. Migration Considerations

- Performance budgets/targets are versioned config and may tighten as the product matures; regressions are gated in CI. Hardware-tier definitions and per-tier caps evolve with the ecosystem ([22](./22_PROVIDER_INTEGRATIONS.md)) and are announced in [42_ROADMAP](./42_ROADMAP.md). New techniques must preserve the pillar priority order ([02](./02_DESIGN_PRINCIPLES.md) §4).
