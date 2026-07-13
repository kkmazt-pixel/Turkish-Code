# 15 — Reasoning Engine (Muhakeme)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth.
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Owner:** Çekirdek `muhakeme/`
> **Related:** [16_COUNCIL_MODE](./16_COUNCIL_MODE.md) · [17_EFFORT_MODES](./17_EFFORT_MODES.md) · [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md) · [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) · [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md) · [13_RAG_SYSTEM](./13_RAG_SYSTEM.md) · [26_TIMELINE](./26_TIMELINE.md)

---

## 1. Purpose

Defines **Muhakeme**, the orchestrator that turns a user goal into actions and answers. It runs the core **plan → act → observe → reflect** loop, assembles context (memory + retrieval + graph), decides when to call tools, applies the effort budget, optionally convenes the council, and produces an inspectable **reasoning trace**. It is the beating heart of the agentic pillar P3 ([00](./00_PROJECT_VISION.md) §5) and the thing every other Çekirdek subsystem serves.

## 2. Scope

The reasoning loop and its state machine, context assembly orchestration, the model-interaction protocol (prompting, tool-calling, streaming), reflection/self-correction, budget enforcement, trace emission, and the hand-offs to Council ([16](./16_COUNCIL_MODE.md)) and Agents ([18](./18_AGENT_SYSTEM.md)). Out of scope: multi-agent orchestration ([18](./18_AGENT_SYSTEM.md)), council deliberation internals ([16](./16_COUNCIL_MODE.md)), tool execution mechanics ([20](./20_TOOL_SYSTEM.md)), provider transport ([21](./21_PROVIDER_SYSTEM.md)).

## 3. Goals

1. A **robust, bounded** agentic loop that plans, uses tools, observes results, and self-corrects toward a goal (PR-14 budgeted).
2. **Transparent reasoning**: every step recorded as a structured trace the user can inspect (P4/P5, [26](./26_TIMELINE.md)).
3. **Grounded**: reasoning is fed cited context from memory/RAG/graph, reducing hallucination ([11](./11_MEMORY_SYSTEM.md)/[13](./13_RAG_SYSTEM.md)/[12](./12_KNOWLEDGE_GRAPH.md)).
4. **Provider-agnostic**: works with local or cloud models behind the provider boundary ([21](./21_PROVIDER_SYSTEM.md)), including models without native tool-calling (PR-8/PR-7).
5. **Interruptible & recoverable**: cancel any time; resume after crash ([10](./10_IPC.md)/[28](./28_CRASH_RECOVERY.md)).
6. **Turkish-native reasoning** by default (PR-12).

### Non-Goals
- Not the multi-agent hierarchy ([18](./18_AGENT_SYSTEM.md) builds on Muhakeme). Not the tool implementations ([20](./20_TOOL_SYSTEM.md)).

## 4. The Reasoning Loop

```
GOAL (user message + session state)
  │
  ▼
[ASSEMBLE CONTEXT]  ← memory recall (11) + retrieval (13) + graph facts (12)
  │                   + skills (19) + instructions + locale (tr)
  ▼
[PLAN]  ── produce/adjust a plan (steps, tool intents) within budget (17)
  │
  ▼
[ACT]  ── take the next step:
  │        • answer directly, OR
  │        • call a tool (20) → request over Core Channel → permission (24) → result
  │        • (optionally) convene the Divan (16) for a hard sub-decision
  ▼
[OBSERVE]  ── incorporate tool result / new info; update state & trace
  │
  ▼
[REFLECT]  ── did this make progress? errors? need re-plan?  (bounded reflection passes)
  │
  ├── not done & budget remains → back to PLAN/ACT
  └── done OR budget exhausted → [FINALIZE] → answer + trace + persisted state
```

- The loop is **explicitly bounded** by the effort budget ([17](./17_EFFORT_MODES.md)): max iterations, max tool calls, max tokens, max reflection passes, max wall-clock. No unbounded loops (PR-14) — a fundamental safety property.
- Each phase emits **trace events** (notifications, [10](./10_IPC.md)) streamed live to the UI ([03](./03_UI_SYSTEM.md)/[06](./06_COMPONENT_LIBRARY.md) §6.2).

## 5. Reasoning Trace (Muhakeme İzi)

Every run produces a structured, persisted trace ([26](./26_TIMELINE.md)):

```
TraceStep {
  runId, seq, kind: context|plan|act|tool_call|observe|reflect|council|final,
  text: string (Turkish),           // the human-readable reasoning
  refs: [source]                    // cited memory/chunks/graph nodes (11/12/13)
  tool?: {name, args, resultRef}    // for tool_call/observe (20)
  councilRef?: divanRunId           // for council steps (16)
  tokens, model, timing
}
```

- The trace is **the** artifact behind explainability (P4): the user can always see *what the agent considered, retrieved, did, and why*.
- Sensitive content in traces is redacted per [30](./30_SECURITY.md); traces never egress without consent.
- The depth/verbosity of the trace scales with effort mode ([17](./17_EFFORT_MODES.md)).

