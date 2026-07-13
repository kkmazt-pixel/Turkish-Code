# 40 — Documentation Rules (Dokümantasyon Kuralları)

> Part of the **turkish.code Engineering Bible**. Canonical source of truth (meta).
> **Status:** Canonical · **Version:** 1.0 · **Last updated:** 2026-07-12
> **Related:** [44_GLOSSARY](./44_GLOSSARY.md) · [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md) · [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) · [AGENTS.md](./AGENTS.md)

---

## 1. Purpose

The rules that govern **this documentation itself** — the `docs/` Engineering Bible. It defines the standard document template, the single-responsibility + no-duplication discipline, cross-referencing, terminology governance, and how docs stay in sync with code. The meta-goal ([00](./00_PROJECT_VISION.md) §8 #5) is that a new AI agent can implement or extend any subsystem using only these docs; that goal is only achievable if the docs obey consistent rules. This document is those rules.

## 2. Scope

Document structure/template, the one-responsibility-per-doc rule, no-duplication + cross-referencing, terminology governance, doc-code synchronization, status/versioning, and language. Out of scope: code style ([36](./36_CODING_STANDARDS.md)), the implementation workflow ([41](./41_IMPLEMENTATION_RULES.md)).

## 3. Core Documentation Principles

- **Single source of truth.** Each fact lives in exactly one document; everything else **cross-references** it (PR-8 for docs). Duplication is the enemy — it drifts and contradicts.
- **One responsibility per document.** A doc owns one subsystem/concern (mirrors PR-13). If a doc needs to explain another subsystem, it links, not re-explains.
- **Detail over brevity.** The Bible optimizes for completeness and unambiguity, not concision — a new implementer must not have to guess ([00](./00_PROJECT_VISION.md) mandate).
- **Consistent terminology.** Every term comes from [44_GLOSSARY](./44_GLOSSARY.md); no synonyms, no drift (the forbidden-alias table is binding).
- **Legible to machines and humans** (PR-11): predictable structure, explicit cross-links, schemas over prose where a contract exists.
- **Docs are canonical intent.** Where docs and code disagree, that's a bug in one of them — resolved deliberately (§8), never ignored.

## 4. Standard Document Template

Every subsystem document follows this section order (adapt where a section is genuinely N/A, but prefer to state "N/A — why"):

```
# NN — Title (Turkish Name)
> header: status, version, date, owner, related links
1. Purpose            13. Configuration
2. Scope              14. Dependencies
3. Goals (& Non-Goals) 15. Edge Cases
4. Responsibilities    16. Failure Recovery
   /Architecture       17. Security
5. Architecture        18. Performance
6. Data Flow           19. Testing Strategy
7. Lifecycle           20. Future Extensions
8. State Machine       21. Examples
9. Directory Structure 22. Anti-Patterns
10. Public APIs        23. Things That Must Never Happen
11. Internal APIs      24. Relationship With Other Subsystems
12. Interfaces         25. Migration Considerations
```

- The exact numbering may vary slightly per doc, but **every** doc must cover: Purpose, Scope, Goals, Architecture/Responsibilities, Edge Cases, Failure Recovery, Security, Testing, Anti-patterns, "Must never happen," Relationships, and Migration. These are the load-bearing sections.
- Meta/overview docs (vision, glossary, index, roadmap) may use a tailored structure but still lead with Purpose + Scope.

## 5. Header Convention

Each doc starts with: the numbered title (+ Turkish name), a one-line "part of the Engineering Bible" banner, **Status** (Canonical/Draft/Deprecated), **Version**, **Last updated** (absolute date), **Owner** (subsystem/module), and **Related** cross-links. This makes provenance and freshness explicit.

## 6. Cross-Referencing (No Duplication)

- Reference other docs by relative link with the number: `[24_PERMISSION_SYSTEM](./24_PERMISSION_SYSTEM.md)`, and often a specific section.
- **Do not restate** another subsystem's internals; state the *interface/contract* you rely on and link to the owning doc. Example: [20](./20_TOOL_SYSTEM.md) says "permissioned per [24](./24_PERMISSION_SYSTEM.md)" — it does not re-describe the permission model.
- When two docs seem to need the same content, that content belongs in **one** of them (or a third, more fundamental one) and both link to it. Common invariants live in their owning doc ([30](./30_SECURITY.md) §12 gathers the security invariants once; others link to it).

## 7. Terminology Governance

- [44_GLOSSARY](./44_GLOSSARY.md) is the terminology authority. New terms are **added there in the same change** that introduces them. Forbidden aliases (glossary §12) are never used.
- Turkish subsystem names are used consistently ([44](./44_GLOSSARY.md)); code identifiers use the ASCII-transliteration rule ([44](./44_GLOSSARY.md) §2, [36](./36_CODING_STANDARDS.md)).
- A rename is a **documented migration**, not a silent edit: update the glossary, the [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md), and every referencing doc in one change.

## 8. Doc–Code Synchronization

- **Docs are written/updated *with* the code, not after.** A change to a subsystem's contract, invariant, or behavior updates its doc in the same change ([41](./41_IMPLEMENTATION_RULES.md) requires it).
- **Contracts are codegen'd from schema** ([10](./10_IPC.md)/[29](./29_STORAGE.md)); the doc describes intent + links to the schema, so the *machine-checked* contract and the *human* explanation stay aligned.
- **Drift check:** contradictions between a doc and code are treated as defects; the [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) cross-reference map helps find affected docs when an invariant changes.
- When code proves a doc wrong, fix the doc (or the code) deliberately and note it — never let a stale doc mislead a future implementer/AI.

## 9. Consistency Passes

- After a batch of docs, run a **consistency pass**: resolve contradictions, merge duplicated concepts into their owning doc, and align terminology (this is the process the Bible itself was built with — [42](./42_ROADMAP.md) §docs). The [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md) tracks cross-references to make this tractable.

## 10. Language

- Documentation is written in **clear English** (the shared engineering lingua franca for implementers), while the **product** is Turkish-first ([04](./04_TURKISH_DESIGN_LANGUAGE.md)). Turkish subsystem names appear in prose with correct orthography; identifiers use transliteration. (Rationale: docs must be maximally implementable by any developer/AI; the product's Turkish-first identity is a runtime property, documented *in* English.)
- User-facing strings in examples are Turkish (they're product copy).

## 11. Diagrams

- ASCII/Mermaid diagrams inline (offline-friendly, versionable, diff-able). No external image dependencies (mirrors the no-CDN ethos, [04](./04_TURKISH_DESIGN_LANGUAGE.md)). Keep diagrams in sync with the prose.

## 12. Status Lifecycle

```
Draft → Canonical → (Deprecated → Removed)
```
- Only **Canonical** docs are binding. Deprecated docs stay until superseding content is Canonical and references are updated. Removal is a migration.

## 13. Edge Cases

- **A concept spans two subsystems:** it belongs to the more fundamental one; the other links. (E.g., the egress choke point is described in [08](./08_TAURI_ARCHITECTURE.md)/[30](./30_SECURITY.md); [21](./21_PROVIDER_SYSTEM.md) links to it.)
- **A new subsystem:** add a numbered doc following the template, register it in [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md), add terms to [44](./44_GLOSSARY.md), and wire cross-references both ways.
- **Contradiction found:** stop and reconcile (update the wrong doc + the index); never leave two conflicting statements.
- **Doc gets too long/multi-topic:** split by responsibility (PR-13 for docs) and cross-link.

## 14. Testing / Verification of Docs

- **Link check:** all cross-reference links resolve (a CI doc-lint).
- **Terminology check:** no forbidden aliases ([44](./44_GLOSSARY.md) §12); referenced terms exist in the glossary.
- **Template check:** each subsystem doc has the load-bearing sections (§4).
- **Index coverage:** every doc is registered in [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md). (These checks are part of [35](./35_TESTING.md)'s doc-lint stage.)

## 15. Security (of docs)

- Docs contain **no secrets** and no real credentials in examples ([30](./30_SECURITY.md)/[34](./34_API_KEYS.md)); example keys are obviously fake. Docs describe security invariants but never include exploit-enabling secrets or real infrastructure details.

## 16. Future Extensions

- Auto-generated API reference from schemas; a docs site build; a "docs coverage" report (which subsystems have full template sections); localized (Turkish) docs edition for contributors who prefer it.

## 17. Anti-Patterns

- Duplicating another doc's content instead of linking.
- Inventing a synonym for a glossary term.
- Updating code without updating its doc (drift).
- A doc covering multiple subsystems.
- External image/link dependencies in docs.
- Leaving a known doc–code contradiction unresolved.
- Real secrets in examples.

## 18. Things That Must Never Happen

1. The same fact is authoritatively stated in two docs (must be one + links).
2. A term is used that contradicts or bypasses [44_GLOSSARY](./44_GLOSSARY.md).
3. A subsystem's contract/behavior changes without its doc updating in the same change.
4. A doc claims something the code contradicts and it's left unreconciled.
5. A real secret/credential appears in documentation.

## 19. Relationship With Other Subsystems

Governs all docs; terminology from [44_GLOSSARY](./44_GLOSSARY.md); registered/mapped by [ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md); enforced alongside the workflow in [41_IMPLEMENTATION_RULES](./41_IMPLEMENTATION_RULES.md); doc-lint in [35_TESTING](./35_TESTING.md); serves the AI-onboarding goal realized in [AGENTS.md](./AGENTS.md).

## 20. Migration Considerations

- The template/rules here are versioned; changing the template applies to *new* docs and is back-filled deliberately. A terminology change ripples via the cross-reference map ([ARCHITECTURE_INDEX](./ARCHITECTURE_INDEX.md)). Deprecations follow the status lifecycle (§12), never silent deletion.
