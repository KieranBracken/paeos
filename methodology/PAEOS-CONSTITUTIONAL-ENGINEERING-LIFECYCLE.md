# PAEOS-X — The Constitutional Engineering Lifecycle

> Status: derived 2026-07-20 from the full corpus (PAEOS-0..6, 4/4.5 spec, 5.5 audit,
> Wave-0 packages, genesis scaffold, skills assessment) merged with the original
> 15-stage Anti-Gravity workflow. Governs every engineering task in PAEOS and every
> workload on it (Sentium, Orca-Strator, Inspiration Engine, Library of Fire, SAKG, …).
> **This is the master Protocol.** It is not above the kernel — it is the kernel's
> protocol layer made explicit, and at S3+ it graduates into PAEOS userland as
> `Policy(kind=protocol)` artifacts (the four genesis protocols are its Trace-A/B
> specializations). It obeys the kernel like anything else: scarred, falsifiable,
> amendable, prunable.

---

## 0. The central reconciliation (read this or misuse everything below)

The original Anti-Gravity workflow was a **pipeline**: 15 stages, every task marched
through all 15. PAEOS-0/1/2 demolished exactly that — work moves through **evidence
states**, not calendar stages, and the router **skips stations**. A lifecycle that fired
all its stages on every task would resurrect the pipeline the whole system exists to kill.

So the lifecycle is **not a sequence.** It is the **maximal ceremony envelope** — the
complete set of engineering obligations that *can* apply. For any given goal, the Router
(verifiability × reversibility) admits only the subset that goal's quadrant requires:

- **Trace-A** (reversible, cheaply verified — most work by count) instantiates **5 stages**:
  Frame → Route → Construct → Verify → Integrate. Fully autonomous, minutes, no founder.
- **Trace-B** (irreversible, expensive to verify — rare, expensive) instantiates **all 12**.
- The middle band (Decompose, Ground, Explore) is the **ceremony point-mass** — it exists
  only where the goal is non-leaf, blocked, or genuinely uncertain.

Stages are **partially ordered by evidence dependency, not time.** Multiple stages run in
parallel across a goal tree; a stage may re-fire when its evidence expires (K2). "Which
stages apply?" is answered per goal by S2, mechanically — never by the engineer's habit.

**How the count was derived (12, not 15/18/19):** each stage must produce a *distinct
evidence type* with a *distinct actor or founder-involvement*. Applying that test to every
obligation in the corpus and every activity in the Anti-Gravity list collapses them to 12.
The rejected inflation is instructive: "first-principles re-derivation," "ambitious
ideation," and "tradeoff analysis" are not separate stages — they are **disciplines and
modes inside one Exploration stage** (S5), fired only on Trace-B. Mistaking a discipline
for a stage is precisely how pipelines bloat, and the minimality budget (K10-spirit)
forbids it. "Prompt evolution" is not a stage at all — prompts are compiled, not written
(K5), so prompts evolve *only* by amending policy/skill artifacts, which is S10.

## 1. Map onto the kernel

```
WORK LOOP  (per goal; router-conditional; the lattice is the spine)
  ┌ declared ─────────────────────────────────────────────────────────┐
  S1 FRAME → S2 ROUTE →[S3 DECOMPOSE]→[S4 GROUND]→[S5 EXPLORE&SELECT]→   │
  → speculated → S6 CONSTRUCT → executed → S7 VERIFY → verified →        │
  → S8 INTEGRATE → integrated ────────────────────────────────────────┘
        │ (any failure / cap-overrun / escalation / expiry / direct-edit)
        ▼
EVOLUTION LOOP  (cross-goal; outcome-triggered; the constitution stays alive)
  S9 CAPTURE → S10 AMEND → S11 PRUNE&ROTATE → S12 SOUNDNESS-AUDIT
        └──────────── recompiles every future context (K5/I6) ──────────┘
```

`[bracketed]` = router-conditional. S9–S12 fire on outcomes, not per goal.

## 2. Cross-cutting invariants (hold *within every stage* — not stages themselves)

