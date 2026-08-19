# PAEOS Canonical 19-Layer Freeze — v1

**Status: FROZEN EXTRACTION — forensic, non-interpretive.**
**Date of extraction: 2026-08-19.** Extracted mechanically by script (disk → disk); every layer
section and state block below is verbatim from the cited sources. Nothing in this document
amends, reconciles, or reinterprets the sources. Conflicts between sources of different tiers are
RECORDED, not resolved (§4).

## 0. Source corpus, precedence, hashes

| Tier | Source | Version/ratification | sha256 |
|---|---|---|---|
| 1 | `operations/ENGINEERING_LIFECYCLE.md` | FROZEN v1.0 2026-07-20; CER v1.2 rules founder-ratified 2026-07-27 | `6eb3b80b02c2c3626e286a9f33292d2b85f9e641040333696e308382c3521e45` |
| 2 | `operations/WORKFLOW_STATE_MACHINE.yaml` | v1.1, `frozen: true`, founder-ratified 2026-07-21 | `3a2d6a1cf2ffa6b291e3bc0419ff1e7faa1b7be41c1b771174aee16704cf4cf8` |

Precedence (per founder directive 2026-08-19): original constitutional PAEOS corpus (highest) →
PAEOS-9 execution architecture / ENGINEERING_LIFECYCLE / ratified amendments & IPs / kernel
constitutional invariants → this Freeze → implementation conformance → current code → audit
reports → AI opinions (lowest). Secondary documents (research backlog reconstructions, audit
notes) do NOT redefine the lifecycle.

## 1. Canonical layer index (mechanically extracted)

| ID | Canonical name (from Source A heading) | Source A lines | Source B state lines |
|---|---|---|---|
| L01 | Intake | 49–57 | 105–117 |
| L02 | Triage | 58–68 | 118–133 |
| L03 | First-Principles Re-Derivation | 69–77 | 134–145 |
| L04 | Ambitious Ideation | 78–86 | 146–157 |
| L05 | Frontier Research | 87–95 | 158–170 |
| L06 | Trade-off Analysis | 96–104 | 171–182 |
| L07 | Trade-off Mitigation | 105–113 | 183–195 |
| L08 | System Design | 114–124 | 196–207 |
| L09 | Multi-Perspective Critique | 125–133 | 208–220 |
| L10 | Adversarial Review | 134–142 | 221–235 |
| L11 | Formal Planning | 143–153 | 236–248 |
| L12 | Branch Implementation | 154–162 | 249–260 |
| L13 | Verification | 163–171 | 261–272 |
| L14 | Independent Audit | 172–182 | 273–287 |
| L15 | Documentation & Ledger | 183–191 | 288–300 |
| L16 | Promotion Decision | 192–202 | 301–313 |
| L17 | Retrospective + Constitutional Review | 203–211 | 314–328 |
| L18 | Knowledge Extraction | 212–222 | 329–340 |
| L19 | Constitutional Evolution | 223–317 | 341–375 |

## 2. Verbatim layer sections (Source A: ENGINEERING_LIFECYCLE.md)

### L01 — verbatim (Source A lines 49–57)

#### L01 — Intake · *Runtime + any source · model: n/a*
- **Purpose:** capture an idea, bug, research question, architectural concern, or improvement.
- **Entry:** a source (founder, agent, incident, external signal) has something worth recording.
- **Required artifacts:** initial description; source; motivation; expected value; initial classification.
- **Exit:** the artifact exists as a `Goal(kind=work|incident)` in `declared`.
- **Approval:** none (capture is unconditional).
- **Failure:** malformed/empty intent → not admitted.
- **Evidence produced:** the declared artifact itself (its existence is the evidence for L02).

### L02 — verbatim (Source A lines 58–68)

#### L02 — Triage · *Planner (Router) · model: Opus/Sonnet*
- **Purpose:** decide whether this deserves engineering effort, and at what ceremony depth.
- **Entry:** a declared artifact from L01.
- **Required artifacts:** disposition (Keep / Merge / Reject / Dormant / Research / Immediate-Priority); priority; scope; duplicate analysis; **forbidden-zone analysis**; **classification (v × r) → ceremony depth**.
- **Exit:** exactly one disposition + a classification Evidence object (bound, expiring — A-14) + a DispatchRecord.
- **Approval:** Reject/Dormant on founder-authored intent → founder confirmation; else automatic.
- **Failure:** unclassifiable → route to L05 (Research) or escalate a Decision.
- **Evidence produced:** disposition record; classification Evidence; duplicate/forbidden-zone findings.

### Phase II — Understanding *(Trace-B in full; auto-discharged for Trace-A)*

### L03 — verbatim (Source A lines 69–77)

#### L03 — First-Principles Re-Derivation · *Planner + Researcher · model: Opus*
- **Purpose:** derive the problem from first principles — no assumptions, no implementation. "What must be true?"
- **Entry:** L02 = Keep/Research/Immediate AND ceremony depth ≥ Trace-B (else auto-pass).
- **Required artifacts:** first-principles model; constraints; fundamental laws.
- **Exit:** the problem is independently derived, not inherited.
- **Approval:** none (internal understanding).
- **Failure:** cannot derive → spawn L05 Frontier Research for missing knowledge.
- **Evidence produced:** the derivation artifact (challenges/validates inherited framing).

### L04 — verbatim (Source A lines 78–86)

#### L04 — Ambitious Ideation · *Planner + Builder · model: Opus/Gemini*
- **Purpose:** generate the strongest possible solution; ignore practicality; aim for the ideal.
- **Entry:** L03 complete.
- **Required artifacts:** alternative architectures; idealized solution; failure modes.
- **Exit:** the candidate space is genuinely wide (decorrelated options exist to select among).
- **Approval:** none.
- **Failure:** degenerate space (all candidates ≈ identical) → collapse to single approach, note it.
- **Evidence produced:** candidate architecture set (feeds L06/L08 tournament).

