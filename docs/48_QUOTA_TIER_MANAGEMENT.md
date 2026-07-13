# 48 — Quota & Tier Management (Kota ve Kademe Yönetimi)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `yonlendirme/quota/`
> **New** ([52_ADR_LOG](./52_ADR_LOG.md) ADR-0006/0009). Recovered gap: `PROJECT_ANALYSIS.md` L34/L40/L43/L84/L97.
> **Related:** [45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md) · [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md) · [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) · [17_EFFORT_MODES](./17_EFFORT_MODES.md)

---

## 1. Purpose

Defines **quota & tier management** — how turkish.code tracks each provider's usage against its **tier limits**, routes to **preserve quota**, and enforces the core requirement that **answer quality is preserved even as quota is exhausted** ([52](./52_ADR_LOG.md) ADR-0006; `PROJECT_ANALYSIS.md` L97). It also owns provider **cooldown** state used by failover ([45](./45_ROUTING_ORCHESTRATION.md), ADR-0009). This is the difference between a naive multi-provider tool (burns the best quota, then degrades) and turkish.code (spreads load, preserves quality).

## 2. Scope

Quota tracking + persistence, tier awareness, quota-preserving routing signals, cooldown state, and the quality-under-exhaustion policy. Out of scope: the routing loop ([45](./45_ROUTING_ORCHESTRATION.md)), scoring math ([47](./47_SCORING_ALGORITHMS.md)), provider execution ([21](./21_PROVIDER_SYSTEM.md)).

## 3. Goals

1. **Track quota** per provider/tier accurately and **persist** it across restarts (L40/L84).
2. **Preserve quota**: route to spread usage so no single provider is needlessly exhausted (ADR-0006).
3. **Preserve quality under exhaustion**: when preferred quota is gone, keep selecting the best *available* model, not a poor default (L97, ADR-0006).
4. **Cooldown** rate-limited/erroring providers so failover is smart ([45](./45_ROUTING_ORCHESTRATION.md), ADR-0009).

### Non-Goals
- Not billing/payment. Not the router/scorer (consumers). Not key handling ([34](./34_API_KEYS.md)).

## 4. Concepts

- **Tier:** a provider's plan level (free/paid/enterprise) with associated **quota limits** (requests/tokens per window). Declared by the provider adapter ([21](./21_PROVIDER_SYSTEM.md) `tierInfo`).
- **Quota window:** the reset period (per-minute/day/month) per limit.
- **Headroom:** remaining quota in the current window → a routing/scoring factor ([47](./47_SCORING_ALGORITHMS.md)).
- **Cooldown:** a temporary "skip this provider" state entered on rate-limit/error, expiring after a backoff ([45](./45_ROUTING_ORCHESTRATION.md)).

## 5. Quota Tracking & Persistence

```
on each provider call: record usage (requests, tokens) against the provider's tier window
compute headroom = limit − usage(window)
persist usage so restarts don't lose quota accounting (survives crash/restart, 28/29-lite)
reset usage at window boundaries
```

- Persistence store: a lightweight local store (a small SQLite table or JSON file — implementation choice, see [29_STORAGE](./29_STORAGE.md) for options; this subsystem is deliberately light, ADR-0010). It holds **no secrets** ([34](./34_API_KEYS.md)).

> **OPEN (design):** the exact **persistence mechanism, window definitions, and per-provider limit sources** are a recovered gap (`PROJECT_ANALYSIS.md` L84). This doc fixes the *model*; specifics are finalized in implementation and versioned here.

## 6. Quota-Preserving Routing (the signal)

- The quota subsystem exposes **headroom** and **cooldown** per provider to the scorer/router. As headroom drops, `providerScore` drops ([47](./47_SCORING_ALGORITHMS.md) §5), so the router naturally **spreads load** and **saves the best provider's quota** for when it's most needed.
- The **cost/quota mode** ([17](./17_EFFORT_MODES.md)) tunes aggressiveness: *Economy* strongly favors high-headroom/cheap providers; *Performance* is willing to spend premium quota for quality.

## 7. Quality-Under-Exhaustion Policy (core requirement, ADR-0006/L97)

