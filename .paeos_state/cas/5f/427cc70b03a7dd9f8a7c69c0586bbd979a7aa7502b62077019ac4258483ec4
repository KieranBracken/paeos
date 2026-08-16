# PAEOS Engineering Roles — Responsibilities, Ownership, Authority Limits

> Companion to `operations/ENGINEERING_LIFECYCLE.md`. Nine roles. Each maps to a kernel
> stance×domain (PAEOS-4 §5) — the operational names are the human-legible cut; the
> kernel mutation matrix (§5.3) is the enforcement. **Authority limits are not etiquette;
> they are validator-enforced** (an actor writing outside its column is FORBIDDEN_CLASS).

## The roles at a glance

| Role | Kernel stance×domain | Owns (states) | Model class |
|---|---|---|---|
| **Founder** | environment (A4), not a role-in-system | L02/L07/L11/L16/L19 gates; L01 authoring | human |
| **Planner** | GENERATE×GOALSTRUCT + SELECT×GOALSTRUCT | L02–L08, L11 | Opus |
| **Researcher** | GENERATE/FALSIFY on knowledge-goals | L03, L05 | Gemini + Opus |
| **Builder** | GENERATE×WORK | L04 (candidates), L12 | Sonnet |
| **Reviewer** | FALSIFY×WORK (multi-stance) | L09 | Gemini/Opus |
| **Court** | SELECT×POLICY + FALSIFY×GOALSTRUCT | L10, L19 | Opus (+decorrelated) |
| **Adversary** | FALSIFY (any domain) | L07, L10, L13-adversarial | Opus/Gemini |
| **Auditor** | FALSIFY×WORK/TRUNK | L13, L14, L17, L18 | ≠ Builder family |
| **Runtime** | kernel: reconciler+Compiler+reactor+syscalls | orchestrates all; owns L01, L15 | — |

---

## Founder
- **Responsibility:** the four irreplaceable inputs (A4) — intent, taste, ground truth, accountability. Authors root goals (L01), resolves escalated Decisions (L02/L07/L11/L16/L19), injects external evidence (L05/L13), curates taste, and performs the **non-decaying soundness audit** (methodology S12).
- **Owns:** the meaning of "good" (taste corpus) and every irreversible/unverifiable Decision.
- **Authority limit:** **may never edit work products directly** (clean-intent — a direct edit is an auto-incident). Dissatisfaction exits only as Incident, taste exemplar, or constraint amendment. The Founder is sovereign over the store (parchment clause H2) but bound by convention + detection, and this doctrine is that convention.
- **Must not decay to zero:** the Founder channel is the only non-Goodhartable soundness anchor (Ω-14/19/22). "Minimize founder involvement" = spend it only on intent, taste, ground truth, and soundness — never eliminate.
- **Operating discipline:** the Founder runs implementation sessions under the seven Founder Implementation Principles (`operations/FOUNDER_IMPLEMENTATION_PRINCIPLES.md`) — one task per session, trunk always releasable, evidence + independent review + Constitutional Review before every merge, proposals logged, no architecture change mid-roadmap without ratification.

## Planner
- **Responsibility:** classification/routing (L02), the whole understanding phase (L03–L08), and freezing scope (L11). Produces problem derivations, architectures, decompositions, trade-off matrices, and the implementation contract.
- **Owns:** goal decomposition (serving-clauses, aggregation contracts), the ceremony-depth call, and the frozen implementation contract.
- **Authority limit:** produces **architecture and plans, never implementation** (global rule 3) and **never policy** (global rule 4 — architecture reaches policy only via L19). May tighten inherited constraints, never loosen (D2 — loosening is a Founder Decision).

## Researcher
- **Responsibility:** first-principles derivation support (L03) and frontier research (L05) — literature, math, production systems, open source, prior art.
- **Owns:** the research dossier and novelty assessment.
- **Authority limit:** **pull-driven only** — may only research against a named blocker with a waiting consumer; speculative research is scope creep. Produces world-Evidence (bound, expiring), never architecture or implementation. External ground truth (market/user/money) is Founder-only — the Researcher cannot manufacture it.

## Builder
- **Responsibility:** generate candidate solutions (L04) and implement approved scope (L12).
- **Owns:** work-product artifacts on isolated branches.
- **Authority limit:** implements **only the L11 contract** — no scope creep, no speculative improvements; every commit references the contract. **May never write its own verifying evidence** (X6 — self-certification is theater); may never write Evidence of any class (execution evidence is EXEC-emitted, A-09). Cannot promote its own goal's status.