## 6. Model Interaction Protocol

- **Prompt assembly:** a layered prompt = system/identity (Turkish-native persona, [04](./04_TURKISH_DESIGN_LANGUAGE.md) voice) + active skills ([19](./19_SKILLS_SYSTEM.md)) + assembled context (§4) + feedback/profile memory ([11](./11_MEMORY_SYSTEM.md)) + tool schemas ([20](./20_TOOL_SYSTEM.md)) + the conversation. Assembly is budget-packed ([13](./13_RAG_SYSTEM.md) §9, [17](./17_EFFORT_MODES.md)).
- **Tool calling:** uses the provider's native tool/function-calling where available; for models without it, a **structured-output fallback** (a strict JSON action grammar the engine parses) provides equivalent capability (PR-7/PR-8). Either way, tool *requests* are validated against tool schemas before execution ([20](./20_TOOL_SYSTEM.md)).
- **Streaming:** token deltas and step boundaries stream as notifications ([10](./10_IPC.md)); the engine can be cancelled mid-generation.
- **Determinism boundary (PR-15):** model non-determinism is isolated here; inputs (assembled prompt) and outputs are recorded in the Timeline so the *system's* behavior is replayable/auditable even though the *model* may vary.

## 7. Reflection & Self-Correction

- After a tool result or a candidate answer, a **bounded reflection** pass checks: Did the tool error? Is the answer grounded in the cited context? Are there contradictions? Should the plan change?
- On detected error/low-confidence, the engine re-plans (within budget) rather than emitting a wrong answer. Repeated failure of the same approach triggers a strategy change or a graceful "couldn't complete, here's what I found" (PR-7/PR-10) — never a confident fabrication.
- Reflection depth is effort-scaled (`Hızlı`: minimal; `Derin/Maksimum`: thorough, may invoke the Divan [16]).

## 8. Council & Agent Hand-offs

- **Council ([16](./16_COUNCIL_MODE.md)):** for a hard decision (ambiguous design choice, high-stakes plan), Muhakeme can convene the Divan; the synthesized result returns as an `observe`/`council` step. Whether/when to convene is effort- and policy-driven ([17](./17_EFFORT_MODES.md)).
- **Agents ([18](./18_AGENT_SYSTEM.md)):** the multi-agent system composes Muhakeme runs — an orchestrator agent decomposes a goal and delegates sub-goals, each executed by a Muhakeme run with a scoped context/tool grant. Muhakeme is the *unit*; Agents are the *composition*.

## 9. State Machine

```
[Init] → [AssembleContext] → [Plan] → [Act] ⇄ [AwaitTool/Permission]
                                  │              │ (permission prompt, doc 24)
                                  ▼              ▼
                             [Observe] ──────▶ [Reflect]
                                  │                 │
                    budget left & !done ◀───────────┤
                                  ▼                 ▼
                              (loop)            [Finalize] → [Done]
Any → [Cancelled] (on $/cancel) | [Failed] (typed error, recoverable)
Every transition → checkpoint to journal (doc 28) + trace event (doc 26)
```

## 10. Data Flow

```
session.send (10) → Muhakeme.run
   → Bellek (11) recall + Getirim (13) retrieve + Graf (12) facts → context
   → Provider (21) chat (stream) → plan/act
   → Tool (20) via İzin/Kabuk (24/08) → result
   → Reflect → (loop) → Finalize
   → trace + state persisted (26/28); final result returned (10)
```

## 11. Directory Structure

```
muhakeme/
  engine.py       # the loop + state machine
  context.py      # context assembly orchestration (calls 11/12/13/19)
  prompt.py       # layered prompt builder (tr persona, budgets)
  toolcall.py     # native + structured-output tool-call handling (20)
  reflect.py      # reflection/self-correction
  trace.py        # trace emission (26)
  policy.py       # when to reflect/council, budget application (17/16)
```

## 12. Configuration

- Effort mode selects budgets/policy ([17](./17_EFFORT_MODES.md)). Configurable: base system persona, default locale (tr), reflection thresholds, council-trigger policy, and grounding strictness ([33](./33_CONFIGURATION.md)).

## 13. Dependencies

- [11_MEMORY_SYSTEM](./11_MEMORY_SYSTEM.md), [12_KNOWLEDGE_GRAPH](./12_KNOWLEDGE_GRAPH.md), [13_RAG_SYSTEM](./13_RAG_SYSTEM.md), [19_SKILLS_SYSTEM](./19_SKILLS_SYSTEM.md), [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md), [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md), [16_COUNCIL_MODE](./16_COUNCIL_MODE.md), [17_EFFORT_MODES](./17_EFFORT_MODES.md), [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md), [26_TIMELINE](./26_TIMELINE.md), [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md).

## 14. Edge Cases