When a preferred model/provider hits quota:
1. **Do not** collapse to a poor default.
2. Re-route to the **best still-available** model by score ([47](./47_SCORING_ALGORITHMS.md)), respecting the **quality floor** (Economy can save cost but not below the task's floor).
3. If *all* cloud quota is exhausted → **Ollama offline fallback** ([32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md)) — reduced but functional, never broken (PR-7).
4. Surface the situation (UI/metrics, [06](./06_COMPONENT_LIBRARY.md)/[51](./51_METRICS.md)) so the user knows quality/cost posture changed.

## 8. Cooldown State Machine

```
[Available] --rate-limit/error--> [CoolingDown(backoff)] --expires--> [Available]
                                       │ repeated failures → longer backoff
router excludes CoolingDown providers from candidates (45 §6)
```

## 9. Directory / Config / Dependencies

```
yonlendirme/quota/
  tracker.py     # usage accounting per tier window
  store.py       # persistence (light; 29 options)
  headroom.py    # headroom + cooldown signals → scorer (47)/router (45)
  policy.py      # quality-under-exhaustion (§7) + mode aggressiveness (17)
```
Limits/windows/cooldown backoff configurable ([33_CONFIGURATION](./33_CONFIGURATION.md)). Depends on [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md) (tierInfo, call events); feeds [45](./45_ROUTING_ORCHESTRATION.md)/[47](./47_SCORING_ALGORITHMS.md); metrics [51](./51_METRICS.md).

## 10. Edge Cases

- **Provider doesn't expose limits:** track observed usage + treat 429s as the signal; conservative headroom estimate.
- **Clock/window skew:** windows are monotonic-time based where possible; a conservative reset avoids over-spending.
- **All providers exhausted/cooling:** Ollama fallback ([32](./32_OFFLINE_FIRST.md)); if none, typed error ([38](./38_ERROR_HANDLING.md)).
- **Restart mid-window:** persisted usage restored so quota isn't "reset for free."
- **Burst that would exceed quota:** the router avoids it by headroom-aware scoring; a hard 429 → cooldown + failover.

## 11. Failure Recovery / Security / Performance

- Usage persistence survives restarts ([28](./28_CRASH_RECOVERY.md)-adjacent); accounting is best-effort and never blocks a call (a tracking failure degrades to conservative estimates, not a hard error). No secrets stored ([34](./34_API_KEYS.md)/[30](./30_SECURITY.md)). O(1) per-call accounting ([31](./31_PERFORMANCE.md)).

## 12. Testing Strategy

- Headroom decreases with usage; resets at window boundary; **persists across restart**.
- Quota-preserving routing spreads load (best provider's quota saved).
- **Quality-under-exhaustion**: draining preferred quota keeps best-available quality (not a poor default) → the marquee test for ADR-0006/L97.
- Cooldown excludes then re-includes providers correctly. See [35_TESTING](./35_TESTING.md).

## 13. Future Extensions

- Predictive quota budgeting across a session; user-set monthly caps per provider; cost dashboards ([51](./51_METRICS.md)); learned window/limit inference.

## 14. Anti-Patterns

- Burning the best provider's quota first, then degrading (the exact failure ADR-0006 prevents).
- Losing quota accounting on restart (must persist).
- Hammering a rate-limited provider (must cooldown).
- Storing quota data with secrets ([34](./34_API_KEYS.md)).

## 15. Things That Must Never Happen

1. Quota exhaustion collapses quality to a poor default (ADR-0006/L97).
2. Quota accounting resets "for free" on restart (must persist).
3. A rate-limited provider is retried without cooldown.
4. All-cloud-exhausted hard-fails when Ollama is available.

## 16. Relationship With Other Subsystems

Feeds signals to [47_SCORING_ALGORITHMS](./47_SCORING_ALGORITHMS.md)/[45_ROUTING_ORCHESTRATION](./45_ROUTING_ORCHESTRATION.md); sourced from [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md); tuned by [17_EFFORT_MODES](./17_EFFORT_MODES.md); offline fallback [32_OFFLINE_FIRST](./32_OFFLINE_FIRST.md); reported in [51_METRICS](./51_METRICS.md); rationale [52_ADR_LOG](./52_ADR_LOG.md).

## 17. Migration Considerations

- The quota model is stable; persistence mechanism + limit sources are `OPEN` until implementation, then versioned. Windows/limits are config; adding per-user caps is additive (PR-18).
