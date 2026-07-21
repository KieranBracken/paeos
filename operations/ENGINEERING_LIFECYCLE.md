# PAEOS Engineering Lifecycle v1.0 — Operational Doctrine

> Status: **FROZEN v1.0**, 2026-07-20. Operational doctrine for all PAEOS-based
> engineering: PAEOS Runtime, Sentium, Orca-Strator, Inspiration Engine, Library of Fire,
> SAKG, and every future project. **Not part of the kernel spec** — this is the workflow
> the PAEOS Runtime will eventually execute automatically. It is implementation-
> independent, multi-model, and versioned/amendable under the same constitutional process
> it governs. Constitutional resolution + crosswalk:
> `methodology/PAEOS-CONSTITUTIONAL-ENGINEERING-LIFECYCLE.md` (§6a).

## Constitutional Rule (the spine)

> **No engineering artifact may transition directly to Implementation.** Every artifact
> SHALL progress through the lifecycle below unless explicitly rejected. Each state
> produces artifacts which become **evidence** for the next state. **A transition without
> evidence is constitutionally invalid** (kernel: K1 — no promotion without evidence).

## Router compatibility — ceremony depth (how this stays PAEOS-compatible)

The spine says *every* artifact is routed through the lifecycle; the router principle
(PAEOS-0/2) says most work is trivial. Both hold via **ceremony depth**, assigned at L02
from verifiability × reversibility:

- **Trace-A** (reversible, cheaply verified): the Runtime **auto-discharges** L03–L11 and
  L17–L18 in one pass (each records a machine "auto-pass, Trace-A" evidence stub), and
  executes L01–L02, L12–L16, L19-if-triggered in full. ~minutes, no human.
- **Trace-B** (irreversible / expensive to verify): **all 19 states execute in full**,
  with founder Decisions at the gates.
- Depth is a per-artifact property, not a per-project choice. "Auto-discharge" is not
  "skip" — it emits the evidence stub that keeps every transition valid.

## Roles (full definitions: `operations/ROLE_RESPONSIBILITIES.md`)

Founder · Planner · Researcher · Builder · Reviewer · Court · Adversary · Auditor ·
Runtime. The **Runtime** orchestrates: it assigns states to agents, compiles their
context, enforces gates, and selects the **model** per role (Opus/Sonnet/Gemini/local),
honoring decorrelation (an Auditor/Adversary MUST differ in model family from the Builder
it checks — kernel A-08).

---

## The 19 States

Each: **Purpose · Entry · Required artifacts · Exit · Approval · Failure · Evidence
produced.** Owning role and recommended model class in the header line.

### Phase I — Discovery

#### L01 — Intake · *Runtime + any source · model: n/a*
- **Purpose:** capture an idea, bug, research question, architectural concern, or improvement.
- **Entry:** a source (founder, agent, incident, external signal) has something worth recording.
- **Required artifacts:** initial description; source; motivation; expected value; initial classification.
- **Exit:** the artifact exists as a `Goal(kind=work|incident)` in `declared`.
- **Approval:** none (capture is unconditional).
- **Failure:** malformed/empty intent → not admitted.
- **Evidence produced:** the declared artifact itself (its existence is the evidence for L02).

#### L02 — Triage · *Planner (Router) · model: Opus/Sonnet*
- **Purpose:** decide whether this deserves engineering effort, and at what ceremony depth.
- **Entry:** a declared artifact from L01.
- **Required artifacts:** disposition (Keep / Merge / Reject / Dormant / Research / Immediate-Priority); priority; scope; duplicate analysis; **forbidden-zone analysis**; **classification (v × r) → ceremony depth**.
- **Exit:** exactly one disposition + a classification Evidence object (bound, expiring — A-14) + a DispatchRecord.
- **Approval:** Reject/Dormant on founder-authored intent → founder confirmation; else automatic.
- **Failure:** unclassifiable → route to L05 (Research) or escalate a Decision.
- **Evidence produced:** disposition record; classification Evidence; duplicate/forbidden-zone findings.

### Phase II — Understanding *(Trace-B in full; auto-discharged for Trace-A)*

#### L03 — First-Principles Re-Derivation · *Planner + Researcher · model: Opus*
- **Purpose:** derive the problem from first principles — no assumptions, no implementation. "What must be true?"
- **Entry:** L02 = Keep/Research/Immediate AND ceremony depth ≥ Trace-B (else auto-pass).
- **Required artifacts:** first-principles model; constraints; fundamental laws.
- **Exit:** the problem is independently derived, not inherited.
- **Approval:** none (internal understanding).
- **Failure:** cannot derive → spawn L05 Frontier Research for missing knowledge.
- **Evidence produced:** the derivation artifact (challenges/validates inherited framing).

