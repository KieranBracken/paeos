# PAEOS-9 Constitutional Ratification Review

Date: 2026-07-21. Question: **is PAEOS-9 a lawful execution architecture** — a pure
composition/execution layer over frozen law (PAEOS-0..8.1), introducing no new
constitution? Not "is it good"; "is it lawful." Method: trace every mechanism to a frozen
source; report every mechanism that cannot be traced, every new concept/authority/stage/
invariant, and every constitutional mechanism that lacks an execution.

## VERDICT: RATIFIED

> Updated 2026-07-21: the three editorial clarifications C1/C2/C3 have been **applied** to
> `spec/PAEOS-9A-runtime-bootstrap.md`. They were labeling/scoping edits, not constitutional
> changes; with them applied the composition is airtight. Verdict advanced from RATIFIED WITH
> CLARIFICATIONS to **RATIFIED**. (Scope note: this review evaluated the runtime *bootstrap*
> document — now `PAEOS-9A`. The separate `spec/PAEOS-9-execution-architecture.md` is a
> distinct, founder-authored document not covered by this review.)

PAEOS-9 (bootstrap) introduces **no new authority, no new lifecycle stage, and no new
invariant.** It is a lawful composition layer: every executing mechanism traces to frozen law.
The three clarifications — two preventing it from *reading* as new law (it never was), one
necessity note — are now applied. No hard violation existed; the architecture is lawful.

---

## Criterion 1 — Constitutional Purity

| Question | Answer | Evidence |
|---|---|---|
| New constitutional concepts? | **No** (with clarification C2) | Every §-mechanism maps to a frozen source (Criterion 2 table). The one extension — SUMMARY/INDEX/EXTRACT corpus compression — traces to PAEOS-3 genesis hand-compilation but must be tagged scaffold-only (C2). |
| New ontology? | **No** (with clarification C1) | RuntimeContext (§3) adds no 5th kernel object; it is an in-memory *projection composing* Goal, EvidenceReq, roles, package, proposals, debt — all existing. But the text blurs three "context" notions and must disambiguate (C1). |
| New authorities? | **No** | The "Runtime" is the existing orchestrator role (ROLE_RESPONSIBILITIES). §7 enforcement *defers to* the WRITE validator (§11); §0/§7 restate CER-5 "recommend, never legislate." No actor gains power. |
| New lifecycle stages? | **No** | Boot steps B1–B9 (§5) are pre-implementation setup, the session-scope analog of 5.5 BOOT-1..8 — not L-states. L01–L19 are untouched; B-steps precede L01. |
| New invariants? | **No** | Every "MUST" in PAEOS-9 executes an existing invariant: "mandatory never truncated" = K10; "freshness gates every transition" = K2; "prompt generated not written" = K5; "same corpus → same hash" = §6.1. No independent invariant is asserted. |
| Redefines existing concepts? | **Risk — clarify (C1)** | "Context" is used for three distinct things: kernel §6.3 Context (per-agent/per-goal), PAEOS-9 CompiledContext (§2 session artifact), PAEOS-9 RuntimeContext (§3 in-memory object). Not a redefinition in substance, but the naming must be disambiguated to prove it. |

**Purity result:** no hard violation. Two clarifications (C1, C2) needed so the text cannot be
*read* as introducing ontology/concepts it does not in substance introduce.

## Criterion 2 — Composition (traceability)

Every major mechanism traces to a frozen source:

| PAEOS-9 mechanism | Traces to |
|---|---|
| Determinism / content_hash (byte-identical) | §6.1 (compile determinism) + F-1 (render grammar) |
| Canonical load order = precedence | §0 / Z-1 |
| Amendment overlay over frozen text (§2 stage 2) | §9.4 amendment lifecycle + Z-1 |
| Contradiction → COMPILE_FAILURE + incident (§2 stage 3) | §6.2 scope-conflict |
| Anti-stale: context bound to corpus_hash, expires on change (§6) | **K2** read-set binding + transitive expiry |
| Compiled context = rebuildable cache, never authoritative (§2.4) | H-08 / D1 |
| Prompt generated, never hand-written (§4) | **K5** + PROMPT_TEMPLATES.md |
| Boot sequence B1–B9 (§5) | 5.5 BOOT-1..8 + FP-1 (one task) + A-16 (worktree) + §13 (genesis lineage) |
| Runtime enforcement, pre-commit rejection (§7) | §11 WRITE validator + X1–X6 + §5.3 mutation matrix + L-state machine + L11 forbidden files |
| Session memory: store permanent, context ephemeral (§8) | D1 crash-only + A2 + K4 append-only + CER-2/CER-3 promotion paths |
| Runtime Health projection (§9) | projection of T5 blocked flag + evidence gaps + §10 budget + gates |
| Genesis-authority scaffold, subsumed by kernel compile() at S3+ (§0) | PAEOS-3 §S1 (founder hand-compiles under genesis authority) + §6 |
| SUMMARY / INDEX / EXTRACT corpus compression (§1.1, §2 stages 4–5) | **Loose** — PAEOS-3 genesis hand-compilation (a document corpus must be selected/digested to fit); NOT in kernel §6.4, which only includes-or-drops whole typed objects → **C2** |