### L05 — verbatim (Source A lines 87–95)

#### L05 — Frontier Research · *Researcher · model: Gemini (web/frontier) + Opus*
- **Purpose:** establish state of the art — literature, mathematics, production systems, open source.
- **Entry:** a blocked understanding (L03/L04/L06) needs external knowledge; **pull-driven, never a phase**.
- **Required artifacts:** research dossier; novelty assessment; prior art.
- **Exit:** the named blocker resolves; a consumer stage can proceed.
- **Approval:** founder Inject for market/user/money ground truth the system cannot generate.
- **Failure:** consumer-less/unbounded research → scope-creep incident (findings expire, K2).
- **Evidence produced:** research dossier (bound, expiring).

### L06 — verbatim (Source A lines 96–104)

#### L06 — Trade-off Analysis · *Planner + Reviewer · model: Opus*
- **Purpose:** identify every important trade-off (latency, accuracy, memory, risk, maintainability, complexity, …).
- **Entry:** ≥1 viable approach from L04.
- **Required artifacts:** trade-off matrix (axes × approaches).
- **Exit:** the decision axes are explicit and comparable for a Judge.
- **Approval:** none.
- **Failure:** hidden/omitted axis surfaced later → incident against this matrix.
- **Evidence produced:** trade-off matrix (the Judge's selection basis).

### L07 — verbatim (Source A lines 105–113)

#### L07 — Trade-off Mitigation · *Planner + Adversary · model: Opus*
- **Purpose:** design safeguards for every important compromise.
- **Entry:** L06 matrix exists with material risks.
- **Required artifacts:** mitigation catalogue; kill switches; fallback behaviour; shadow mode; safety constraints.
- **Exit:** every high-severity trade-off has a named safeguard or an accepted-risk record.
- **Approval:** irreversible accepted-risks → founder Decision.
- **Failure:** an unmitigated high-severity risk with no accepted-risk record → blocks L08.
- **Evidence produced:** mitigation catalogue.

### L08 — verbatim (Source A lines 114–124)

#### L08 — System Design · *Planner (Decomposer) · model: Opus*
- **Purpose:** produce the architecture — no implementation.
- **Entry:** selected approach (L04/L06) + mitigations (L07).
- **Required artifacts:** component graph; interfaces; data flow; state machines; schemas; storage; APIs; dependencies. For decomposition: child goals + serving-clauses + aggregation contract.
- **Exit:** intent-conservation audit passes (no orphans/gaps); verification seams are also good product boundaries (Ω-24); constraints tightened only (D2).
- **Approval:** high-fanout irreversible nodes → Court (L09/L10) then possibly founder Decision.
- **Failure:** orphan/gap/loosened-constraint → redesign or escalate.
- **Evidence produced:** the architecture artifact set; conservation + spec-sufficiency audit records.

### Phase III — Constitutional Review

### L09 — verbatim (Source A lines 125–133)

#### L09 — Multi-Perspective Critique · *Reviewer (7 perspectives) · model: Gemini/Opus (decorrelated)*
- **Purpose:** attack the design from every stance — Builder, Architect, Risk Officer, Performance, Security, Replay, Maintainer.
- **Entry:** an architecture artifact from L08.
- **Required artifacts:** finding register; required changes.
- **Exit:** every perspective has reported; required changes are logged.
- **Approval:** none (advisory to L10/L11).
- **Failure:** a perspective is skipped → the review is incomplete, cannot advance.
- **Evidence produced:** per-perspective finding register.

### L10 — verbatim (Source A lines 134–142)

#### L10 — Adversarial Review · *Court + Adversary · model: Opus/Gemini (≠ Builder family)*
- **Purpose:** attempt to prove the design wrong — contradictions, hidden assumptions, circular reasoning, economic/security/scaling failures, emergent behaviour.
- **Entry:** L08 design + L09 findings.
- **Required artifacts:** adversarial report; blocking amendments.
- **Exit:** a verdict (RATIFY / RATIFY-WITH-AMENDMENTS / REJECT) with every finding carrying violated-principle · evidence · severity · smallest-amendment (the 3.5/5.5 court format).
- **Approval:** **Court verdict is a gate** — REJECT halts; amendments must be resolved.
- **Failure:** a proven contradiction/blocking finding → design returns to L08.
- **Evidence produced:** adversarial report; blocking-amendment ledger.

### L11 — verbatim (Source A lines 143–153)

#### L11 — Formal Planning · *Planner · model: Opus*
- **Purpose:** freeze implementation scope — the implementation contract.
- **Entry:** L10 verdict = RATIFY(-WITH-AMENDMENTS, resolved).
- **Required artifacts:** affected files; **forbidden files**; rollback plan; acceptance criteria; test strategy; dependencies.
- **Exit:** implementation contract approved (this is the artifact L12 is bound to).
- **Approval:** founder Decision for irreversible scope; else Planner + Court sign-off.
- **Failure:** ambiguous/incomplete contract → incident (every ambiguity is an incident).
- **Evidence produced:** the frozen implementation contract.

### Phase IV — Engineering

### L12 — verbatim (Source A lines 154–162)

#### L12 — Branch Implementation · *Builder · model: Sonnet (fast generation)*
- **Purpose:** implement **only** the approved scope.
- **Entry:** approved implementation contract (L11) on an isolated branch/worktree (A-16).
- **Required artifacts:** working implementation; commits each referencing the L11 contract.
- **Exit:** the scope is built and runs (`executed`); **no scope creep, no speculative improvements**.
- **Approval:** none (the Builder self-reports; it may NOT self-verify — X6).
- **Failure:** scope creep, or cannot build within budget → incident (cap-overrun, A-12).
- **Evidence produced:** implementation artifacts + builder execution self-report (not promoting evidence).

### L13 — verbatim (Source A lines 163–171)

#### L13 — Verification · *Auditor/Runtime (mechanical) + Adversary · model: local+Sonnet, then Opus*
- **Purpose:** prove correctness. Order: Compile → Lint → Unit → Integration → Simulation → Replay → Performance.
- **Entry:** `executed` implementation from L12.
- **Required artifacts:** evidence records; test logs; coverage.
- **Exit:** the acceptance criteria (L11) are satisfied by **live, signed, independent** evidence (A-09), repeatability-aware (flaky ≠ refutation, Ω-01); no live refutation.
- **Approval:** none (mechanical evidence is self-approving via EXEC signature).
- **Failure:** any refutation → regress + incident (L19/Capture).
- **Evidence produced:** signed execution evidence, test logs, coverage, perf numbers.

### L14 — verbatim (Source A lines 172–182)

#### L14 — Independent Audit · *Auditor · model: Opus or Gemini (MUST ≠ Builder family, A-08)*
- **Purpose:** a different agent (different model family) hunts faults: AI slop, hidden mocks, fake implementations, dead code, architecture violations, security flaws, regressions.
- **Entry:** L13 passed.
- **Required artifacts:** audit report.
- **Exit:** audit clean, or findings routed back to L12.
- **Approval:** **audit is a gate** — no promotion without surviving independent audit (global rule).
- **Failure:** slop/mock/violation found → back to L12 with findings.
- **Evidence produced:** independent audit report (decorrelated verification, I3/A-08).

### Phase V — Integration

### L15 — verbatim (Source A lines 183–191)

#### L15 — Documentation & Ledger · *Runtime + Builder · model: Sonnet*
- **Purpose:** synchronize institutional knowledge.
- **Entry:** L14 clean.
- **Required artifacts:** updated Inventory Atlas, roadmaps, architecture diagrams, knowledge graph, decision logs.
- **Exit:** all institutional records reflect the change; traceability to origin intact (global rule).
- **Approval:** none.
- **Failure:** stale/missing ledger update → incident (undocumented change).
- **Evidence produced:** ledger deltas; updated traceability links.

### L16 — verbatim (Source A lines 192–202)

#### L16 — Promotion Decision · *Integrator + Founder (Audit verb) · model: Opus*
- **Purpose:** decide the artifact's fate: Merge / Seal / Reject / Research-Only / Dormant.
- **Entry:** L15 complete; artifact `verified`.
- **Required artifacts:** final disposition.
- **Exit:** merged to trunk **single-threaded** (I9/K8), or the alternate disposition recorded.
- **Approval:** founder Audit (optional walk of integrated deltas); Seal/Reject of founder work → founder.
- **Failure:** merge conflict / coherence break → incident.
- **Evidence produced:** merge commit + aggregation roll-up, or disposition record.

### Phase VI — Learning

### L17 — verbatim (Source A lines 203–211)

#### L17 — Retrospective + Constitutional Review · *Auditor + Runtime · model: Opus*
- **Purpose:** improve engineering itself, and **improve PAEOS itself** — what slowed us, what failed, what repeated, which prompts improved, what should become policy.
- **Entry:** L16 complete (or a failure at any state).
- **Required artifacts:** lessons learned; workflow amendments; and the **mandatory Constitutional Review** (CER-4 / `operations/IMPLEMENTATION_REVIEW_PROTOCOL.md`) evaluating the 10-point checklist: (a) what architectural weaknesses were discovered? (b) what assumptions were invalidated? (c) which parts of PAEOS became stronger? (d) which Improvement Proposals were created (proposals/, CER-2)? (e) which Architectural Debt items were recorded (ledger/debt/, CER-3)? (f) should future implementation strategy change? Output saved to `reviews/tasks/<task_id>_review.md`.
- **Exit:** the Constitutional Review is written (`reviews/tasks/<task_id>_review.md`); every lesson is either discarded-with-reason or converted to an L18/L19 input, a Proposal, or a Debt entry. A task without a Constitutional Review is **incomplete** (CER-4).
- **Approval:** none (Steward-owned, continuous, with teeth). The review **recommends**; it never legislates (CER-5).
- **Failure:** a repeated mistake with no lesson → the meta-failure (Ω-11); a completed task with no Constitutional Review → the task is not done.
- **Evidence produced:** lessons-learned record; the Constitutional Review (`reviews/tasks/<task_id>_review.md`); links to any Proposals/Debt created.

### L18 — verbatim (Source A lines 212–222)

#### L18 — Knowledge Extraction · *Auditor (Steward) · model: Opus*
- **Purpose:** generalize reusable knowledge.
- **Entry:** L17 lessons exist.
- **Required artifacts:** new design pattern / protocol / skill / template / invariant / amendment / heuristic — as warranted.
- **Exit:** reusable knowledge is captured as a **versioned artifact** (skill/template/protocol), scarred and falsifiable (K6).
- **Approval:** new kernel-scope policy → Court + founder (§14.5).
- **Failure:** repeated mistake not converted to Skill/Template/Amendment (global rule violated).
- **Evidence produced:** institutional-knowledge artifacts (with scars + falsifiers).

### Phase VII — Evolution

### L19 — verbatim (Source A lines 223–317)

#### L19 — Constitutional Evolution · *Court + Founder · model: Opus (+ decorrelated Adversary)*
- **Purpose:** update PAEOS itself — did implementation reveal hidden assumptions? should policy/schema/lifecycle/routing change?
- **Entry:** an incident, an L18 amendment candidate, or a kernel-surface finding.
- **Required artifacts:** Incident; Amendment (`policy_delta` + motivation-scars + `falsifier_watch` + own evidence spec); policy evolution; kernel proposal (if warranted).
- **Exit:** amendment reaches `provisional` (delta applied, falsifier armed) → `verified | reverted` (A-06); kernel-surface changes pass §14.5 ceremony + founder Decision.
- **Approval:** **founder** for any kernel-surface change (self-application is Trace-B).
- **Failure:** falsifier fires → mechanical revert (A-06); a defect that produces no incident → unlearned (Ω-11).
- **Evidence produced:** Incident + Amendment ledger entries; recompiled policy affecting every future context (K5/I6).

---

## Constitutional Execution Rules (Engineering Lifecycle v1.2 — Founder-Ratified 2026-07-27)

> These six rules **govern every state** without adding any state or changing any ordering.
> They are the canonical definition; all other implementation documents reference them, they
> are not restated. Constitutional grounding: this is PAEOS-0 falsificationism (challenge
> every assumption; no rule without a scar) applied continuously to PAEOS itself, and the
> PAEOS-3.5 adversarial-court method run on every cycle rather than once. **PAEOS exists to
> discover the best architecture, not to implement the first that works. The runtime MUST
> assume the current architecture is incomplete until evidence suggests otherwise, and a
> builder MUST NOT be attached to the constitution merely because it exists.**

- **CER-1 — Mandatory Critical Thinking.** Every implementation task MUST actively attempt to
  *falsify* the current architecture — searching for architectural weaknesses, unnecessary
  complexity, hidden assumptions, better abstractions, simpler designs, missing constitutional
  rules, and opportunities to reduce the trusted computing base or improve verification,
  determinism, or portability. **Acceptance is never sufficient.** This is a stance every
  agent carries in every state (sharpest at L03, L09, L10, L13, L14, L17), enforced by the
  Universal Preamble of `operations/PROMPT_TEMPLATES.md`. It adds no state; it is a lens.

- **CER-2 — Improvement Proposals.** No implementation may silently improve the constitution.
  Every discovered improvement MUST generate a formal document `proposals/PAEOS-IP-NNNN.md`
  (fields: observation · current behaviour · proposed improvement · justification · risks ·
  backwards compatibility · constitutional impact · recommendation). Implementation MAY
  continue regardless of a proposal's acceptance. A proposal is, in kernel terms, a **draft
  amendment-goal awaiting founder ratification** (K7/§14.5) — it recommends, it does not change
  anything. See `proposals/README.md`.

- **CER-3 — Architectural Debt Ledger.** Whenever an implementation deliberately chooses a
  non-ideal solution, it MUST record `ledger/debt/DEBT-NNNN.md` (fields: compromise · reason ·
  ideal solution · repayment conditions · priority · estimated impact). **Architectural debt
  MUST NOT exist only inside conversation history** (PAEOS-0 A2: artifacts durable, context
  ephemeral; the Sentium buried-decisions scar). In kernel terms a debt entry is a recorded
  compromise / open incident (K7). See `ledger/debt/README.md`.

- **CER-4 — End-of-Task Constitutional Review.** Every completed task MUST finish with the
  Constitutional Review defined in **L17** above and governed by `operations/IMPLEMENTATION_REVIEW_PROTOCOL.md`.
  It is mandatory; a task without it is not done.

- **CER-5 — Separation of Powers.** Improvement Proposals NEVER automatically modify PAEOS.
  Only a **founder-ratified constitutional amendment** may change the kernel, lifecycle,
  authority, invariants, or constitutional law (§14.5, K7, D2). **The runtime MAY recommend;
  it MUST NEVER legislate.** This rule is what makes CER-1..CER-4 safe: unlimited critical
  thinking and proposal generation, zero unauthorized change. It reinforces the existing
  Founder-only authority boundary; it grants no new power to any agent.

- **CER-6 — Constitutional Derivation.** Before introducing any new architectural concept,
  interface, abstraction, module, namespace, service, or kernel responsibility, the Builder
  MUST demonstrate its explicit derivation from existing constitutional artifacts (`Z0`, `spec/`,
  `derivation/`). If no derivation exists, implementation MUST halt and produce an Improvement
  Proposal (`proposals/PAEOS-IP-NNNN.md`) rather than invent architecture. Implementation MAY
  refine constitutional intent; implementation MAY NOT create constitutional intent.

## Global Constitutional Rules (apply across every state)

1. No direct transition from Intake to Implementation.
2. Every transition requires evidence (K1).
3. Implementation never creates architecture (L12 is bound to the L11 contract and CER-6 derivation).
4. Architecture never creates policy (L08 → policy only via L19).
5. Policy changes require constitutional review (L10/L19, §14.5).
6. Every implementation must survive an independent audit (L14, decorrelated model, A-08).
7. Every completed task must improve institutional knowledge (L15/L18).
8. Every discovered defect becomes an Incident (L19).
9. Every ambiguity becomes an Incident (the HALT rule — SC register).
10. Every repeated mistake becomes a Skill, Template, or Amendment (L18).
11. Every engineering artifact must be traceable to its origin (serving-clause chain).
12. The workflow itself is versioned and amendable under the same constitutional process (L19 applies to this document).
13. Every task MUST attempt to falsify the current architecture; acceptance is never sufficient (CER-1).
14. Every discovered improvement MUST become a formal Proposal, never a silent change (CER-2).
15. Every deliberate non-ideal choice MUST be recorded as Architectural Debt (CER-3).
16. Every completed task MUST end with a Constitutional Review (CER-4 / `IMPLEMENTATION_REVIEW_PROTOCOL.md`).
17. Only the founder may ratify changes to kernel/lifecycle/authority/invariants; the runtime recommends, never legislates (CER-5).
18. Implementation MUST NOT invent architecture; un-derived concepts trigger an immediate HALT and Improvement Proposal (CER-6).
19. Every workload, system, or product built by PAEOS MUST maintain a living `Implementation Atlas` (`docs/IMPLEMENTATION_ATLAS.md`) tracking all components, trust zones, constitutional origins, statuses, and evidence anchors (L15).

## Versioning

This is **v1.3** (Universal Implementation Atlas amendment, founder-ratified 2026-07-27;
adds Global Rule 19, mandates `docs/IMPLEMENTATION_ATLAS.md` across all PAEOS-governed workloads;
adds no state, changes no ordering, modifies no kernel invariant). Amendments to the lifecycle are
L19 events on this document — scarred, falsifiable, founder-ratified. The machine-executable form is
`operations/WORKFLOW_STATE_MACHINE.yaml`; roles are in `operations/ROLE_RESPONSIBILITIES.md`;
per-state prompts are in `operations/PROMPT_TEMPLATES.md`.

## 3. Verbatim execution rules and state machine (Source B: WORKFLOW_STATE_MACHINE.yaml)

### `version:` (verbatim)

```yaml
version: "1.1"    # v1.1 Constitutional Execution Rules amendment, founder-ratified 2026-07-21
```

### `frozen:` (verbatim)

```yaml
frozen: true
```

### `governs:` (verbatim)

```yaml
governs: [paeos-runtime, sentium, orca-strator, inspiration-engine, library-of-fire, sakg, "*future"]
```

### `constitutional_rule:` (verbatim)

```yaml
constitutional_rule: >
  No engineering artifact may transition directly to Implementation. Every artifact
  progresses through the lifecycle unless explicitly rejected. Each state produces
  artifacts that become evidence for the next. A transition without evidence is invalid.

# ---- Constitutional Execution Rules (v1.1) — govern EVERY state; add no state ----
# Canonical definition: operations/ENGINEERING_LIFECYCLE.md §Constitutional Execution Rules.
# PAEOS exists to discover the best architecture, not implement the first that works.
```

### `constitutional_execution_rules:` (verbatim)

```yaml
constitutional_execution_rules:
  CER-1_mandatory_critical_thinking: >
    Every task MUST actively attempt to FALSIFY the current architecture (weaknesses,
    complexity, hidden assumptions, better abstractions, simpler designs, missing rules,
    smaller TCB, better verification/determinism/portability). Acceptance is never
    sufficient. A stance carried in every state; enforced by the prompt Universal Preamble.
  CER-2_improvement_proposals:
    rule: >
      No silent constitutional improvement. Every discovered improvement MUST emit
      proposals/PAEOS-IP-NNNN.md. Implementation MAY continue regardless of acceptance.
    fields: [observation, current_behaviour, proposed_improvement, justification, risks,
             backwards_compatibility, constitutional_impact, recommendation]
    kernel_mapping: draft amendment-goal awaiting founder ratification (K7 / §14.5)
  CER-3_architectural_debt_ledger:
    rule: >
      Every deliberate non-ideal choice MUST be recorded at ledger/debt/DEBT-NNNN.md.
      Debt MUST NOT live only in conversation (A2; Sentium buried-decisions scar).
    fields: [compromise, reason, ideal_solution, repayment_conditions, priority, estimated_impact]
    kernel_mapping: recorded compromise / open incident (K7)
  CER-4_end_of_task_constitutional_review:
    rule: "Every completed task MUST end with a Constitutional Review (produced at L17; operations/IMPLEMENTATION_REVIEW_PROTOCOL.md)."
    questions: [weaknesses_discovered, assumptions_invalidated, parts_of_paeos_strengthened,
                proposals_created, debt_recorded, should_strategy_change]
  CER-5_separation_of_powers: >
    Proposals NEVER auto-modify PAEOS. Only a founder-ratified amendment may change
    kernel/lifecycle/authority/invariants/law (§14.5, K7, D2). The runtime MAY recommend;
    it MUST NEVER legislate. This makes CER-1..CER-4 safe.
  CER-6_constitutional_derivation: >
    Before introducing any new architectural concept, interface, abstraction, module,
    namespace, service, or kernel responsibility, the Builder MUST demonstrate its explicit
    derivation from existing constitutional artifacts (Z0, spec/, derivation/). If no derivation
    exists, implementation MUST halt and emit an Improvement Proposal rather than invent architecture.
```

### `ceremony_depth:` (verbatim)

```yaml
ceremony_depth:
  assigned_at: L02
  basis: [verifiability, reversibility]   # kernel router (v x r)
  levels:
    trace_a:            # reversible AND cheaply verified
      description: routine work; Runtime auto-discharges the Trace-B front-end
      auto_discharge: [L03, L04, L05, L06, L07, L08, L09, L10, L11, L17, L18]
      execute_full:   [L01, L02, L12, L13, L14, L15, L16]
      evolution:      L19_on_trigger
      human: none
    trace_b:            # irreversible OR expensive to verify
      description: full ceremony; founder Decisions at gates
      execute_full: [L01..L19]
      human: founder_decisions_at_gates
  rule: >
    auto_discharge != skip. Each auto-discharged state MUST still emit an evidence stub
    {result: auto_pass, reason: trace_a, by: runtime} so every transition remains valid.

# ---- Model orchestration (Runtime assigns; decorrelation is mandatory) ----
```

### `model_policy:` (verbatim)

```yaml
model_policy:
  classes:
    opus:   {use: [deep-reasoning, planning, adversarial, court, audit], }
    sonnet: {use: [fast-generation, construction, docs], }
    gemini: {use: [frontier-research, decorrelated-critique], }
    local:  {use: [mechanical-checks, lint, compile], }
  decorrelation:            # kernel A-08 / I3
    rule: >
      The model family verifying or auditing work (L10, L13-adversarial, L14) MUST differ
      from the family that built it (L12). Same-family verification is theater.
    enforced_at: [L10, L14]
  runtime_selects: true     # per-state recommended_model is advisory; Runtime binds actual model

# ---- Roles (full defs: operations/ROLE_RESPONSIBILITIES.md) ----
```

### `gates:` (verbatim)

```yaml
gates:
  triage_reject:   {at: L02, approver: founder, when: "reject/dormant on founder-authored intent"}
  court_verdict:   {at: L10, approver: court,   blocks_on: [REJECT, unresolved_amendments]}
  plan_freeze:     {at: L11, approver: [planner, court], founder_if: irreversible_scope}
  audit_gate:      {at: L14, approver: auditor, blocks_on: [slop, mock, violation, regression]}
  promotion:       {at: L16, approver: integrator, founder_if: "seal/reject of founder work"}
  kernel_change:   {at: L19, approver: founder, ceremony: "§14.5 self-application (Trace-B)"}

# ---- States ----
# Each: phase, purpose, role, recommended_model, entry, required_artifacts,
# produced_evidence, exit, transitions (target: condition), failure.
```

### `global_rules:` (verbatim)

```yaml
global_rules:
  - no_direct_intake_to_implementation
  - every_transition_requires_evidence            # K1
  - implementation_never_creates_architecture     # L12 bound to L11
  - architecture_never_creates_policy             # L08 -> policy only via L19
  - policy_changes_require_constitutional_review  # §14.5
  - every_implementation_survives_independent_audit  # L14, A-08
  - every_task_improves_institutional_knowledge   # L15/L18
  - every_defect_becomes_incident
  - every_ambiguity_becomes_incident              # HALT rule
  - every_repeated_mistake_becomes_skill_template_or_amendment
  - every_artifact_traceable_to_origin            # serving-clause chain
  - workflow_is_versioned_and_amendable           # this file evolves via L19
  - every_task_attempts_to_falsify_architecture   # CER-1
  - every_improvement_becomes_a_proposal_not_a_silent_change  # CER-2
  - every_deliberate_nonideal_choice_becomes_debt # CER-3
  - every_task_ends_with_constitutional_review    # CER-4
  - only_founder_ratifies_kernel_lifecycle_authority_invariants  # CER-5 (runtime recommends, never legislates)
```

### `terminal_states:` (verbatim)

```yaml
terminal_states: [DONE]
```

### `initial_state:` (verbatim)

```yaml
initial_state: L01
```

### States L01–L19 (verbatim)

#### State `L01` (Source B lines 105–117, verbatim)

```yaml
  L01:
    name: Intake
    phase: I-Discovery
    role: runtime
    recommended_model: n/a
    entry: "a source has something worth recording"
    required_artifacts: [description, source, motivation, expected_value, initial_classification]
    produced_evidence: [declared_artifact]
    exit: "artifact exists as Goal(declared)"
    transitions:
      L02: "artifact declared"
    failure: "malformed intent -> not admitted"
```

#### State `L02` (Source B lines 118–133, verbatim)

```yaml
  L02:
    name: Triage
    phase: I-Discovery
    role: planner
    recommended_model: [opus, sonnet]
    entry: "declared artifact from L01"
    required_artifacts: [disposition, priority, scope, duplicate_analysis, forbidden_zone_analysis, classification_v_r, dispatch_record]
    produced_evidence: [disposition_record, classification_evidence, dispatch_record]
    exit: "exactly one disposition + classification Evidence (bound, expiring: A-14)"
    transitions:
      L03:  "disposition in [keep, immediate] AND ceremony=trace_b"
      L12:  "disposition in [keep, immediate] AND ceremony=trace_a"   # auto-discharge L03..L11
      L05:  "disposition = research"
      DONE: "disposition in [reject, merge, dormant]"
    failure: "unclassifiable -> L05 or escalate Decision"
```

#### State `L03` (Source B lines 134–145, verbatim)

```yaml
  L03:
    name: First-Principles Re-Derivation
    phase: II-Understanding
    role: [planner, researcher]
    recommended_model: opus
    entry: "L02 keep/research/immediate AND trace_b"
    required_artifacts: [first_principles_model, constraints, fundamental_laws]
    produced_evidence: [derivation_artifact]
    exit: "problem independently derived, not inherited"
    transitions: {L04: "derivation complete", L05: "blocked on external knowledge"}
    failure: "cannot derive -> spawn L05"
```

#### State `L04` (Source B lines 146–157, verbatim)

```yaml
  L04:
    name: Ambitious Ideation
    phase: II-Understanding
    role: [planner, builder]
    recommended_model: [opus, gemini]
    entry: "L03 complete"
    required_artifacts: [alternative_architectures, idealized_solution, failure_modes]
    produced_evidence: [candidate_set]
    exit: "candidate space genuinely wide (decorrelated options)"
    transitions: {L05: "needs prior art", L06: "candidates exist"}
    failure: "degenerate space -> collapse to single approach (noted)"
```

#### State `L05` (Source B lines 158–170, verbatim)

```yaml
  L05:
    name: Frontier Research
    phase: II-Understanding
    role: researcher
    recommended_model: [gemini, opus]
    entry: "a blocked understanding needs external knowledge (pull-driven)"
    required_artifacts: [research_dossier, novelty_assessment, prior_art]
    produced_evidence: [research_dossier]   # bound, expiring (K2)
    exit: "named blocker resolves"
    approval: {founder_inject: "market/user/money ground truth"}
    transitions: {L03: "reframes problem", L04: "informs ideation", L06: "informs tradeoffs", L08: "informs design"}
    failure: "consumer-less research -> scope-creep incident"
```

#### State `L06` (Source B lines 171–182, verbatim)

```yaml
  L06:
    name: Trade-off Analysis
    phase: II-Understanding
    role: [planner, reviewer]
    recommended_model: opus
    entry: ">=1 viable approach from L04"
    required_artifacts: [tradeoff_matrix]
    produced_evidence: [tradeoff_matrix]
    exit: "decision axes explicit and comparable"
    transitions: {L07: "matrix has material risks", L08: "no material risk"}
    failure: "omitted axis surfaced later -> incident"
```

#### State `L07` (Source B lines 183–195, verbatim)

```yaml
  L07:
    name: Trade-off Mitigation
    phase: II-Understanding
    role: [planner, adversary]
    recommended_model: opus
    entry: "L06 matrix with material risks"
    required_artifacts: [mitigation_catalogue, kill_switches, fallback_behaviour, shadow_mode, safety_constraints]
    produced_evidence: [mitigation_catalogue]
    exit: "every high-severity tradeoff mitigated or accepted-risk recorded"
    approval: {founder_decision: "irreversible accepted-risks"}
    transitions: {L08: "mitigations designed"}
    failure: "unmitigated high-severity risk, no accepted-risk record -> blocks L08"
```

#### State `L08` (Source B lines 196–207, verbatim)

```yaml
  L08:
    name: System Design
    phase: II-Understanding
    role: planner
    recommended_model: opus
    entry: "selected approach + mitigations"
    required_artifacts: [component_graph, interfaces, data_flow, state_machines, schemas, storage, apis, dependencies]
    produced_evidence: [architecture_artifacts, conservation_audit, spec_sufficiency_audit]
    exit: "intent-conservation passes; seams are good product boundaries (Ω-24); constraints tightened only (D2)"
    transitions: {L09: "architecture produced"}
    failure: "orphan/gap/loosened-constraint -> redesign or escalate"
```

#### State `L09` (Source B lines 208–220, verbatim)

```yaml
  L09:
    name: Multi-Perspective Critique
    phase: III-Constitutional-Review
    role: reviewer
    recommended_model: [gemini, opus]
    perspectives: [builder, architect, risk_officer, performance, security, replay, maintainer]
    entry: "architecture from L08"
    required_artifacts: [finding_register, required_changes]
    produced_evidence: [finding_register]
    exit: "every perspective reported"
    transitions: {L10: "critique complete"}
    failure: "a perspective skipped -> incomplete, cannot advance"
```

#### State `L10` (Source B lines 221–235, verbatim)

```yaml
  L10:
    name: Adversarial Review
    phase: III-Constitutional-Review
    role: [court, adversary]
    recommended_model: [opus, gemini]   # MUST differ from builder family
    entry: "L08 design + L09 findings"
    required_artifacts: [adversarial_report, blocking_amendments]
    produced_evidence: [adversarial_report, verdict]
    exit: "verdict in [RATIFY, RATIFY_WITH_AMENDMENTS(resolved)]"
    gate: court_verdict
    transitions:
      L11:  "verdict = RATIFY or amendments resolved"
      L08:  "verdict = REJECT or blocking finding"
    failure: "proven contradiction -> back to L08"
```

#### State `L11` (Source B lines 236–248, verbatim)

```yaml
  L11:
    name: Formal Planning
    phase: III-Constitutional-Review
    role: planner
    recommended_model: opus
    entry: "L10 ratified"
    required_artifacts: [affected_files, forbidden_files, rollback_plan, acceptance_criteria, test_strategy, dependencies, derivation_refs] # CER-6
    produced_evidence: [implementation_contract]
    exit: "implementation contract approved"
    gate: plan_freeze
    transitions: {L12: "contract approved"}
    failure: "ambiguous contract OR un-derived architecture -> incident (ambiguity = incident / CER-6 halt)"
```

#### State `L12` (Source B lines 249–260, verbatim)

```yaml
  L12:
    name: Branch Implementation
    phase: IV-Engineering
    role: builder
    recommended_model: sonnet
    entry: "approved contract on isolated branch/worktree (A-16)"
    required_artifacts: [implementation, commits_referencing_contract]
    produced_evidence: [branch_commits]
    exit: "runnable code matches contract"
    transitions: {L13: "implementation complete"}
    failure: "cannot satisfy contract without un-derived architecture -> HALT (CER-6), emit proposal"
```

#### State `L13` (Source B lines 261–272, verbatim)

```yaml
  L13:
    name: Verification
    phase: IV-Engineering
    role: builder
    recommended_model: sonnet
    entry: "L12 complete"
    required_artifacts: [executable_test_results, signed_exec_evidence] # A-09
    produced_evidence: [exec_evidence_object]
    exit: "all evidence specs satisfied + signed"
    transitions: {L14: "evidence signed"}
    failure: "failing tests -> iterate in L12; forged evidence -> immediate halt"
```

#### State `L14` (Source B lines 273–287, verbatim)

```yaml
  L14:
    name: Independent Audit
    phase: IV-Engineering
    role: auditor
    recommended_model: gemini    # MUST differ from builder family (A-08)
    entry: "L13 signed evidence"
    required_artifacts: [independent_audit_report, static_analysis, type_check_report]
    produced_evidence: [audit_verdict]
    exit: "audit verdict = PASS"
    gate: audit_gate
    transitions:
      L15:  "audit verdict = PASS"
      L12:  "audit verdict = FAIL (findings returned to builder)"
    failure: "unresolved audit findings -> back to L12"
```

#### State `L15` (Source B lines 288–300, verbatim)

```yaml
  L15:
    name: Documentation & Ledger
    phase: V-Integration
    role: builder
    recommended_model: sonnet
    entry: "L14 passed"
    required_artifacts: [doc_updates, ledger_entry, changelog_entry, implementation_atlas] # docs/IMPLEMENTATION_ATLAS.md
    produced_evidence: [documentation_commit, updated_atlas_row]
    exit: "docs + atlas + ledger current"
    transitions: {L16: "docs complete"}
    failure: "missing docs / stale atlas -> back to L15"
```

#### State `L16` (Source B lines 301–313, verbatim)

```yaml
  L16:
    name: Promotion Decision
    phase: V-Integration
    role: integrators   # single-threaded integration (I9/K8)
    recommended_model: opus
    entry: "L15 complete; artifact verified"
    required_artifacts: [final_disposition]  # merge | seal | reject | research_only | dormant
    produced_evidence: [merge_commit, aggregation_rollup]
    exit: "merged single-threaded (I9/K8) or alternate disposition recorded"
    gate: promotion
    transitions: {L17: "merged or dispositioned"}
    failure: "merge conflict / coherence break -> incident"
```

#### State `L17` (Source B lines 314–328, verbatim)

```yaml
  L17:
    name: Retrospective + Constitutional Review
    phase: VI-Learning
    role: [auditor, runtime]
    recommended_model: opus
    entry: "L16 complete OR any failure"
    required_artifacts: [lessons_learned, workflow_amendments, constitutional_review]  # CER-4 / operations/IMPLEMENTATION_REVIEW_PROTOCOL.md
    constitutional_review_questions: [weaknesses_discovered, assumptions_invalidated,
                                       parts_of_paeos_strengthened, proposals_created,
                                       debt_recorded, should_strategy_change]
    produced_evidence: [lessons_record, constitutional_review_artifact, proposal_links, debt_links] # reviews/tasks/<task_id>_review.md
    exit: "Constitutional Review written to reviews/tasks/<task_id>_review.md (CER-4); every lesson discarded-with-reason or converted to L18/L19/Proposal/Debt"
    transitions: {L18: "lessons exist", L19: "workflow/policy change implied"}
    failure: "repeated mistake, no lesson -> meta-failure (Ω-11); no Constitutional Review -> task not done (CER-4)"
```

#### State `L18` (Source B lines 329–340, verbatim)

```yaml
  L18:
    name: Knowledge Extraction
    phase: VI-Learning
    role: auditor    # Steward stance
    recommended_model: opus
    entry: "L17 lessons exist"
    required_artifacts: [new_pattern_or_protocol_or_skill_or_template_or_invariant_or_amendment_or_heuristic]
    produced_evidence: [institutional_knowledge_artifact]   # versioned, scarred, falsifiable (K6)
    exit: "reusable knowledge captured as versioned artifact"
    transitions: {L19: "kernel-scope change implied", DONE: "workload-scope knowledge captured"}
    failure: "repeated mistake not converted to skill/template/amendment (global rule 10)"
```

#### State `L19` (Source B lines 341–375, verbatim)

```yaml
  L19:
    name: Constitutional Evolution
    phase: VII-Evolution
    role: [court, founder]
    recommended_model: opus
    entry: "incident OR L18 amendment candidate OR kernel-surface finding"
    required_artifacts: [incident, amendment, policy_evolution, kernel_proposal_if_warranted]
    produced_evidence: [incident_record, amendment_ledger_entry, recompiled_policy]
    exit: "amendment provisional -> verified|reverted (A-06); kernel change passes §14.5 + founder"
    gate: kernel_change
    transitions: {DONE: "amendment integrated or reverted"}
    failure: "falsifier fires -> mechanical revert; defect with no incident -> unlearned (Ω-11)"

# ---- Global invariants (checked on every transition) ----
global_rules:
  - no_direct_intake_to_implementation
  - every_transition_requires_evidence            # K1
  - implementation_never_creates_architecture     # L12 bound to L11
  - architecture_never_creates_policy             # L08 -> policy only via L19
  - policy_changes_require_constitutional_review  # §14.5
  - every_implementation_survives_independent_audit  # L14, A-08
  - every_task_improves_institutional_knowledge   # L15/L18
  - every_defect_becomes_incident
  - every_ambiguity_becomes_incident              # HALT rule
  - every_repeated_mistake_becomes_skill_template_or_amendment
  - every_artifact_traceable_to_origin            # serving-clause chain
  - workflow_is_versioned_and_amendable           # this file evolves via L19
  - every_task_attempts_to_falsify_architecture   # CER-1
  - every_improvement_becomes_a_proposal_not_a_silent_change  # CER-2
  - every_deliberate_nonideal_choice_becomes_debt # CER-3
  - every_task_ends_with_constitutional_review    # CER-4
  - only_founder_ratifies_kernel_lifecycle_authority_invariants  # CER-5 (runtime recommends, never legislates)

terminal_states: [DONE]
initial_state: L01
```

## 4. Canonical conflicts — RECORDED, NOT RESOLVED

- **CONFLICT-1 (numbering authority):** `backlog/research/PAEOS_CANONICAL_LIFECYCLE.md` — an AI
  reconstruction (contains inline uncertainty, e.g. "actually wait…" at L14) — assigns different
  layer orderings than Sources A/B. Authority tier: research backlog (lowest). Requires founder
  resolution if it is to carry any weight; by default it is superseded by this Freeze.
- **CONFLICT-2 (historical IP stage labels):** an earlier constitutional IP describes VERIFY as
  "stage 11", adversarial review as "stage 12", seal ≈ "stage 14", Evolution across 15–19 —
  inconsistent with Sources A/B (VERIFY=L13, design-adversary=L10, post-build audit=L14).
  Sources A/B are frozen and ratified later; the IP predates the freeze. Requires founder
  resolution.
- **CONFLICT-3 (implementer model names):** Source A names model families (Opus/Sonnet/Gemini)
  per layer; the implemented runtime uses codex/gpt-5.6-sol and cline-pass/glm-5.3. Source B
  `model_policy` is the machine-executable rule; whether the substitution satisfies it is a
  **conformance question (Step 2), not a canonical question.**

## 5. Non-interpretation statement

This Freeze adds no states, renumbers nothing, reconciles nothing, and proposes no amendments.
Per the Source B constitutional rule, the CER "governs every state; add no state." Any change to
the canonical map must proceed through the amendment loop (L19) with founder ratification.