These are the laws every stage obeys; listing them once keeps the 12 stages clean.

| Law | Obligation on every stage | Clause |
|---|---|---|
| Evidence-gated | no state changes without live evidence; live refutation blocks (default-deny) | K1, A-10 |
| Read-set bound + expiry | every evidence declares its read-set; stale evidence regresses its stage | K2, A-07 |
| Independent verification | promoting evidence differs in stance (and model family where non-mechanical) from generation | I3, A-08 |
| Signed execution | execution-class evidence is EXEC-emitted and adapter-signed, never agent-authored | A-09 |
| Compiled context only | agents act on compiled contexts (constitution+role+skills+links+evidence), never hand-written prompts | K5/I6, A-05 |
| Append-only, crash-only | all state is store artifacts; any agent killable with zero loss | K4, D1 |
| Budget conservation | Σ child budgets ≤ parent; exhaustion → incident, never silent overrun | A-12 |
| Provenance stamped | actor/role/model stamped server-side, never accepted from proposer | 5.5 B-02 |
| **Falsify the constitution** | every cycle attempts to falsify the current architecture and improve PAEOS; improvements become Proposals, deliberate compromises become Debt, and only the founder ratifies constitutional change — the runtime recommends, never legislates | Lifecycle v1.1 CER-1..CER-5 (operations/) |

The last row is PAEOS-0's falsificationism turned on PAEOS itself: the same discipline that
forbids a rule without a scar forbids a *constitution* accepted merely because it exists.
Operationally it is the v1.1 Constitutional Execution Rules; it adds no stage and changes no
invariant — it makes continuous self-improvement mandatory and unauthorized self-modification
impossible.

## 3. The twelve stages

Each stage: **Objective · Inputs · Outputs · Entry · Exit · Evidence · Failure · Review ·
Routing · Founder · Automation**, then **Why / Prevents / Forced-by**.

---

