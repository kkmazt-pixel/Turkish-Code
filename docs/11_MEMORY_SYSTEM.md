# 11 — Memory System (Bellek)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `bellek/`
> **Related:** [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md) · [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) · [14_EMBEDDINGS](./14_EMBEDDINGS.md) · [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) · [26_TIMELINE](./26_TIMELINE.md) · [29_STORAGE](./29_STORAGE.md)

---

## 1. Purpose

Defines **Bellek**, the layered, durable memory that lets turkish.code *remember* across turns and across sessions — the structural basis of Pillar P4 ([00](./00_PROJECT_VISION.md) §5). Bellek decides what to retain, how to retrieve it when relevant, and how the user inspects and controls it. It is distinct from, but built on, the retrieval ([13](./13_RAG_SYSTEM.md)), graph ([12](./12_KNOWLEDGE_GRAPH.md)), and storage ([29](./29_STORAGE.md)) subsystems.

## 2. Scope

The memory layers and their semantics, the write path (what gets remembered and how), the recall path (retrieval + ranking + injection into context), consolidation, user control (inspect/pin/forget), scoping, and privacy. Out of scope: the raw event log ([26_TIMELINE](./26_TIMELINE.md) — Bellek is *curated* memory, the Timeline is the *complete* record), embedding mechanics ([14](./14_EMBEDDINGS.md)), and generic retrieval ([13](./13_RAG_SYSTEM.md), which Bellek uses).

## 3. Goals

1. Persist useful knowledge about the **user**, the **project**, and prior **feedback** so the agent improves over time.
2. Recall the *right* memory at the *right* time without polluting context (precision over recall for injected memory — PR-14 budget discipline).
3. Give the user **full visibility and control** over what is remembered (P4/P5): inspect, edit, pin, forget.
4. Keep everything **local and private** (P1); memory is sensitive and never egresses without consent.
5. Distinguish curated memory from the exhaustive Timeline; Bellek is the *editorialized* long-term store.

### Non-Goals
- Not the full audit log (that's [26](./26_TIMELINE.md)). Not raw code indexing (that's [13](./13_RAG_SYSTEM.md)/[12](./12_KNOWLEDGE_GRAPH.md)). Not a cloud-synced profile.

## 4. Memory Layers

Five layers, each with distinct lifetime, scope, and use. (Terms fixed in [44](./44_GLOSSARY.md) §6.)

| Layer | Turkish | Lifetime | Scope | Contents |
|---|---|---|---|---|
| **Working** | Çalışan Bellek | session | session | current conversation, active plan, transient scratch |
| **Episodic** | Anısal Bellek | durable | workspace | summaries of past sessions/runs ("what we did on X") |
| **Semantic** | Anlamsal Bellek | durable | workspace (+ global opt) | distilled facts about the project & domain, vector-indexed |
| **Profile** | Profil Belleği | durable | global (per user) | stable facts about the user (role, preferences, environment) |
| **Feedback** | Geri Bildirim Belleği | durable | global + workspace | corrections/approvals on *how the agent should behave* (with why) |

- **Working** feeds directly into the prompt for the current run; it is bounded by the effort budget ([17](./17_EFFORT_MODES.md)) and summarized into Episodic on session close.
- **Feedback** is special: it changes agent *behavior* (e.g., "always write commit messages in Turkish"), carries a **rationale**, and is weighted highly at recall. It mirrors the "feedback" memory type this very documentation process uses.
- **Profile/global** memory is shared across workspaces; **workspace** memory is isolated per project ([25](./25_WORKSPACE_SYSTEM.md)).

## 5. Memory Record Schema

A memory item (persisted in the Workspace/App DB, [29](./29_STORAGE.md)):

```
MemoryItem {
  id: uuid
  layer: working|episodic|semantic|profile|feedback
  scope: session|workspace|global
  kind: fact|preference|feedback|episode|entity-note
  title: string (short, Turkish by default)
  body: string (the memory; for feedback: includes "Neden/Why" + "Nasıl uygula/How")
  links: [entityId]        // ties to Bilgi Grafı (doc 12)
  embeddingRef: vectorId   // doc 14 (for semantic recall)
  salience: float          // learned importance (0..1)
  source: {runId, eventId} // provenance into the Timeline (doc 26)
  pinned: bool             // user-forced always-relevant
  createdAt, lastUsedAt, useCount, confidence
  ttl?: duration           // optional expiry for volatile facts
}
```

Every memory item is **traceable to its source** in the Timeline (provenance) — the user can always ask "why do you think this?" (P4).

## 6. Architecture

```
                 ┌────────────────────────── Bellek ──────────────────────────┐
 Muhakeme (15) ──▶ RECALL: query → retrieve (Getirim 13) + graph (12) +        │
                 │          profile/feedback lookup → rank → budget → inject    │
 run events ────▶ WRITE:  capture candidates → dedup/merge → embed (14) →       │──▶ Storage (29)
 (Timeline 26)   │          store → link to graph (12)                          │
                 │ CONSOLIDATE: periodic summarize/decay/promote across layers  │
                 │ CONTROL:  inspect / pin / forget / edit (via BellekPaneli 6) │
                 └──────────────────────────────────────────────────────────────┘
```

