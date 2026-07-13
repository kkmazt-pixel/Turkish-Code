# 45 — Routing & Orchestration (Yönlendirme ve Orkestrasyon)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `yonlendirme/`
> **New in v2.0 of the provider layer** ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0004/0005/0006/0009).
> **Related:** [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md) · [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md) · [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md) · [17_EFFORT_MODES](./17_EFFORT_MODES.md)

---

## 1. Purpose

Defines the **router** — the brain of the model-first architecture. For every model request it answers: *which model, on which provider, right now?* It selects the **best model for the task** (not a favored provider — [52](./52_ADR_LOG.md) ADR-0005), using capability match ([46](./46_CAPABILITY_TAXONOMY.md)), scoring ([47](./47_SCORING_ALGORITHMS.md)), tier/quota state ([48](./48_QUOTA_TIER_MANAGEMENT.md)), health, and the user's cost/quota dial ([17](./17_EFFORT_MODES.md)). It also owns the **resilience loop**: smart failover, retry, timeout, and cooldown (ADR-0009). This is where "dynamic routing over static" (ADR-0004) lives.

## 2. Scope

The routing decision flow, the candidate→score→select pipeline, dynamic (runtime) signals, the failover/retry/timeout/cooldown loop, failure state handling, and the interfaces to scoring/quota/capability/provider. Out of scope: the scoring *formulas* ([47](./47_SCORING_ALGORITHMS.md)), quota *mechanics* ([48](./48_QUOTA_TIER_MANAGEMENT.md)), capability *vocabulary* ([46](./46_CAPABILITY_TAXONOMY.md)), provider *execution* ([21](./21_PROVIDER_SYSTEM.md)).

## 3. Goals

1. **Model-first** (ADR-0005): choose the best *model* for the task's required capabilities.
2. **Dynamic** (ADR-0004): decide at runtime from live signals (health, quota, latency, cost mode), never a static table.
3. **Resilient** (ADR-0009): smart failover/retry/timeout/cooldown; never hard-fail while a viable model remains.
4. **Quota-preserving & quality-aware** (ADR-0006): respect the cost/quota dial and preserve answer quality even as quota is exhausted ([48](./48_QUOTA_TIER_MANAGEMENT.md)).
5. **Provider-agnostic to callers** (ADR-0012): agents/reasoning ask for a capability; the router hides provider choice.

### Non-Goals
- Not the reasoning loop ([15](./15_REASONING_ENGINE.md), a caller). Not scoring math or quota bookkeeping (siblings).

## 4. Routing Decision Flow

```
request(capabilityNeed, costMode, effort, role) →
 1. CANDIDATES:  registry (21) → models matching role + capabilities (46)
 2. FILTER:      drop unhealthy/cooling-down providers (21/48); drop quota-exhausted where cost mode forbids (48)
 3. SCORE:       score each candidate model (47) using
                   capability-fit × quality × latency × cost × quota-headroom × health,
                   weighted by the cost/quota mode (17: Performance|Balanced|Economy)
 4. SELECT:      pick top-scored model; record the decision + rationale (26/51)
 5. EXECUTE:     provider.chat/embed/rerank (21), streaming (10)
 6. ON FAILURE:  smart failover → next-best candidate (retry/timeout/cooldown, §6)
 7. RESULT:      return; emit routing metrics (51)
```

- **Capability need** comes from the task/agent (via the reasoning engine [15]) and the capability taxonomy ([46](./46_CAPABILITY_TAXONOMY.md)).
- **Cost mode** (Performance/Balanced/Economy, [17](./17_EFFORT_MODES.md) ADR-0011) reweights the score: *Performance* favors quality/latency regardless of cost; *Economy* favors cheap/quota-preserving; *Balanced* is the middle.
- The full decision (candidates, scores, choice, why) is recorded for transparency ([26_TIMELINE](./26_TIMELINE.md)) and metrics ([51_METRICS](./51_METRICS.md)).

> **OPEN (design):** the exact **router decision flow diagram** and **failure state diagram** are recovered as *gaps* in `PROJECT_ANALYSIS.md` (L86/L87). §5/§6 give the canonical shape; concrete thresholds are to be finalized during implementation and recorded here (marked `OPEN` until then).

## 5. Dynamic Signals