#### L04 — Ambitious Ideation · *Planner + Builder · model: Opus/Gemini*
- **Purpose:** generate the strongest possible solution; ignore practicality; aim for the ideal.
- **Entry:** L03 complete.
- **Required artifacts:** alternative architectures; idealized solution; failure modes.
- **Exit:** the candidate space is genuinely wide (decorrelated options exist to select among).
- **Approval:** none.
- **Failure:** degenerate space (all candidates ≈ identical) → collapse to single approach, note it.
- **Evidence produced:** candidate architecture set (feeds L06/L08 tournament).

#### L05 — Frontier Research · *Researcher · model: Gemini (web/frontier) + Opus*
- **Purpose:** establish state of the art — literature, mathematics, production systems, open source.
- **Entry:** a blocked understanding (L03/L04/L06) needs external knowledge; **pull-driven, never a phase**.
- **Required artifacts:** research dossier; novelty assessment; prior art.
- **Exit:** the named blocker resolves; a consumer stage can proceed.
- **Approval:** founder Inject for market/user/money ground truth the system cannot generate.
- **Failure:** consumer-less/unbounded research → scope-creep incident (findings expire, K2).
- **Evidence produced:** research dossier (bound, expiring).

#### L06 — Trade-off Analysis · *Planner + Reviewer · model: Opus*
- **Purpose:** identify every important trade-off (latency, accuracy, memory, risk, maintainability, complexity, …).
- **Entry:** ≥1 viable approach from L04.
- **Required artifacts:** trade-off matrix (axes × approaches).
- **Exit:** the decision axes are explicit and comparable for a Judge.
- **Approval:** none.
- **Failure:** hidden/omitted axis surfaced later → incident against this matrix.
- **Evidence produced:** trade-off matrix (the Judge's selection basis).

#### L07 — Trade-off Mitigation · *Planner + Adversary · model: Opus*
- **Purpose:** design safeguards for every important compromise.
- **Entry:** L06 matrix exists with material risks.
- **Required artifacts:** mitigation catalogue; kill switches; fallback behaviour; shadow mode; safety constraints.
- **Exit:** every high-severity trade-off has a named safeguard or an accepted-risk record.
- **Approval:** irreversible accepted-risks → founder Decision.
- **Failure:** an unmitigated high-severity risk with no accepted-risk record → blocks L08.
- **Evidence produced:** mitigation catalogue.

#### L08 — System Design · *Planner (Decomposer) · model: Opus*
- **Purpose:** produce the architecture — no implementation.
- **Entry:** selected approach (L04/L06) + mitigations (L07).
- **Required artifacts:** component graph; interfaces; data flow; state machines; schemas; storage; APIs; dependencies. For decomposition: child goals + serving-clauses + aggregation contract.
- **Exit:** intent-conservation audit passes (no orphans/gaps); verification seams are also good product boundaries (Ω-24); constraints tightened only (D2).
- **Approval:** high-fanout irreversible nodes → Court (L09/L10) then possibly founder Decision.
- **Failure:** orphan/gap/loosened-constraint → redesign or escalate.
- **Evidence produced:** the architecture artifact set; conservation + spec-sufficiency audit records.

### Phase III — Constitutional Review

#### L09 — Multi-Perspective Critique · *Reviewer (7 perspectives) · model: Gemini/Opus (decorrelated)*
- **Purpose:** attack the design from every stance — Builder, Architect, Risk Officer, Performance, Security, Replay, Maintainer.
- **Entry:** an architecture artifact from L08.
- **Required artifacts:** finding register; required changes.
- **Exit:** every perspective has reported; required changes are logged.
- **Approval:** none (advisory to L10/L11).
- **Failure:** a perspective is skipped → the review is incomplete, cannot advance.
- **Evidence produced:** per-perspective finding register.

#### L10 — Adversarial Review · *Court + Adversary · model: Opus/Gemini (≠ Builder family)*
- **Purpose:** attempt to prove the design wrong — contradictions, hidden assumptions, circular reasoning, economic/security/scaling failures, emergent behaviour.
- **Entry:** L08 design + L09 findings.
- **Required artifacts:** adversarial report; blocking amendments.
- **Exit:** a verdict (RATIFY / RATIFY-WITH-AMENDMENTS / REJECT) with every finding carrying violated-principle · evidence · severity · smallest-amendment (the 3.5/5.5 court format).
- **Approval:** **Court verdict is a gate** — REJECT halts; amendments must be resolved.
- **Failure:** a proven contradiction/blocking finding → design returns to L08.
- **Evidence produced:** adversarial report; blocking-amendment ledger.

#### L11 — Formal Planning · *Planner · model: Opus*
- **Purpose:** freeze implementation scope — the implementation contract.
- **Entry:** L10 verdict = RATIFY(-WITH-AMENDMENTS, resolved).
- **Required artifacts:** affected files; **forbidden files**; rollback plan; acceptance criteria; test strategy; dependencies.
- **Exit:** implementation contract approved (this is the artifact L12 is bound to).
- **Approval:** founder Decision for irreversible scope; else Planner + Court sign-off.
- **Failure:** ambiguous/incomplete contract → incident (every ambiguity is an incident).
- **Evidence produced:** the frozen implementation contract.

### Phase IV — Engineering

#### L12 — Branch Implementation · *Builder · model: Sonnet (fast generation)*
- **Purpose:** implement **only** the approved scope.
- **Entry:** approved implementation contract (L11) on an isolated branch/worktree (A-16).
- **Required artifacts:** working implementation; commits each referencing the L11 contract.
- **Exit:** the scope is built and runs (`executed`); **no scope creep, no speculative improvements**.
- **Approval:** none (the Builder self-reports; it may NOT self-verify — X6).
- **Failure:** scope creep, or cannot build within budget → incident (cap-overrun, A-12).
- **Evidence produced:** implementation artifacts + builder execution self-report (not promoting evidence).

#### L13 — Verification · *Auditor/Runtime (mechanical) + Adversary · model: local+Sonnet, then Opus*
- **Purpose:** prove correctness. Order: Compile → Lint → Unit → Integration → Simulation → Replay → Performance.
- **Entry:** `executed` implementation from L12.
- **Required artifacts:** evidence records; test logs; coverage.
- **Exit:** the acceptance criteria (L11) are satisfied by **live, signed, independent** evidence (A-09), repeatability-aware (flaky ≠ refutation, Ω-01); no live refutation.
- **Approval:** none (mechanical evidence is self-approving via EXEC signature).
- **Failure:** any refutation → regress + incident (L19/Capture).
- **Evidence produced:** signed execution evidence, test logs, coverage, perf numbers.

#### L14 — Independent Audit · *Auditor · model: Opus or Gemini (MUST ≠ Builder family, A-08)*
- **Purpose:** a different agent (different model family) hunts faults: AI slop, hidden mocks, fake implementations, dead code, architecture violations, security flaws, regressions.
- **Entry:** L13 passed.
- **Required artifacts:** audit report.
- **Exit:** audit clean, or findings routed back to L12.
- **Approval:** **audit is a gate** — no promotion without surviving independent audit (global rule).
- **Failure:** slop/mock/violation found → back to L12 with findings.
- **Evidence produced:** independent audit report (decorrelated verification, I3/A-08).

### Phase V — Integration

#### L15 — Documentation & Ledger · *Runtime + Builder · model: Sonnet*
- **Purpose:** synchronize institutional knowledge.
- **Entry:** L14 clean.
- **Required artifacts:** updated Inventory Atlas, roadmaps, architecture diagrams, knowledge graph, decision logs.
- **Exit:** all institutional records reflect the change; traceability to origin intact (global rule).
- **Approval:** none.
- **Failure:** stale/missing ledger update → incident (undocumented change).
- **Evidence produced:** ledger deltas; updated traceability links.

#### L16 — Promotion Decision · *Integrator + Founder (Audit verb) · model: Opus*
- **Purpose:** decide the artifact's fate: Merge / Seal / Reject / Research-Only / Dormant.
- **Entry:** L15 complete; artifact `verified`.
- **Required artifacts:** final disposition.
- **Exit:** merged to trunk **single-threaded** (I9/K8), or the alternate disposition recorded.
- **Approval:** founder Audit (optional walk of integrated deltas); Seal/Reject of founder work → founder.
- **Failure:** merge conflict / coherence break → incident.
- **Evidence produced:** merge commit + aggregation roll-up, or disposition record.

### Phase VI — Learning

#### L17 — Retrospective + Constitutional Review · *Auditor + Runtime · model: Opus*
- **Purpose:** improve engineering itself, and **improve PAEOS itself** — what slowed us, what failed, what repeated, which prompts improved, what should become policy.
- **Entry:** L16 complete (or a failure at any state).
- **Required artifacts:** lessons learned; workflow amendments; and the **mandatory Constitutional Review** (CER-4) answering, in writing: (a) what architectural weaknesses were discovered? (b) what assumptions were invalidated? (c) which parts of PAEOS became stronger? (d) which Improvement Proposals were created (proposals/, CER-2)? (e) which Architectural Debt items were recorded (ledger/debt/, CER-3)? (f) should future implementation strategy change?
- **Exit:** the Constitutional Review is written; every lesson is either discarded-with-reason or converted to an L18/L19 input, a Proposal, or a Debt entry. A task without a Constitutional Review is **incomplete** (CER-4).
- **Approval:** none (Steward-owned, continuous, with teeth). The review **recommends**; it never legislates (CER-5).
- **Failure:** a repeated mistake with no lesson → the meta-failure (Ω-11); a completed task with no Constitutional Review → the task is not done.
- **Evidence produced:** lessons-learned record; the Constitutional Review; links to any Proposals/Debt created.

#### L18 — Knowledge Extraction · *Auditor (Steward) · model: Opus*
- **Purpose:** generalize reusable knowledge.
- **Entry:** L17 lessons exist.
- **Required artifacts:** new design pattern / protocol / skill / template / invariant / amendment / heuristic — as warranted.
- **Exit:** reusable knowledge is captured as a **versioned artifact** (skill/template/protocol), scarred and falsifiable (K6).
- **Approval:** new kernel-scope policy → Court + founder (§14.5).
- **Failure:** repeated mistake not converted to Skill/Template/Amendment (global rule violated).
- **Evidence produced:** institutional-knowledge artifacts (with scars + falsifiers).

### Phase VII — Evolution

#### L19 — Constitutional Evolution · *Court + Founder · model: Opus (+ decorrelated Adversary)*
- **Purpose:** update PAEOS itself — did implementation reveal hidden assumptions? should policy/schema/lifecycle/routing change?
- **Entry:** an incident, an L18 amendment candidate, or a kernel-surface finding.
- **Required artifacts:** Incident; Amendment (`policy_delta` + motivation-scars + `falsifier_watch` + own evidence spec); policy evolution; kernel proposal (if warranted).
- **Exit:** amendment reaches `provisional` (delta applied, falsifier armed) → `verified | reverted` (A-06); kernel-surface changes pass §14.5 ceremony + founder Decision.
- **Approval:** **founder** for any kernel-surface change (self-application is Trace-B).
- **Failure:** falsifier fires → mechanical revert (A-06); a defect that produces no incident → unlearned (Ω-11).
- **Evidence produced:** Incident + Amendment ledger entries; recompiled policy affecting every future context (K5/I6).

---

## Constitutional Execution Rules (Engineering Lifecycle v1.1 — Founder-Ratified 2026-07-21)

> These five rules **govern every state** without adding any state or changing any ordering.
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
  Constitutional Review defined in **L17** above. It is mandatory; a task without it is not
  done.

- **CER-5 — Separation of Powers.** Improvement Proposals NEVER automatically modify PAEOS.
  Only a **founder-ratified constitutional amendment** may change the kernel, lifecycle,
  authority, invariants, or constitutional law (§14.5, K7, D2). **The runtime MAY recommend;
  it MUST NEVER legislate.** This rule is what makes CER-1..CER-4 safe: unlimited critical
  thinking and proposal generation, zero unauthorized change. It reinforces the existing
  Founder-only authority boundary; it grants no new power to any agent.

## Global Constitutional Rules (apply across every state)

1. No direct transition from Intake to Implementation.
2. Every transition requires evidence (K1).
3. Implementation never creates architecture (L12 is bound to the L11 contract).
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
16. Every completed task MUST end with a Constitutional Review (CER-4).
17. Only the founder may ratify changes to kernel/lifecycle/authority/invariants; the runtime recommends, never legislates (CER-5).

## Versioning

This is **v1.1** (Constitutional Execution Rules amendment, founder-ratified 2026-07-21;
adds CER-1..CER-5 and enriches L17; adds no state, changes no ordering, modifies no kernel
invariant). Amendments to the lifecycle are L19 events on this document — scarred,
falsifiable, founder-ratified. The machine-executable form is
`operations/WORKFLOW_STATE_MACHINE.yaml`; roles are in `operations/ROLE_RESPONSIBILITIES.md`;
per-state prompts are in `operations/PROMPT_TEMPLATES.md`.
