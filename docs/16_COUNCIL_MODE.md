# 16 — Council Mode (Divan)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `divan/`
> **Related:** [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) · [17_EFFORT_MODES](./17_EFFORT_MODES.md) · [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) · [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [26_TIMELINE](./26_TIMELINE.md)

---

## 1. Purpose

Defines **Divan** (Council) — a deliberation mode where multiple model **personas** independently propose, then critique each other, and a **synthesizer** reconciles their views into a single, higher-quality answer. The name honors the Ottoman *Dîvân*, the council of state. Divan trades compute for quality on hard, high-stakes, or ambiguous problems, and it makes disagreement *visible* — reinforcing transparency (P4/P5). It is invoked by the reasoning engine ([15](./15_REASONING_ENGINE.md)) or by the user, under the effort budget ([17](./17_EFFORT_MODES.md)).

## 2. Scope

The council topology (personas, rounds, synthesis), invocation policy, the deliberation protocol, aggregation/synthesis strategies, budget control, the council trace, and its integration into a reasoning run. Out of scope: the base reasoning loop ([15](./15_REASONING_ENGINE.md)), provider mechanics ([21](./21_PROVIDER_SYSTEM.md)), multi-agent delegation ([18](./18_AGENT_SYSTEM.md) — Divan is deliberation, not task decomposition).

## 3. Goals

1. **Higher answer quality** on hard problems via diverse perspectives + critique (ensemble/debate reduces single-model blind spots and errors).
2. **Visible deliberation**: the user sees each üye's stance, the critique, and the synthesis (transparency, [06](./06_COMPONENT_LIBRARY.md) §6.3).
3. **Bounded cost**: council size/rounds strictly budgeted ([17](./17_EFFORT_MODES.md), PR-14) — Divan is expensive by design and must never run unbounded.
4. **Provider-flexible**: personas may map to the *same* local model with different roles/prompts (works offline!) or to *different* models/providers ([21](./21_PROVIDER_SYSTEM.md)) — diversity from prompting when only one model is available (PR-6/PR-7).
5. **Turkish deliberation** by default (PR-12).

### Non-Goals
- Not always-on (it's opt-in/triggered). Not task delegation ([18](./18_AGENT_SYSTEM.md)). Not a consensus-voting gimmick — synthesis is reasoned reconciliation, not majority vote.

## 4. Council Topology

```
                ┌── Üye A (persona: "muhafazakâr/careful") ─┐
   PROMPT ──────┼── Üye B (persona: "yenilikçi/creative")  ─┼─▶ PROPOSALS
                └── Üye C (persona: "eleştirmen/skeptic")   ─┘
                                   │
                       [CRITIQUE ROUND(s)]  each üye sees others' proposals,
                                   │          critiques & optionally revises
                                   ▼
                       [SYNTHESİZER / Hakem]  reconciles into one answer +
                                   │           records where members disagreed
                                   ▼
                              SYNTHESIS (returned to Muhakeme 15)
```

- **Personas (Üye):** each = a model ([21](./21_PROVIDER_SYSTEM.md)) + a role/stance prompt + optional specialization (e.g., security reviewer, performance reviewer, Turkish-idiom reviewer). Default persona set is configurable; effort mode sets the count ([17](./17_EFFORT_MODES.md)).
- **Synthesizer (Hakem/judge):** a distinct role (often the strongest available model) that reads all proposals + critiques and produces the final answer, explicitly noting unresolved disagreements and confidence.
- **Rounds:** ≥1 propose round + 0..R critique rounds, capped by budget.

## 5. Invocation Policy (When Divan Convenes)

- **User-invoked:** the user selects council for a query (via `CabaSecici`/`DivanGorunumu`, [06](./06_COMPONENT_LIBRARY.md)).
- **Auto-invoked by Muhakeme ([15](./15_REASONING_ENGINE.md) §8):** when policy signals a hard/ambiguous/high-stakes decision *and* the effort mode permits (`Derin`/`Maksimum` typically enable auto-council; `Hızlı` never). Signals: low reflection confidence, conflicting retrieved evidence, a design decision with trade-offs, or an irreversible/high-impact action.
- **Never** for trivial tasks (cost discipline). The trigger policy is documented and tunable ([33](./33_CONFIGURATION.md)).

## 6. Deliberation Protocol

1. **Frame:** the synthesizer (or Muhakeme) frames the exact question + shared context (assembled per [13](./13_RAG_SYSTEM.md)) given to all üye — everyone deliberates on the same grounded context to keep it fair and grounded.
2. **Propose (parallel):** each üye independently produces a proposal + rationale (parallelized across providers where possible, [21](./21_PROVIDER_SYSTEM.md)).
3. **Critique (bounded rounds):** each üye sees the others' proposals and critiques/updates; disagreements are surfaced explicitly.
4. **Synthesize:** the Hakem reconciles — not by vote, but by reasoned integration — and outputs the final answer, a confidence, and a "points of disagreement" summary.
5. **Return:** the synthesis + a `divanRunId` go back to Muhakeme as a `council` trace step ([15](./15_REASONING_ENGINE.md) §5).

## 7. Aggregation / Synthesis Strategies

Selectable strategies (config/effort):
- **Reasoned synthesis (default):** Hakem integrates the best of each proposal.
- **Debate-to-consensus:** extra critique rounds until convergence or round cap.
- **Best-of / rank:** Hakem selects the single best proposal (cheaper).
- **Specialized panel:** fixed expert personas (security/perf/Turkish-idiom) each own a dimension; Hakem merges.
Ties/deadlocks are reported honestly (no forced fake consensus) — the synthesis states the disagreement (PR-10/PR-11).

## 8. Budget Control (Critical)

- **Everything is bounded** ([17](./17_EFFORT_MODES.md), PR-14): number of üye (e.g., 2–5), critique rounds (0–R), per-üye token budget, and total wall-clock. The Divan's cost is `~(members × rounds)` model calls, so caps are mandatory.
- The effort mode picks the council configuration; the user is shown the (higher) cost implication before an expensive council runs.
- Cancellation ([10](./10_IPC.md)) aborts all in-flight üye calls immediately.

## 9. Council Trace (Divan İzi)

A persisted record ([26](./26_TIMELINE.md)) capturing: the framed question, each üye's proposal + model, each critique, the synthesis + confidence + disagreements, and cost. Surfaced by `DivanGorunumu` ([06](./06_COMPONENT_LIBRARY.md) §6.3) with the synthesis highlighted (`altin` pulse, [05](./05_ANIMATION_SYSTEM.md)). This visible deliberation is a differentiator and a trust feature.

## 10. State Machine

```
[Framed] → [Proposing] → [Critiquing]×R → [Synthesizing] → [Done]
Any → [Cancelled] ($/cancel) | [Degraded] (a member failed → continue with the rest, PR-7)
Budget cap reached at any point → jump to [Synthesizing] with what's available.
```

## 11. Directory Structure

```
divan/
  council.py     # topology, orchestration, rounds
  persona.py     # üye definitions (model + stance)
  synthesize.py  # Hakem strategies (§7)
  policy.py      # invocation triggers (§5), budget mapping (17)
  trace.py       # divan trace (26)
```

## 12. Configuration

- Default persona set + stances, synthesizer model, per-effort council size/rounds, invocation trigger thresholds, and strategy are configurable ([33](./33_CONFIGURATION.md)/[17](./17_EFFORT_MODES.md)). Fully-local council (one model, many stances) is the offline default.

## 13. Dependencies

- [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) (models for üye/Hakem), [15_REASONING_ENGINE](./15_REASONING_ENGINE.md) (caller), [17_EFFORT_MODES](./17_EFFORT_MODES.md) (budgets), [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) (shared context), [26_TIMELINE](./26_TIMELINE.md) (trace), [10_IPC](./10_IPC.md) (streaming/cancel).

## 14. Edge Cases

- **Only one model available (offline):** personas differ by stance/prompt on the same model — still yields useful diversity (PR-6). The UI is honest that members share a model.
- **A üye/provider fails mid-round:** continue with remaining members (Degraded, PR-7); note reduced panel in the trace.
- **All members agree immediately:** skip extra critique rounds (save budget); synthesis is quick.
- **Persistent deadlock:** stop at round cap; synthesis reports the disagreement rather than fabricating consensus.
- **Budget too small for a real council:** fall back to single-model reasoning ([15](./15_REASONING_ENGINE.md)) with a note (don't run a degenerate 1-member "council").
- **Cancellation:** aborts all üye calls; partial deliberation is preserved in the trace.
- **Cloud personas + offline:** if a configured cloud üye is unreachable, drop it and continue locally (never block on egress, PR-6).

## 15. Failure Recovery

- Council runs are checkpointed within the parent reasoning run ([28](./28_CRASH_RECOVERY.md)); a crash resumes or restarts the council step. A failed council degrades to single-model reasoning rather than failing the whole task (PR-7).

## 16. Security

- Same untrusted-output posture as [15](./15_REASONING_ENGINE.md): council output can only act through tools+permissions; the Divan itself performs no side effects (it deliberates; Muhakeme acts). Traces redact secrets ([30](./30_SECURITY.md)); cloud personas mean egress → consent-gated ([21](./21_PROVIDER_SYSTEM.md), PR-16).

## 17. Performance

- Parallelize üye proposals; cap members/rounds/tokens; short-circuit on early agreement; cache the shared framed context. Council is intentionally the most expensive mode — reserved for when quality justifies it ([17](./17_EFFORT_MODES.md), [31](./31_PERFORMANCE.md)).

## 18. Testing Strategy

- **Budget-bound tests:** members×rounds strictly capped; cancellation aborts all calls.
- **Degradation tests:** member failure → continue with rest; cloud-member offline → local continue.
- **Synthesis honesty:** deadlocks reported, not faked.
- **Offline council:** single-model multi-stance works with no network.
- **Trace completeness:** every proposal/critique/synthesis recorded. See [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- Learned persona selection per problem type; specialized standing panels (security/perf/Turkish-language) as skills ([19](./19_SKILLS_SYSTEM.md)); tool-using üye (each can retrieve independently); user-configurable custom councils; weighting members by demonstrated reliability.

## 20. Examples

- "Bu API'yi nasıl versiyonlayalım?" under `Derin`: careful/creative/skeptic personas propose (URI vs header vs media-type versioning), critique trade-offs, Hakem synthesizes a recommendation with explicit trade-offs and notes the one point of remaining disagreement — all visible in `DivanGorunumu`.

## 21. Anti-Patterns

- Running Divan for trivial tasks (waste).
- Unbounded members/rounds (cost blowup — PR-14).
- Majority-vote "synthesis" that discards reasoning.
- Faking consensus when members genuinely disagree.
- Blocking on an unreachable cloud persona (violates offline-first).
- Letting council output trigger side effects directly.

## 22. Things That Must Never Happen

1. A council runs without member/round/token/time caps.
2. Divan is unavailable offline when a local model exists (must run single-model multi-stance).
3. Synthesis fabricates agreement that didn't exist.
4. Council deliberation performs a side effect without going through [20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md).
5. The deliberation is hidden from the user (must be inspectable).

## 23. Relationship With Other Subsystems

Invoked by [15_REASONING_ENGINE](./15_REASONING_ENGINE.md); bounded by [17_EFFORT_MODES](./17_EFFORT_MODES.md); uses models via [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md)/[22_PROVIDER_INTEGRATIONS](./22_PROVIDER_INTEGRATIONS.md); shares context from [13_RAG_SYSTEM](./13_RAG_SYSTEM.md); recorded in [26_TIMELINE](./26_TIMELINE.md); visualized by [06_COMPONENT_LIBRARY](./06_COMPONENT_LIBRARY.md) §6.3; distinct from [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) (deliberation vs delegation).

## 24. Migration Considerations

- Persona sets and synthesis strategies are versioned config; adding strategies is additive (PR-18). The council trace schema is versioned with the Timeline. Changing default council sizes affects cost/latency and is announced in [42_ROADMAP](./42_ROADMAP.md).