**Composition result:** one mechanism (corpus SUMMARY/EXTRACT) is an extension rather than a
direct trace. It is lawful *as a genesis scaffold* — the kernel's clean include-or-drop works
because its inputs are minimal typed objects (K10-capped constitution + trigger-loaded skills);
PAEOS-9's inputs are the full pre-store markdown corpus, so it must digest to fit, exactly the
hand-compilation PAEOS-3 contemplates. It vanishes at S3+. Requires C2 tagging.

## Criterion 3 — Necessity

| Section | Removable without reducing *execution*? | Note |
|---|---|---|
| §1 Loading, §2 Compiler, §4 Generator, §5 Boot, §6 Refresh, §7 Enforcement, §8 Memory | **No** — these ARE the execution | core; retain |
| §3 RuntimeContext | **No** — the object §4/§7 read | core; retain |
| §9 Runtime Health | **Yes** — observability, not execution | introduces no law; a read-only projection. Execution proceeds without it. Keep as a **non-normative** diagnostic (it usefully answers §7's "why blocked"), but it is not required for lawful execution. **C3.** |
| §0 Framing, §10 Adversarial Review | **Yes** — explanation / self-justification | non-executing; harmless; §10 satisfies CER-1. Mark non-normative. **C3.** |

**Necessity result:** §9, §10, §0 do not execute anything; they introduce no law and reduce no
execution ability if removed. Recommend marking them non-normative (C3); no removal required.

## Criterion 4 — Architectural Leakage

PAEOS-9 names concrete artifacts (git, sha256, JSON, `.runtime/`, boot.log, Claude Code hook).
**This is not leakage into constitutional architecture**, because PAEOS-9 *is* the execution
layer, not the constitution — concreteness belongs here. The specific names are consistent with
frozen law: git (H4), SHA-256/JCS/ULID (pinned constants), Claude Code + hooks (§12.6 reference
adapter). No implementation detail forces a new *constitutional* commitment. **Pass.**

## Criterion 5 — Completeness (every constitutional mechanism has an execution)

| Constitutional mechanism | Executed by |
|---|---|
| K1 evidence-gated promotion | §7 (state won't close without evidence; L14 gate) |
| K2 evidence expiry | §6 freshness check (reused for the context itself) |
| K5 compiled contexts | §2 compiler + §4 generator |
| §5.3 mutation matrix / B-01/B-02 | §7 forbidden.writes; provenance server-stamped |
| §9.4 amendment overlay | §2 stage 2 |
| §0 precedence | §1 load order + §2 stage 1 |
| CER-1..5 | §4 preamble (1), §8 promotion paths (2,3), §7 (5), L17 wiring (4) |
| FP-1..7 | §5 B5/B7 (1,2), §8 session-close (3–7) |
| §10 budget conservation | RuntimeContext.task.budget + §7 budget_exceeded + defer to WRITE validator |
| §13 genesis lineage | §5 B3 constitutional-basis hash check |

No constitutional mechanism was found that exists in law but cannot execute under PAEOS-9. The
reproducible-constitution test (PAEOS-3 S5) and tournaments (L05) are correctly *out of scope*
(a maturity audit and a within-task activity, respectively — not session-bootstrap concerns).
**Pass.**

---

## Criterion 6 — Verdict and required clarifications

**RATIFIED.** PAEOS-9 (bootstrap) is a lawful execution architecture. It legislates nothing; it
composes and executes frozen law. The three clarifications below are **applied** (2026-07-21):

- **C1 (disambiguate "context").** State explicitly that **RuntimeContext (§3) is a
  session-scope projection that *composes* existing objects (Goal, EvidenceReq, roles, package,
  scars, proposals, debt) and is distinct from — a superset view over — the kernel's per-goal
  §6.3 Context; it adds no kernel object and redefines nothing.** Name the three context notions
  once and fix their relationship.
- **C2 (tag scaffold vs permanent).** Explicitly mark the file-loading (§1) and SUMMARY/INDEX/
  EXTRACT corpus compression (§2 stages 4–5) as **genesis-scaffold-only** mechanisms that exist
  because the pre-store corpus is markdown, and that **vanish at S3+** when kernel compile()
  operates on typed store objects (where K10 + trigger-loading make digestion unnecessary).
  This prevents them reading as permanent constitutional law; they trace to PAEOS-3 genesis
  hand-compilation.
- **C3 (mark non-normative).** Label §0, §9, §10 as non-normative (framing / observability /
  self-review). They introduce no law and are not required for lawful execution; retained for
  utility.

None of C1–C3 changes a mechanism; each is a labeling/scoping clarification that makes the
composition provably airtight. No new authority, stage, or invariant exists to remove; no
constitutional mechanism lacks execution. The architecture is lawful.