Routing is a function of live state, refreshed continuously:
- **Health** per provider (up/degraded/cooling_down/down) ([21](./21_PROVIDER_SYSTEM.md) §9).
- **Quota headroom** per provider/tier ([48](./48_QUOTA_TIER_MANAGEMENT.md)).
- **Latency profile** per model (seed + live + benchmark, [50](./50_BENCHMARK_SPEEDTEST.md)).
- **Cost** per model ([22](./22_PROVIDER_INTEGRATIONS.md) pricing).
- **Capability fit** for the task ([46](./46_CAPABILITY_TAXONOMY.md)).
- **User cost/quota mode** ([17](./17_EFFORT_MODES.md)) and any per-role model pin ([21](./21_PROVIDER_SYSTEM.md) §6).

## 6. Resilience Loop — Failover, Retry, Timeout, Cooldown (ADR-0009)

```
attempt(model):
  call with TIMEOUT (per-call deadline; also from effort budget 17)
  success → done
  transient error / rate-limit / timeout:
     RETRY with bounded backoff up to N (per policy)
     if provider rate-limited/erroring → put provider in COOLDOWN (48) →
     SMART FAILOVER → next-best candidate model (re-score excluding cooling-down providers)
  all cloud candidates exhausted → OFFLINE FALLBACK to Ollama (32)
  no viable model → typed error (38) with remediation
```

- **Smart** (not static) failover: on failure the router re-scores the remaining candidates with updated signals, so it fails over to the genuinely next-best *model*, which may live on a different provider (ADR-0009, supersedes "simple static failover" which was rejected).
- **Cooldown** prevents hammering a degraded/rate-limited provider ([48](./48_QUOTA_TIER_MANAGEMENT.md)); the provider is skipped until its cooldown expires.
- **Quality-under-exhaustion** (ADR-0006, L97): as preferred models hit quota, the router keeps selecting the best *available* model to preserve quality rather than collapsing to a poor default ([48](./48_QUOTA_TIER_MANAGEMENT.md)).

## 7. Failure States

```
[Routing] → [Executing] → [Done]
    │            │ transient → [Retrying] → (back to Executing | Failover)
    │            │ provider bad → [Failover] → (next candidate | OfflineFallback)
    │            └ quota block → [Failover]/[Degrade]
    └ no candidates → [Unroutable] → typed error (38)
[OfflineFallback] (Ollama) → [Done] | [Unroutable]
```

## 8. Interfaces

- **In:** `route(request)` from the reasoning engine ([15](./15_REASONING_ENGINE.md))/embeddings ([14](./14_EMBEDDINGS.md))/council ([16](./16_COUNCIL_MODE.md)).
- **Uses:** registry + health + execution ([21](./21_PROVIDER_SYSTEM.md)); capability match ([46](./46_CAPABILITY_TAXONOMY.md)); scores ([47](./47_SCORING_ALGORITHMS.md)); quota/tier/cooldown ([48](./48_QUOTA_TIER_MANAGEMENT.md)); latency/quality ([50](./50_BENCHMARK_SPEEDTEST.md)).
- **Out:** routing decisions/metrics ([51_METRICS](./51_METRICS.md)), trace events ([26_TIMELINE](./26_TIMELINE.md)).

## 9. Directory Structure

```
yonlendirme/
  router.py       # the decision flow (§4)
  candidates.py   # candidate gen + capability filter (46)
  resilience.py   # failover/retry/timeout/cooldown loop (§6, 48)
  decision.py     # decision record + rationale (26/51)
# scoring (47), quota (48), capability (46), cache (49) are separate modules
```

## 10. Configuration

- Retry counts/backoff, per-call timeout defaults, cooldown durations, cost-mode score weights, and per-role pins are configurable ([33_CONFIGURATION](./33_CONFIGURATION.md)); tied to the two dials ([17](./17_EFFORT_MODES.md)).

## 11. Dependencies

- [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md), [46_CAPABILITY_TAXONOMY](./46_CAPABILITY_TAXONOMY.md), [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md), [48_QUOTA_TIER_MANAGEMENT](./48_QUOTA_TIER_MANAGEMENT.md), [49_MODEL_CACHE](./49_MODEL_CACHE.md), [50_BENCHMARK_SPEEDTEST](./50_BENCHMARK_SPEEDTEST.md), [17_EFFORT_MODES](./17_EFFORT_MODES.md), [26_TIMELINE](./26_TIMELINE.md), [51_METRICS](./51_METRICS.md).

