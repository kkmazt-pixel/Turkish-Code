# 17 — Effort Modes (Çaba Modları)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 2.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `caba/`
> **Changed in v2.0** (per [52_ADR_LOG](./52_ADR_LOG.md) ADR-0011): there are now **two orthogonal dials** — a **compute-depth** dial (this doc's original Hızlı/Dengeli/Derin/Maksimum) **and** a **cost/quota** dial (**Performance / Balanced / Economy**) that drives routing/quota behavior (§4b).
> **Related:** [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) · [16_COUNCIL_MODE](./16_COUNCIL_MODE.md) · [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md) · [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md) · [31_PERFORMANCE](./31_PERFORMANCE.md)

---

## 1. Purpose

turkish.code exposes **two orthogonal control dials**:

1. **Compute-depth dial (Çaba / Effort)** — how hard the agent *thinks*: reasoning iterations, tokens, retrieval depth, council size, reflection passes, wall-clock. Resolves to an **Effort Budget** consumed uniformly across subsystems (PR-14). *This is the original subject of this document (§4–§21).*
2. **Cost/quota dial (Maliyet Modu)** — how the router *spends*: **Performance / Balanced / Economy**, driving which model/provider is chosen under quota/cost constraints ([45](./45_ROUTING_ORCHESTRATION.md)/[47](./47_SCORING_ALGORITHMS.md)/[48](./48_QUOTA_TIER_MANAGEMENT.md)). *Defined in §4b.*

The dials are **independent**: a user can think **Derin** (deep) while spending **Economy** (cheap), or **Hızlı** (fast) on **Performance** (best model). Both are expressed in every run's `meta` ([10](./10_IPC.md) §6.2).

## 2. Scope

Both dials, the Effort Budget schema, how the compute budget flows to subsystems, how the cost mode flows to routing, selection (user + auto), and cost transparency. Out of scope: how each subsystem *uses* its budget (their docs), the routing/scoring/quota mechanics ([45](./45_ROUTING_ORCHESTRATION.md)/[47](./47_SCORING_ALGORITHMS.md)/[48](./48_QUOTA_TIER_MANAGEMENT.md)), performance measurement ([31](./31_PERFORMANCE.md)).

## 3. Goals

1. Give users (and the agent) a **single, understandable dial** for the speed/quality trade-off.
2. Make the dial **concrete**: a mode deterministically produces a budget consumed uniformly across subsystems (PR-9/PR-14/PR-15).
3. **Cost transparency**: the user understands (and, for expensive modes, is warned about) latency/compute before running.
4. Work **offline** at every tier (higher modes do more local work, not necessarily cloud — PR-6).

### Non-Goals
- Not a model picker (that's [21](./21_PROVIDER_SYSTEM.md)); a mode may *influence* model choice but doesn't own it. Not per-tool config.

## 4. The Modes

Four canonical modes (Turkish names are user-facing):

| Mode | Turkish | Feel | Typical use |
|---|---|---|---|
| Fast | **Hızlı** | snappy, shallow | quick Q&A, autocomplete-like help, tight loops |
| Balanced | **Dengeli** (default) | good default | most day-to-day agentic work |
| Deep | **Derin** | thorough, slower | hard problems, larger refactors, careful review |
| Maximum | **Maksimum** | exhaustive, costly | high-stakes decisions, deep multi-file work, council |

The default is **Dengeli**. Modes are ordered; higher = more of every budget dimension.

## 4b. The Cost/Quota Dial (Maliyet Modu) — ADR-0011

Orthogonal to compute-depth, the **cost/quota mode** tells the **router** ([45](./45_ROUTING_ORCHESTRATION.md)) how to trade **quality vs. cost/quota** when choosing a model/provider:

| Mode | Turkish | Router behavior |
|---|---|---|
| **Performance** | Başarım | Favor the highest-quality/fastest model regardless of cost; spend premium quota freely. Scoring ([47](./47_SCORING_ALGORITHMS.md)) weights quality/latency/Turkish-fidelity high, cost/quota near-zero. |
| **Balanced** | Dengeli | Even weighting of quality vs cost/quota (default). |
| **Economy** | Tasarruf | Favor cheap / quota-preserving models, **but never below the task's quality floor** ([47](./47_SCORING_ALGORITHMS.md) §6). Preserve premium quota for when it matters ([48](./48_QUOTA_TIER_MANAGEMENT.md)). |

- The default is **Balanced**.
- The mode becomes a **score-weighting input** in [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md) §6 and a **quota-aggressiveness input** in [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md) §6. It does **not** change the compute-depth budget (§5) — the dials are independent.
- **Quality floor interaction:** even in Economy, the **compute-depth** dial can raise the minimum acceptable model quality (e.g., `Derin`/`Maksimum` won't pick a weak model just to save cost) — this is how the two dials compose ([47](./47_SCORING_ALGORITHMS.md) §6).

The remainder of this document (§5 onward) describes the **compute-depth Effort Budget**; the cost/quota mode's mechanics live in the routing/scoring/quota docs.

## 5. Effort Budget Schema

A mode resolves to an `EffortBudget` passed in every run's `meta` ([10](./10_IPC.md) §6.2) and consumed by subsystems:

```
EffortBudget {
  maxLoopIterations: int        // reasoning loop cap (15)
  maxToolCalls: int             // total tool calls per run (20)
  maxTokensPerCall: int         // model output budget per call (21)
  maxTotalTokens: int           // aggregate token budget
  reflectionPasses: int         // self-correction depth (15 §7)
  retrieval: {                  // getirim (13)
     topKPerRetriever, rerank: bool|depth, graphExpandHops (12)
  }
  memory: { recallK, budgetTokens }   // bellek (11)
  council: {                    // divan (16)
     enabled: bool, autoTrigger: bool, maxMembers, maxRounds
  }
  agents: { maxSubAgents, maxDepth }  // ajan (18)
  wallClockMs: int              // hard time budget
  modelPreference?: tier        // hint to provider selection (21)
}
```

Representative values (illustrative; tuned in config [33](./33_CONFIGURATION.md)):

| Dimension | Hızlı | Dengeli | Derin | Maksimum |
|---|---|---|---|---|
| loop iterations | 3 | 8 | 20 | 40 |
| tool calls | 5 | 20 | 60 | 150 |
| reflection passes | 0 | 1 | 3 | 5 |
| retrieval topK / rerank | small / off | medium / on | large / deep | largest / deep |
| council | off | off (manual only) | auto-eligible (2–3) | auto (3–5) |
| sub-agents / depth | 0 / 0 | 2 / 1 | 5 / 2 | 12 / 3 |
| wall-clock | seconds | tens of s | minutes | minutes+ |

## 6. Budget Flow (How It Constrains Everything)

```
User/Agent picks mode → caba.resolve(mode) → EffortBudget
   → attached to run meta (10)
   → Muhakeme (15): caps loop/reflection/tokens
   → Getirim (13): topK/rerank/graph hops
   → Bellek (11): recallK/budget
   → Divan (16): enabled/size/rounds
   → Ajan (18): sub-agent count/depth
   → Provider (21): model tier hint, per-call tokens
   Every subsystem reads ITS slice; none may exceed it (PR-14, enforced).
```

- The budget is **passed explicitly** (PR-9), never read from a global. Subsystems that would exceed their slice must stop and finalize gracefully ([15](./15_REASONING_ENGINE.md) §14).
- **Sub-budgets:** when Muhakeme delegates to a sub-agent ([18](./18_AGENT_SYSTEM.md)) or a council ([16](./16_COUNCIL_MODE.md)), it allocates a *portion* of the remaining budget — nested work can never exceed the parent's total (prevents fan-out blowups).

## 7. Selection

- **Manual:** the user sets the mode via `CabaSecici` ([06](./06_COMPONENT_LIBRARY.md) §6.7), globally or per-message. Plain-Turkish descriptions explain each mode's trade.
- **Auto-suggest (optional):** the engine may *suggest* a higher mode when it detects a hard task ("Bu iş için Derin modu öneririm"), but never silently escalates cost — escalation to a more expensive mode is user-confirmed (cost transparency, PR-16 spirit).
- **Per-agent:** sub-agents inherit or receive a reduced budget from the orchestrator ([18](./18_AGENT_SYSTEM.md)).

## 8. Cost Transparency

- Before running an expensive mode (Derin/Maksimum, especially with council), the UI indicates the expected higher latency/compute. Actual consumption (tokens, tool calls, time) is recorded in the Timeline ([26](./26_TIMELINE.md)) and shown post-run, so users learn the trade empirically.
- For cloud providers, higher effort can mean higher token spend → surfaced explicitly ([34](./34_API_KEYS.md), [21](./21_PROVIDER_SYSTEM.md)).

## 9. Lifecycle

```
mode selected → resolve to budget → run consumes budget (metered) →
budget exhaustion handled gracefully (finalize partial, offer higher mode) →
consumption recorded (26) and displayed
```

## 10. State / Metering

- The run carries a **live budget meter** (remaining iterations/tokens/time). Each subsystem decrements its slice; the meter is checked at every loop boundary and before any expensive step (council, sub-agent spawn). Exhaustion → graceful finalize, never a hard crash (PR-7/PR-10).

## 11. Configuration

- The concrete numeric mapping for each mode lives in config ([33](./33_CONFIGURATION.md)) so it can be tuned per hardware tier (a CPU-only laptop may cap `Maksimum` lower than a GPU workstation, [31](./31_PERFORMANCE.md)). Defaults ship sensible; power users can customize.

## 12. Dependencies

- Consumed by [15](./15_REASONING_ENGINE.md), [13](./13_RAG_SYSTEM.md), [11](./11_MEMORY_SYSTEM.md), [16](./16_COUNCIL_MODE.md), [18](./18_AGENT_SYSTEM.md), [21](./21_PROVIDER_SYSTEM.md). Recorded by [26_TIMELINE](./26_TIMELINE.md). Configured via [33_CONFIGURATION](./33_CONFIGURATION.md).

## 13. Edge Cases

- **Budget too small for the task:** finalize with partial results + "reached effort limit; try Derin?" (never silently truncate a wrong-looking answer as if complete).
- **Hardware can't sustain a mode** (Maksimum on a weak CPU): the mode is capped to what the hardware allows (degradation ladder, PR-7) with a note.
- **Nested budgets exhausted mid-council/sub-agent:** the nested unit finalizes early with what it has; parent continues.
- **User escalates mid-run:** allowed at a safe boundary; the meter is topped up and the run continues (or restarts the current step) — never mid-token chaos.
- **Council enabled but budget forbids a real panel:** fall back to single-model ([16](./16_COUNCIL_MODE.md) §14).

## 14. Failure Recovery

- The budget meter is part of the run checkpoint ([28](./28_CRASH_RECOVERY.md)); a resumed run continues with the remaining budget. No mode can cause an unbounded run (PR-14) — the wall-clock and iteration caps are absolute.

## 15. Security

- Effort modes never override safety: higher effort does more *thinking/retrieval*, not more *unpermissioned action*. Every tool call still passes permissions ([24](./24_PERMISSION_SYSTEM.md)) regardless of mode. Higher modes that enable cloud/council still respect egress consent (PR-16).

## 16. Performance

- The mode IS the performance dial. `Hızlı` must feel instant; `Maksimum` may take minutes but must stream progress throughout so it never feels hung ([05](./05_ANIMATION_SYSTEM.md), [10](./10_IPC.md)). Measurement per [31_PERFORMANCE](./31_PERFORMANCE.md).

## 17. Testing Strategy

- **Bound enforcement:** each mode's caps are strictly honored across subsystems (no overrun).
- **Nested-budget tests:** sub-agent/council allocation never exceeds parent remaining.
- **Graceful exhaustion:** partial finalize + suggestion, no crash/wrong-confident answer.
- **Determinism:** same mode → same budget (PR-15).
- **Hardware capping:** weak-hardware config caps high modes correctly. See [35_TESTING](./35_TESTING.md).

## 18. Future Extensions

- Learned auto-mode selection per task type; per-dimension custom modes (power users); a "budget spent" live HUD; adaptive mid-run budget adjustment based on progress signals.

## 19. Examples

- Quick question → `Hızlı`: 1 retrieval, no rerank, ≤3 loop steps, no council → sub-second-ish answer.
- "Bu servisi mikroservislere böl" → user picks `Maksimum`: deep retrieval + rerank, council auto-eligible, multi-sub-agent plan, minutes of streamed work with a full trace.

## 20. Anti-Patterns

- Reading effort settings from a global instead of the passed budget (PR-9).
- Silent cost escalation without user awareness.
- Any subsystem exceeding its budget slice.
- Uncapped nested (sub-agent/council) budgets.
- Treating higher effort as license to skip permissions.

## 21. Things That Must Never Happen

1. A run exceeds its wall-clock/iteration budget (unbounded work).
2. Nested work exceeds the parent's remaining budget.
3. A mode escalates cloud/cost without user awareness/consent.
4. Higher effort weakens the permission/safety model.
5. Budget exhaustion produces a confident-but-truncated answer presented as complete.

## 22. Relationship With Other Subsystems

The single source of budgets consumed by [15](./15_REASONING_ENGINE.md), [13](./13_RAG_SYSTEM.md), [11](./11_MEMORY_SYSTEM.md), [16](./16_COUNCIL_MODE.md), [18](./18_AGENT_SYSTEM.md), and hinting [21](./21_PROVIDER_SYSTEM.md); metered into [26_TIMELINE](./26_TIMELINE.md); configured via [33_CONFIGURATION](./33_CONFIGURATION.md); the practical control surface of [31_PERFORMANCE](./31_PERFORMANCE.md).

## 23. Migration Considerations

- The mode→budget mapping is versioned config; retuning is additive and hardware-aware. Adding a new mode or budget dimension is additive (PR-18) — subsystems ignore unknown budget fields gracefully and default sensibly.