- **Budget exhausted mid-task:** finalize gracefully with partial results + a clear "reached the effort limit" note and an offer to continue at higher effort (PR-7).
- **Tool denied by permission ([24](./24_PERMISSION_SYSTEM.md)):** observe the denial, adapt the plan (find another route or ask the user), never bypass.
- **Model emits malformed tool call:** the structured parser rejects; the engine re-prompts with a corrective instruction (bounded retries).
- **Hallucinated file/symbol:** grounding check against graph/retrieval ([12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)) catches references to nonexistent entities; the engine corrects.
- **Infinite-loop tendency** (same action repeatedly): loop-detection + budget caps break it (PR-14).
- **Provider failure mid-stream:** typed error → retry/failover per [21](./21_PROVIDER_SYSTEM.md); resume from last checkpoint if possible ([28](./28_CRASH_RECOVERY.md)).
- **Cancellation:** stops the loop and any in-flight tool/agent/council; emits `cancelled`; partial edits protected by snapshots ([27](./27_SNAPSHOTS.md)).
- **Non-tool-calling model:** structured-output fallback (§6).

## 15. Failure Recovery

- Every transition checkpoints to the journal ([28](./28_CRASH_RECOVERY.md)); after a crash the run resumes from the last checkpoint (re-observe/re-plan as needed).
- A failed run is typed and recoverable; the trace explains where it stopped (P4).

## 16. Security

- Treats model output as untrusted (prompt injection): tool requests are schema-validated and permissioned ([20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)); the engine never lets model text directly trigger a side effect (PR-3). Retrieved/tool content injected into context is clearly delimited to reduce injection leverage. Traces redact secrets ([30](./30_SECURITY.md)).

## 17. Performance

- Stream early (first tokens fast); parallelize context assembly (retrieval + memory + graph concurrently); cache assembled context for follow-ups; effort-scaled work. Budgets/metrics in [31_PERFORMANCE](./31_PERFORMANCE.md).

## 18. Testing Strategy

- **Loop-bound tests:** budgets strictly enforced; no unbounded iteration/tool fan-out.
- **Grounding tests:** answers cite provided context; hallucinated references are caught.
- **Tool-call fallback tests:** structured-output path matches native tool-calling behavior.
- **Reflection/self-correction tests:** an injected tool error leads to re-plan, not a wrong answer.
- **Cancellation/resume tests** ([28](./28_CRASH_RECOVERY.md)).
- **Determinism harness:** replay assembled-prompt fixtures → deterministic system behavior (PR-15). See [35_TESTING](./35_TESTING.md).

## 19. Future Extensions

- Pluggable reasoning strategies (ReAct, tree/graph-of-thought, plan-and-execute) behind a strategy interface; learned effort/council-trigger policies; speculative tool execution; richer grounding verifiers.

## 20. Examples

- "Testleri çalıştır ve kırılanları düzelt": PLAN(run tests → analyze failures → edit → re-run) → ACT(tool `shell.exec` for tests, permission-gated) → OBSERVE(failures) → retrieve failing code ([13](./13_RAG_SYSTEM.md)) → edit via `fs.write` (snapshot [27]) → re-run → REFLECT(green?) → FINALIZE, with the full trace visible.

## 21. Anti-Patterns

- Unbounded loops / uncapped tool calls / uncapped reflection.
- Letting model text trigger a side effect without schema+permission.
- Emitting confident answers ungrounded in retrieved context.
- Hiding reasoning (no trace) — breaks P4.
- Baking a single provider's tool-calling format into the engine (must be provider-agnostic).

## 22. Things That Must Never Happen

1. The loop runs without hard budget bounds.
2. A tool executes without schema validation + permission.
3. A run produces no inspectable trace.
4. Model output directly performs a side effect (bypassing [20](./20_TOOL_SYSTEM.md)/[24](./24_PERMISSION_SYSTEM.md)).
5. A crash loses an in-flight run irrecoverably (must checkpoint).

## 23. Relationship With Other Subsystems

Muhakeme is orchestrated over [10_IPC](./10_IPC.md); consumes context from [11](./11_MEMORY_SYSTEM.md)/[12](./12_KNOWLEDGE_GRAPH.md)/[13](./13_RAG_SYSTEM.md)/[19](./19_SKILLS_SYSTEM.md); acts via [20_TOOL_SYSTEM](./20_TOOL_SYSTEM.md) under [24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md); calls models via [21_PROVIDER_SYSTEM](./21_PROVIDER_SYSTEM.md); is bounded by [17_EFFORT_MODES](./17_EFFORT_MODES.md); can convene [16_COUNCIL_MODE](./16_COUNCIL_MODE.md); is composed by [18_AGENT_SYSTEM](./18_AGENT_SYSTEM.md); records to [26_TIMELINE](./26_TIMELINE.md) and checkpoints to [28_CRASH_RECOVERY](./28_CRASH_RECOVERY.md).

## 24. Migration Considerations

- The trace schema is versioned ([26](./26_TIMELINE.md)); additive changes preferred (PR-18). New reasoning strategies are added behind the strategy interface without breaking the loop contract. Provider/tool-calling changes are absorbed by `toolcall.py` (PR-8).