### S1 — FRAME
- **Objective:** turn an intent into a well-formed, falsifiable Goal.
- **Inputs:** a raw intent (founder Author verb, or a parent's decomposition).
- **Outputs:** `Goal{ spec.delta, spec.evidence_spec (non-empty, falsifiable), constraints, capabilities?, serving_clause?, status=declared }`.
- **Entry:** an intent exists with no governing Goal.
- **Exit:** a schema-valid Goal whose evidence_spec could actually fail (a plan that can't fail is a vibe).
- **Evidence:** the Goal validates; for **root** goals, an A-15 adversarial interrogation record (the delta's clauses attacked for gaps).
- **Failure:** unfalsifiable/absent evidence_spec ⟹ kernel rejects (unreconcilable goal). Universal/safety intent ("never leak PII") is acknowledged as falsifiable-only — its evidence_spec must state the *bounded* proxy and name the residual intent–spec gap (Ω-25).
- **Review:** root goals get founder + adversarial interrogation; child goals get the S3 conservation audit.
- **Routing:** always. Root goals additionally pass A-15 ceremony.
- **Founder:** authors root goals (Author verb); none for child goals.
- **Automation:** child-goal framing fully automatable (Decomposer); root framing is the founder's irreplaceable intent act (A4).
- **Why / Prevents / Forced-by:** a goal without a falsifiable spec cannot be reconciled or ever declared done → prevents scope-vagueness and undetectable failure → **I1, PAEOS-4 §2.5, A-15, Ω-25.**

### S2 — ROUTE
- **Objective:** decide *which stages this goal needs* and under what budget.
- **Inputs:** the declared Goal; current check inventory; dependents set.
- **Outputs:** classification Evidence `(v ∈ {mechanical,adversarial,external}, r ∈ {reversible,guarded,irreversible})`; a `DispatchRecord{protocol, fanout, evidence_reqs, child_budget, escalate}`.
- **Entry:** Goal is `declared`.
- **Exit:** a DispatchRecord exists; budget is stamped (conserved against parent, A-12).
- **Evidence:** classification is itself Evidence, **bound and expiring** (A-14) — new checks or new dependents force re-routing.
- **Failure:** unclassifiable goal ⟹ escalate (S4 research or a Decision). Misclassification is caught late by dependents-expiry and re-routes.
- **Review:** the classification's read-set is auditable; drift re-fires S2.
- **Routing:** always. This stage *is* the router.
- **Founder:** only if classification is impossible without ground truth (rare).
- **Automation:** fully automatable (Router = SELECT×GOALSTRUCT), with the one escalation valve.
- **Why / Prevents / Forced-by:** uniform ceremony is the master waste; classification is what lets Trace-A skip 7 stages and forces Trace-B through all 12 → prevents both bureaucracy-on-trivia and rigor-starvation-on-danger → **PAEOS-0 router, PAEOS-4 §7, A-12, A-14.**

### S3 — DECOMPOSE  *(conditional: non-leaf goals)*
- **Objective:** split a goal into independently reconcilable children.
- **Inputs:** a non-leaf Goal + its constraints.
- **Outputs:** child Goals (each with serving_clause + evidence_spec), an aggregation contract, tightened-only constraints (D2).
- **Entry:** S2 classified the goal as too large for one reconciliation loop.
- **Exit:** children exist; **intent-conservation audit** passes (no orphans serving no clause, no gaps in parent clauses); **spec-sufficiency audit** passes (A-11 — can't satisfy a child's spec while violating parent intent).
- **Evidence:** conservation + spec-sufficiency audit records (FALSIFY×GOALSTRUCT).
- **Failure:** orphan/gap/loosened-constraint ⟹ redecompose or escalate (constraint loosening is a founder Decision, D2/I10).
- **Review:** adversarial attack on the decomposition (irreversibility-concentration, verification-seam quality — including "is this a good *product* boundary or only a good *audit* boundary?", Ω-24).
- **Routing:** non-leaf only. Rival decompositions + tournament when the split is itself high-fanout/irreversible (Trace-B recursion).
- **Founder:** only the topmost/most-irreversible splits (a Decision).
- **Automation:** automatable; the decomposition *criterion* is fixed — **concentrate irreversibility, distribute verifiability.**
- **Why / Prevents / Forced-by:** bad seams force joint verification (throughput collapse) and ship products shaped like audit trails → prevents the F8 livelock's decomposition root cause and Conway mis-shaping → **PAEOS-2 §6, A-11, A-07, Ω-24.**

### S4 — GROUND  *(conditional: a promotion is blocked by missing world-knowledge)*
- **Objective:** produce the specific world-Evidence a blocked stage needs.
- **Inputs:** a named blocker (S2 can't classify / S3 can't bound constraints / S5 can't select).
- **Outputs:** Evidence about the world (research artifact) with a named consumer.
- **Entry:** a specific downstream promotion is blocked for want of external knowledge.
- **Exit:** the blocker resolves; the consuming stage can proceed.
- **Evidence:** research findings, bound (K2) — they expire as the world moves.
- **Failure:** unbounded/consumer-less research ⟹ scope creep, flagged by conservation audit.
- **Review:** the consumer validates sufficiency; findings are adversarially checkable.
- **Routing:** pull-driven only. **No speculative "research phase"** — evidence gathered ahead of need expires before use (I2).
- **Founder:** injects ground truth the system cannot generate (Inject verb) — market/user/money.
- **Automation:** knowledge-goal research automatable (Builder/Adversary on knowledge goals); founder-only for external ground truth.
- **Why / Prevents / Forced-by:** research-as-phase produces stale, unconsumed evidence → prevents front-loaded investigation waste → **PAEOS-2 §3, I1, I2.**

### S5 — EXPLORE & SELECT  *(conditional: generation is uncertain; degenerate case = single build)*
- **Objective:** find the right approach among rivals, cheaply.
- **Inputs:** a leaf (or decomposition) goal whose best approach is non-obvious.
- **Outputs:** N candidate artifacts (`speculated`, branch-isolated per A-16) + a selection verdict.
- **Entry:** S2 says errors decorrelate across attempts AND selection is cheaper than generation.
- **Exit:** one candidate selected by a Judge against the taste corpus; losers retained (evidence, not waste).
- **Evidence:** candidate artifacts + a Judge verdict (SELECT×WORK). **Modes** (all Trace-B): first-principles **re-derivation** (challenge inherited approach), **ambitious ideation** (widen the candidate space), **tradeoff analysis** (make the axes explicit for the Judge).
- **Failure:** degenerate candidate distribution (all N ≈ identical) ⟹ fan-out was wasted, collapse to single build; evidence-starved Judge ⟹ spawn S4.
- **Review:** blind judging against exemplars; tie/starvation → founder Curate (taste) or Decision.
- **Routing:** Trace-B / uncertain-generation only. Trace-A skips this entirely — the surviving build *is* the plan.
- **Founder:** Curate (taste exemplars) when the Judge starves; never picks the winner directly.
- **Automation:** tournaments automatable; fan-out N is budget-bounded (verification, not tokens) and tuned by evolution.
- **Why / Prevents / Forced-by:** debating approaches is slower than building and judging them; but fanning out where errors correlate buys nothing → prevents both analysis-paralysis and wasteful parallelism → **PAEOS-2 §4, PAEOS-0 tournaments, A-16.**

### S6 — CONSTRUCT
- **Objective:** build the selected approach to a runnable state.
- **Inputs:** the selected candidate / a leaf goal + its compiled context (constitution+role+**capability-resolved skills**+links+evidence).
- **Outputs:** work-product Artifacts; a self-reported `executed` state.
- **Entry:** an approach exists (S5 winner, or Trace-A direct).
- **Exit:** artifacts exist and ran; builder self-reports execution.
- **Evidence:** builder's execution self-report (NOT promoting evidence — X6 forbids self-verification).
- **Failure:** cannot build within budget ⟹ cap-overrun incident (A-12).
- **Review:** none here — review is S7's job, by a different stance (I3).
- **Routing:** always (the one stage that always runs).
- **Founder:** never (clean-intent: the founder does not write work products; a direct edit is an auto-incident).
- **Automation:** fully automatable (Builder = GENERATE×WORK); capability requirements (CAP-1) guarantee the right skill loads even on greenfield goals.
- **Why / Prevents / Forced-by:** generation is the cheap step; keeping it separate from verification is what makes independent verification possible → prevents self-certifying builders → **PAEOS-0 A1, X6, K5, CAP-1.**

### S7 — VERIFY
- **Objective:** produce independent evidence that the work meets its evidence_spec.
- **Inputs:** `executed` artifacts + the goal's evidence_spec.
- **Outputs:** verifying-or-refuting Evidence sufficient to satisfy the spec (→ `verified`), or an Incident.
- **Entry:** goal is `executed`.
- **Exit:** evidence_spec satisfied by **live, independent** evidence, no live refutation.
- **Evidence:** **mechanical mode** — EXEC-emitted signed checks (A-09), repeatability-aware so a flaky check is not mistaken for a refutation (Ω-01); **adversarial mode** (verification-expensive quadrants) — an Adversary constructs failing inputs (I3), provenance-decorrelated from the builder (A-08); **whole-system mode** — emergent properties (perf, security-of-the-whole, coherence) get evidence attached to the *non-leaf* goal, since they don't compose from leaves (Ω-04).
- **Failure:** refuting evidence ⟹ regress + Incident (S9). Spec satisfied but intent not (spec-gaming) ⟹ caught by A-11/whole-system evidence.
- **Review:** this stage *is* review; adversarial review is its expensive mode, not a separate stage.
- **Routing:** always. Mode by quadrant: mechanical (cheap-verify) → +adversarial (expensive-verify) → +external evidence (v=external).
- **Founder:** Inject external ground-truth evidence for v=external goals.
- **Automation:** mechanical mode fully automatable; adversarial mode automatable via stance+model decorrelation; external mode is founder-fed.
- **Why / Prevents / Forced-by:** an AI reviewing its own (or a same-distribution peer's) work is verification theater → prevents correlated-blind-spot false confidence → **I1, I3, A-08, A-09, Ω-01, Ω-04.**

### S8 — INTEGRATE
- **Objective:** merge verified work into the trunk coherently.
- **Inputs:** a `verified` goal's artifacts.
- **Outputs:** trunk update (single-writer); parent aggregation-contract input recorded.
- **Entry:** goal is `verified`, no live refutation.
- **Exit:** merged to `trunk/<name>` by the single Integrator; parent promotion re-evaluated.
- **Evidence:** the merge commit + aggregation roll-up; post-integration evidence expiry does not regress (integrated is history) but spawns an Incident if it later goes stale (T2).
- **Failure:** merge conflict / coherence break ⟹ Incident; never parallelized away.
- **Review:** coherence is the Integrator's charge; conflicts route to S9.
- **Routing:** always, **single-threaded per trunk** (the one place concurrency is forbidden).
- **Founder:** Audit verb (optional) — walk integrated deltas + conservation report.
- **Automation:** automatable (Integrator = GENERATE×TRUNK), but serialized by invariant (K8/I9).
- **Why / Prevents / Forced-by:** architectural coherence is the property that fragments under parallelism → prevents incoherent merges → **I9/K8.**

---

*Evolution loop — triggered by outcomes across goals, not per goal. This is where the
constitution stays alive, and where "scar extraction / ledger / retrospective / prompt
evolution" actually live.*

### S9 — CAPTURE
- **Objective:** turn every failure into a tracked debt.
- **Inputs:** any of: refuting evidence, cap-overrun, escalation, post-integration expiry, founder direct-edit, conformance failure.
- **Outputs:** `Goal(kind=incident){ failure_ref, hazard_class }` — open until resolved.
- **Entry:** any failure signal fires.
- **Exit:** an Incident exists, hazard-classified (reversible/irreversible).
- **Evidence:** the failure record it points at.
- **Failure:** a failure that produces *no* incident is the meta-failure — latent/invisible failure never teaches (Ω-11), and selection then evolves *toward* unobservable failure modes (Ω-19). Weak evidence specs are the leak; S3's spec-sufficiency audit is the plug.
- **Review:** the Steward triages; nothing is closed by ignoring it.
- **Routing:** automatic (reactor T2/T5). Founder *direct edits* are themselves auto-incidents (clean-intent).
- **Founder:** none to capture; a founder whose behavior generates an incident (a direct edit) has revealed an ABI gap.
- **Automation:** fully automatable (reactor).
- **Why / Prevents / Forced-by:** no rule without a scar means scars must be caught first → prevents silent, unlearned failure → **K6, T2/T5, PAEOS-2 §5, Ω-11.**

### S10 — AMEND
- **Objective:** convert scars into policy so the failure-class cannot recur.
- **Inputs:** open Incidents; recurring one-offs; tournament results; firing records.
- **Outputs:** `Goal(kind=amendment){ policy_delta, motivation(scars), falsifier_watch, evidence_spec }` — the ledger entry.
- **Entry:** the Steward mines an Incident (or a founder Decision resolves toward policy).
- **Exit:** the amendment reaches `provisional` (delta applied, falsifier armed), then `verified | reverted` (A-06 probationary integration).
- **Evidence:** the amendment's own evidence spec, watched under operation; contested amendments go to tournament.
- **Failure:** the falsifier fires ⟹ **mechanical revert** (A-06). A one-off that recurs ⟹ it should have been an amendment (Ω-27) — the Steward audits one-off rate.
- **Review:** kernel-surface amendments run full Trace-B ceremony + a founder Decision (§14.5 self-application).
- **Routing:** Steward-owned; no other role may amend userland.
- **Founder:** Resolve verb for escalated Decisions; every Decision closes in an amendment or a recorded one-off (I8/K7).
- **Automation:** drafting automatable (Steward); founder resolves the irreducible residual. **This is "prompt evolution":** prompts are compiled from policy (K5), so evolving prompts = amending policy/skill artifacts — never hand-tuning text.
- **Why / Prevents / Forced-by:** an intervention that doesn't amend policy re-escalates forever → prevents constitutional stagnation and repeated founder toil → **PAEOS-1 §8, A-06, K6, I8, Ω-27.**

### S11 — PRUNE & ROTATE  *(Steward, continuous)*
- **Objective:** keep the constitution minimal, honest, and un-gamed.
- **Inputs:** firing records; the incident corpus; the live policy set.
- **Outputs:** pruning amendments (tombstones, A-13); rotated evaluation regimes; a reproducible-constitution result.
- **Entry:** periodic Steward cadence, or a firing record going quiet.
- **Exit:** quiet policies tombstoned; metric regimes rotated; re-derivation matches the live constitution (or an Incident is filed).
- **Evidence:** firing-record analysis; the **reproducible-constitution test** (re-derive from scars blind; divergence = Incident, PAEOS-3 S5); regime-rotation records.
- **Failure:** unpruned bloat taxes every context (K10); un-rotated metrics let honest optimization Goodhart the evidence regime (Ω-19); path-dependence traps the constitution in a bad basin (Ω-20 — vicarious/foreign scars are the escape, A-18).
- **Review:** an Adversary argues for deleting each rule; re-admission of a tombstoned rule needs evidence exceeding the original scar (A-13).
- **Routing:** cross-goal, continuous, low-priority.
- **Founder:** none routinely (this is automatable retrospective-with-teeth).
- **Automation:** highly automatable (Steward = GENERATE×POLICY + FALSIFY×POLICY).
- **Why / Prevents / Forced-by:** an OS that only grows is dying; a metric selected-upon drifts from its intent → prevents bloat, Goodhart drift, and basin lock-in → **PAEOS-0 falsifiers, K10, A-13, Ω-19/20.**

### S12 — SOUNDNESS AUDIT  *(founder-anchored, periodic — the one stage that must NOT decay)*
- **Objective:** verify the evaluation machinery itself is still sound and still aimed at reality.
- **Inputs:** integrated deltas; the intervention-rate trend; live root goals; sampled ground truth.
- **Outputs:** a founder soundness attestation; re-ratified (or amended) root goals; injected reality.
- **Entry:** periodic, founder-paced (queue-pressure equilibrium, PAEOS-2 §7).
- **Exit:** the founder has sampled ground truth, confirmed the evidence regime hasn't Goodharted, and re-ratified live root goals against current reality (Ω-17).
- **Evidence:** founder-injected external evidence (highest provenance); attestation record.
- **Failure:** a flat intervention rate = Steward failing to mine Decisions (Incident). **Letting this stage decay to zero is the constitutional failure** — the system loses its Gödel escape hatch (Ω-14), its Goodhart immunity (Ω-19), and its freshness (Ω-05/22) in one economy.
- **Review:** this stage *is* the meta-review; nothing internal can review it (self-certification limit).
- **Routing:** cross-system, periodic; never skipped, never fully automated.
- **Founder:** irreducible. The five verbs converge here at maturity to **Author + Inject + this audit** — the channels no policy can absorb.
- **Automation:** deliberately **bounded below** — the founder channel is the only non-Goodhartable signal; "minimize founder intervention" means *spend it only on soundness, taste, and ground truth*, never eliminate it.
- **Why / Prevents / Forced-by:** a self-hosting system cannot prove its own evaluator sound from inside → prevents a corrupted regime ratifying itself forever → **Ω-14, Ω-19, Ω-22, PAEOS-3 S5.**

## 4. Routing profiles (which stages instantiate)

| Quadrant | Stages instantiated | Founder | Typical latency |
|---|---|---|---|
| Reversible × cheap-verify (Trace-A) | S1 S2 S6 S7ᵐ S8 | none | minutes, autonomous |
| Reversible × expensive-verify | + S5 S7ᵃ | Curate on starve | hours |
| Irreversible × cheap-verify | + S3 (gated) S7 mechanical-gate | none if policy-covered | hours |
| Irreversible × expensive-verify (Trace-B) | all of S1–S8, heavy S3–S5 | Decision (S2/S3/S5) | days; ceremony point-mass |
| Any failure | + S9 → S10 (→ S11 background) | Resolve if escalated | — |
| Periodic | S11 (Steward), S12 (founder) | S12 irreducible | — |

ᵐ mechanical only · ᵃ adversarial mode added.

## 5. Founder ABI mapped to stages

| Verb | Stage(s) | Decays? |
|---|---|---|
| Author | S1 (root goals) | never (intent, A4) |
| Resolve | S2/S3/S5 escalations → S10 | toward zero as policy accretes |
| Inject | S4, S7 (external), S12 | never (ground truth, A4) |
| Curate | S5 (Judge starvation) | toward zero |
| Audit | S8 (optional), **S12 (mandatory floor)** | S12 must NOT decay (Ω-14) |

## 6. Freeze, portability, and graduation

- **Frozen** as the master Protocol v1.0. Amendments to it run the same §14.5 ceremony as
  any kernel-surface change (it is self-applying: a change to the lifecycle is Trace-B).
- **Workload-agnostic:** kernel-scope. Each workload (Sentium, Orca-Strator, Inspiration
  Engine, Library of Fire, SAKG) may **tighten** it in workload scope (A-17), never loosen
  (D2). Loosening is a founder Decision.
- **Graduation:** during bootstrap this lives as `methodology/` + the checklist + the
  runtime prompt (genesis-authority scaffolds). At S3+, it becomes `Policy(kind=protocol)`
  artifacts the Compiler assembles automatically — at which point the runtime prompt
  (a hand-written prompt) is *replaced by the Compiler* (K5), and this document's
  authority moves into the store it describes.

## 6a. Two resolutions of one lifecycle (methodology ↔ operations)

This document is the **constitutional** resolution: 12 evidence-distinct stages, kernel-
integrated, router-conditional. The **operational** resolution lives in
`operations/ENGINEERING_LIFECYCLE.md` as **19 states (L01–L19)** — the human-facing,
Runtime-executable expansion the founder specified. They are the *same lifecycle*; the 19
states are a finer cut of the 12 obligations, and the router principle survives in
operations as **ceremony depth**: every artifact still passes every gate that produces
evidence (the founder's "no direct Intake→Implementation" rule holds), but for Trace-A
work the Runtime **auto-discharges** the Trace-B front-end states (L03–L11) in a single
pass, while Trace-B work executes them in full. Crosswalk:

| 12 constitutional stages | 19 operational states |
|---|---|
| S1 Frame · S2 Route | L01 Intake · L02 Triage |
| S3 Decompose · S4 Ground · S5 Explore&Select | L03 First-Principles · L04 Ideation · L05 Frontier Research · L06 Trade-off Analysis · L07 Trade-off Mitigation · L08 System Design |
| S7 Verify (design-stage adversarial mode) | L09 Multi-Perspective Critique · L10 Adversarial Review |
| S1/S3 (implementation contract) | L11 Formal Planning |
| S6 Construct | L12 Branch Implementation |
| S7 Verify | L13 Verification · L14 Independent Audit |
| S8 Integrate | L15 Documentation & Ledger · L16 Promotion Decision |
| S10 Amend · S11 Prune | L17 Retrospective · L18 Knowledge Extraction |
| S9 Capture · S10 Amend · S12 Soundness-Audit | L19 Constitutional Evolution |

Neither doc overrides the other: methodology explains *why and how much*; operations
defines *the executable states, transitions, roles, and prompts*.

## 7. The one-sentence version

**The Constitutional Engineering Lifecycle is a 12-stage maximal ceremony envelope —
Frame, Route, Decompose, Ground, Explore&Select, Construct, Verify, Integrate, Capture,
Amend, Prune&Rotate, Soundness-Audit — of which the router instantiates only the subset a
goal's verifiability × reversibility demands (5 for routine work, all 12 for the rare
irreversible-and-unverifiable node), ordered by evidence dependency rather than calendar,
gated at every step by independent evidence, closed by an evolution loop that turns every
scar into policy, and anchored by one founder audit that is forbidden to decay.**