Bellek **uses** Getirim ([13](./13_RAG_SYSTEM.md)) for vector recall and the Bilgi Grafı ([12](./12_KNOWLEDGE_GRAPH.md)) for structured relations; it does not reimplement them. It **owns** the curation logic (what to keep, how to rank, when to forget).

## 7. Write Path (What Gets Remembered)

1. **Candidate capture:** during/after a run, a memory-extraction pass proposes candidate items from: explicit user statements ("remember that…"), inferred stable facts, feedback/corrections, and end-of-run episode summaries.
2. **Filtering (precision-first):** discard the ephemeral, the already-known (dedup against existing via embedding similarity + graph match), and anything the repo/Timeline already records better (don't duplicate code facts that Getirim can retrieve — mirrors the "don't save what the repo records" discipline).
3. **Consent for sensitive content:** memory that could be sensitive (secrets, personal data) is never stored in plaintext memory; secrets are redacted ([30](./30_SECURITY.md)). Nothing here egresses ([P1]).
4. **Embed & link:** compute an embedding ([14](./14_EMBEDDINGS.md)), link to graph entities ([12](./12_KNOWLEDGE_GRAPH.md)), persist ([29](./29_STORAGE.md)).
5. **Salience init:** initial importance from kind (feedback/profile high) and recency.

## 8. Recall Path (What Gets Injected)

1. **Trigger:** at context assembly ([13](./13_RAG_SYSTEM.md) §context assembly), Muhakeme requests relevant memory for the current query/goal.
2. **Multi-source retrieval:** vector recall of Semantic/Episodic (Getirim), always-include Pinned + high-salience Feedback + relevant Profile, and graph-adjacent entity notes ([12](./12_KNOWLEDGE_GRAPH.md)).
3. **Rank & de-dupe:** score by similarity × salience × recency × pinned, remove near-duplicates.
4. **Budget:** select the top-K that fit the memory slice of the effort budget ([17](./17_EFFORT_MODES.md)); precision over recall — a smaller set of highly-relevant memories beats flooding the context.
5. **Inject with provenance:** injected memory is tagged so the reasoning trace ([15](./15_REASONING_ENGINE.md)) and the UI ([06](./06_COMPONENT_LIBRARY.md) §6.9) can show *what was recalled and why*.

## 9. Consolidation & Forgetting

- **Session close → Episodic:** summarize Working memory into an episode; extract durable facts into Semantic; decay the rest.
- **Decay:** salience decays with disuse; low-salience, unpinned, expired (`ttl`) items are pruned during periodic consolidation. Feedback/Profile/Pinned never auto-decay to zero.
- **Merge:** similar items are merged (keeping the strongest provenance) to fight bloat.
- **Contradiction handling:** newer, higher-confidence facts supersede older ones; the older item is marked superseded (kept for audit, hidden from recall) — never silently deleted (PR-4, auditability).
- All consolidation is deterministic given inputs (PR-15) and logged to the Timeline.

## 10. User Control (P4/P5 Requirement)

The user can, via `BellekPaneli` ([06](./06_COMPONENT_LIBRARY.md) §6.9):
- **Inspect** all memory (browse/search, see provenance and what was recalled for a given run).
- **Pin/Unpin** items (force always-relevant / demote).
- **Edit** an item's body/title.
- **Forget** an item (soft-delete, auditable) or hard-purge (permanent) for privacy.
- **Scope control:** move an item between workspace/global; mark as never-remember.
Memory control is a first-class product feature, not a hidden setting.

## 11. Lifecycle

```
capture → filter → embed/link → store
   ↘ (recall on demand across the session)
session close → consolidate (summarize/promote/decay)
periodic → consolidate/merge/prune
user action → pin/edit/forget (auditable)
```

## 12. State Machine (Memory Item)

```
[Candidate] → [Active] ⇄ [Pinned]
     │            │  decay/disuse
     │            ▼
     │        [Dormant] → prune → [Purged]
     └──rejected──▶ (dropped)
   [Active] --superseded by newer fact--> [Superseded] (retained, hidden from recall)
```

## 13. Configuration

- Recall K, salience weights, decay rate, consolidation interval, per-layer budgets, and global-vs-workspace default scope are configurable ([33](./33_CONFIGURATION.md)) per effort mode ([17](./17_EFFORT_MODES.md)).
- Privacy defaults: sensitive-content redaction on; memory egress off ([30](./30_SECURITY.md)).

## 14. Dependencies

- [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) (vector recall), [14_EMBEDDINGS](./14_EMBEDDINGS.md) (embeddings), [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md) (entity links), [29_STORAGE](./29_STORAGE.md) (persistence), [26_TIMELINE](./26_TIMELINE.md) (provenance), [17_EFFORT_MODES](./17_EFFORT_MODES.md) (budgets).

## 15. Edge Cases

- **Contradictory memories:** newest high-confidence wins; older superseded (§9).
- **Memory bloat:** consolidation/merge/decay bound growth; a hard cap per layer triggers aggressive pruning of lowest-salience unpinned items.
- **Bad memory poisoning behavior** (a wrong "fact" degrading answers): user can Forget; low-confidence auto-decays; feedback that repeatedly proves wrong loses salience.
- **Prompt-injected "remember this"** from untrusted content ([30](./30_SECURITY.md)): candidate capture treats model/tool-sourced "remember" requests as low-confidence and never auto-pins; sensitive writes are redacted.
- **Cross-workspace leakage:** workspace-scoped memory must never surface in another workspace ([25](./25_WORKSPACE_SYSTEM.md)); only `global` scope is shared.
- **Corrupt embedding/index:** recall falls back to keyword/graph recall; index rebuildable ([13](./13_RAG_SYSTEM.md)).

## 16. Failure Recovery

- Memory writes are journaled; a crash mid-consolidation resumes safely ([28](./28_CRASH_RECOVERY.md)).
- If the vector store is unavailable, recall degrades to keyword + pinned + feedback + profile (PR-7) — reduced quality, not failure.

## 17. Security

- Memory is **local and private** (P1); no egress without explicit consent ([30](./30_SECURITY.md), [34](./34_API_KEYS.md)).
- Secrets/sensitive tokens are redacted before storage; a scanner prevents obvious secrets from entering memory.
- User purge is honored completely (hard-delete removes rows + vectors + blobs).

## 18. Performance

- Recall is on the hot path of every run; keep it fast via ANN vector search ([14](./14_EMBEDDINGS.md)), cached pinned/feedback/profile sets, and a bounded K. Writes/consolidation happen off the reasoning hot path (background). Budgets in [31](./31_PERFORMANCE.md).

## 19. Testing Strategy

- **Recall precision/recall** tests on curated fixtures (right memory surfaces; irrelevant doesn't flood).
- **Consolidation determinism** (PR-15): same session → same episode summary/promotions.
- **Control tests:** pin/edit/forget/purge fully effective (purged memory never recalled again).
- **Isolation tests:** workspace memory never leaks cross-workspace.
- **Injection-safety tests:** untrusted "remember" requests can't auto-pin or store secrets. See [35_TESTING](./35_TESTING.md).

## 20. Future Extensions

- Learned salience via feedback loops; user-defined memory categories; optional, explicitly-consented encrypted sync across the user's own devices (still P1-respecting); memory "profiles" per client/project.

## 21. Examples

**Feedback memory (behavioral, with rationale):**
```
kind: feedback | scope: global | salience: high | pinned: true
title: "Commit mesajları Türkçe"
body:  "Kullanıcı commit mesajlarını Türkçe istiyor.
        Neden: ekip Türkçe çalışıyor. Nasıl uygula: git commit üretiminde tr."
source: {runId: r42, eventId: e13}
```
Recalled on any commit-message task and shown in the reasoning trace as "hatırlanan geri bildirim".

## 22. Anti-Patterns

- Dumping the entire conversation into durable memory (bloat; violates precision-first).
- Duplicating code facts better served by live retrieval ([13](./13_RAG_SYSTEM.md)).
- Auto-pinning model/tool-suggested memories.
- Storing secrets or sensitive data in plaintext memory.
- Silent deletion of superseded/contradicted memories (breaks audit).
- Leaking workspace memory across workspaces.

## 23. Things That Must Never Happen

1. Memory egresses off-device without explicit consent.
2. A secret is persisted into memory in plaintext.
3. Workspace-scoped memory surfaces in a different workspace.
4. A user "forget/purge" leaves recallable residue.
5. Injected memory lacks provenance to the Timeline.

## 24. Relationship With Other Subsystems

Built on [13](./13_RAG_SYSTEM.md)/[14](./14_EMBEDDINGS.md)/[12](./12_KNOWLEDGE_GRAPH.md); persisted by [29](./29_STORAGE.md); provenance from [26_TIMELINE](./26_TIMELINE.md); consumed by [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) (context assembly) and scoped by [25_WORKSPACE_SYSTEM](./25_WORKSPACE_SYSTEM.md); surfaced by [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md) §6.9; bounded by [17_EFFORT_MODES](./17_EFFORT_MODES.md); privacy per [30_SECURITY](./30_SECURITY.md).

## 25. Migration Considerations

- Memory schema and embedding model are versioned; changing the embedding model triggers a background re-embed migration ([14](./14_EMBEDDINGS.md)). Layer/scope changes are forward-only migrations ([29](./29_STORAGE.md)). Superseded items are retained across migrations for audit.