## 12. Edge Cases

- **All providers cooling down / rate-limited:** wait for the soonest cooldown or fall to Ollama ([32](./32_OFFLINE_FIRST.md)); never busy-loop.
- **Task needs a capability no model has:** degrade to the closest-capability model + note the degradation ([47](./47_SCORING_ALGORITHMS.md), PR-7).
- **Cost mode Economy but only expensive models available:** pick the least-cost viable + warn; never silently overspend.
- **Latency-critical (Groq) preferred but down:** failover by score, not by fixed order.
- **OpenRouter model disappeared mid-session:** re-candidate from refreshed cache ([49](./49_MODEL_CACHE.md)).
- **Mid-stream provider failure:** abort stream, failover, resume run from checkpoint if needed ([28](./28_CRASH_RECOVERY.md)).

## 13. Failure Recovery

- The router itself is stateless per request (decisions recorded in the Timeline). A crash mid-route resumes via the reasoning run's checkpoint ([28](./28_CRASH_RECOVERY.md)); quota/cooldown state is persisted ([48](./48_QUOTA_TIER_MANAGEMENT.md)) so recovery respects it.

## 14. Security

- Routing decisions and rationales are logged **without secrets** ([39](./39_LOGGING.md)); provider keys never touch the router (they live in provider adapters/config, [34](./34_API_KEYS.md)). Model output remains untrusted downstream ([15](./15_REASONING_ENGINE.md)).

## 15. Performance

- Candidate scoring is O(candidates) over a cached registry ([49](./49_MODEL_CACHE.md)); negligible vs. model latency. The router optimizes end-to-end latency/cost per the dial. Metrics in [51_METRICS](./51_METRICS.md).

## 16. Testing Strategy

- **Model-first selection:** best-capability model chosen regardless of provider.
- **Cost-mode reweighting:** Economy vs Performance pick different models on the same task.
- **Failover/cooldown/timeout:** injected failures produce smart failover, honor cooldown, respect timeout (ADR-0009).
- **Quality-under-exhaustion:** as quota drains, the router keeps selecting the best *available* model ([48](./48_QUOTA_TIER_MANAGEMENT.md)).
- **Offline fallback:** all cloud unavailable → Ollama. See [35_TESTING](./35_TESTING.md).

## 17. Future Extensions

- Learned routing (bandit/RL over live outcomes); speculative multi-model racing under Performance mode; per-task capability inference; user-visible "why this model" explainer.

## 18. Anti-Patterns

- Static routing tables / fixed provider order (rejected, ADR-0004/0009).
- Provider-first selection (rejected, ADR-0005).
- Hard-failing while a viable model or Ollama remains.
- Putting scoring/quota math in the router (belongs in [47](./47_SCORING_ALGORITHMS.md)/[48](./48_QUOTA_TIER_MANAGEMENT.md)).
- Ignoring the cost/quota mode.

## 19. Things That Must Never Happen

1. Routing selects by provider loyalty instead of best-model-for-task.
2. A request hard-fails while a viable model (incl. Ollama fallback) exists.
3. The router hammers a rate-limited/cooling-down provider.
4. A routing decision is unrecorded (no rationale/metrics).
5. Quota exhaustion collapses quality to a poor default instead of best-available.

## 20. Relationship With Other Subsystems

The consumer-facing brain over [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md); uses [46](./46_CAPABILITY_TAXONOMY.md)/[47](./47_SCORING_ALGORITHMS.md)/[48](./48_QUOTA_TIER_MANAGEMENT.md)/[49](./49_MODEL_CACHE.md)/[50](./50_BENCHMARK_SPEEDTEST.md); serves [15_REASONING_ENGINE](./15_REASONING_ENGINE.md)/[16_COUNCIL_MODE](./16_COUNCIL_MODE.md)/[14_EMBEDDINGS](./14_EMBEDDINGS.md); driven by the two dials of [17_EFFORT_MODES](./17_EFFORT_MODES.md); rationale in [52_ADR_LOG](./52_ADR_LOG.md); offline path per [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md).

## 21. Migration Considerations

- Routing policy/weights are versioned config; the decision-flow + failure-state diagrams remain `OPEN` until implementation finalizes them (then recorded here). Learned routing is additive behind the same interface (PR-8).