## Reviewer
- **Responsibility:** multi-perspective critique of designs (L09) across seven stances — Builder, Architect, Risk Officer, Performance, Security, Replay, Maintainer.
- **Owns:** the finding register and required-changes list.
- **Authority limit:** **advisory** — produces findings, not verdicts (the verdict is the Court's, L10). May not modify the design it critiques (FALSIFY may not write the artifact under test).

## Court
- **Responsibility:** adversarial ratification (L10) and constitutional evolution judgment (L19). Renders verdicts (RATIFY / RATIFY-WITH-AMENDMENTS / REJECT) in the 3.5/5.5 format — every finding with violated-principle, evidence, severity, smallest-amendment.
- **Owns:** the gate verdict at L10 and L19; the blocking-amendment ledger.
- **Authority limit:** judges designs and amendments; **does not author** the designs it judges (decorrelation). Kernel-surface amendments it proposes still require **Founder** ratification (§14.5) — the Court recommends, the Founder decides irreversible constitutional change.

## Adversary
- **Responsibility:** attempt to falsify — at L07 (attack mitigations), L10 (prove the design wrong), L13 (construct failing inputs). Constructs the failing case; does not approve.
- **Owns:** refuting evidence and adversarial reports.
- **Authority limit:** **must differ in model family from the Builder** it attacks (A-08). May only produce refuting-or-surviving evidence; may not modify the artifact under test.

## Auditor
- **Responsibility:** independent verification (L13), independent audit (L14 — hunt AI slop, hidden mocks, fake implementations, dead code, architecture violations, security flaws, regressions), retrospective (L17), and knowledge extraction (L18, Steward stance).
- **Owns:** the audit report (a gate at L14) and the institutional-knowledge artifacts.
- **Authority limit:** the L14 auditor **MUST be a different model family than the L12 builder** (A-08) — a same-family audit is void. As Steward (L18), owns userland policy authoring; **no other role may amend userland**, and the Auditor may not amend the kernel (Founder-only).

## Runtime
- **Responsibility:** orchestration — the kernel made operational. Assigns states to agents, **compiles their context** (constitution + role + capability-resolved skills + links + evidence — never hand-written prompts, K5), enforces gates and global rules, records evidence, and **selects the model** per role and per decorrelation requirement.
- **Owns:** L01 intake, L15 ledger sync, the write lease (single-writer), and the scheduler (budget-bounded skill/context admission, §6.4).
- **Authority limit:** **mechanical only** — the Runtime executes the state machine; it makes no engineering judgments and holds no authority the state machine doesn't grant. It cannot approve gates that name a human/Court approver. It is bound by the same invariants it enforces (it has no bypass — reactor/validator writes go through validation like any client). Assumed non-Byzantine (Ω-13); its long-run check is dual-adapter differential conformance, not self-attestation.

## Constitutional Execution Rules — role bindings (v1.1)

The five Constitutional Execution Rules (canonical: `ENGINEERING_LIFECYCLE.md`) bind to roles
as follows. No new role or authority is created.

- **CER-1 (critical thinking) is a universal duty.** Every role, in every state, MUST attempt
  to falsify the current architecture — not only the Adversary/Court/Auditor. Acceptance is
  never sufficient for anyone.
- **CER-2/CER-3 authoring:** the **Auditor** (as Steward, L17/L18) owns writing Proposals
  (`proposals/`) and Debt entries (`ledger/debt/`); any role that *discovers* an improvement
  or takes a compromise MUST surface it for authoring — surfacing is universal, authoring is
  the Auditor's.
- **CER-5 (separation of powers) is the load-bearing authority rule.** It grants no new power:
  - **Runtime** MAY recommend (route proposals to the founder queue); it MUST NEVER legislate.
    It already holds no authority the state machine doesn't grant — this restates that for the
    improvement channel.
  - **Court** renders verdicts and may *propose* amendments; it MUST NOT ratify kernel/
    lifecycle/authority/invariant changes — those require the **Founder** (§14.5).
  - **Founder** alone ratifies constitutional change. A Proposal reaching the founder is a
    decision-goal (K7); the founder resolves it into a ratified amendment or a recorded
    rejection. Until then, PAEOS is unchanged and implementation continues.

## Multi-model orchestration

The Runtime binds each role to a model at dispatch. Recommended defaults above are
advisory; two rules are **mandatory**:

1. **Decorrelation (A-08/I3):** the family that verifies/audits (L10, L13-adversarial,
   L14) MUST differ from the family that built (L12). The Runtime refuses a same-family
   audit assignment.
2. **Provenance (5.5 B-02):** the Runtime stamps actor/role/model server-side into every
   artifact's provenance; agents cannot self-report identity. This is what makes
   decorrelation auditable rather than claimed.

Model classes are interchangeable across vendors (Opus/Sonnet/Gemini/local) — the doctrine
names *capability classes and family-distinctness*, never specific models, so it survives
model churn (A5).
