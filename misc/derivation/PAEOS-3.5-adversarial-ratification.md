# PAEOS-3.5: Adversarial Ratification

> **Archival status:** Ratification record, archived 2026-07-19. This is the derivation-
> layer summary — the verdict and the complete amendment ledger that PAEOS-4 was built
> from. The full adversarial working (seven investigation files: kernel stress test,
> invariant attacks, hidden assumptions, minimality audit, independent re-derivation,
> required amendments, verdict) lives in `reviews/3.5-adversarial/` and is the normative
> detail. Where this summary and those files differ, those files govern.

---

## Mandate

An independent constitutional court was instructed to **demolish** PAEOS-0..3, not improve them: remove unnecessary primitives, expose unenforceable invariants, merge concepts that secretly collapse, surface hidden assumptions, prove contradictions. Only demonstrated defects were admitted; every finding carried violated-principle, evidence, severity, and smallest-amendment fields. The corpus's only privilege was surviving scrutiny.

## Verdict: RATIFY WITH AMENDMENTS

The court proved a formal contradiction (amendments could not satisfy the lattice ordering their own evolution loop required), a forgeable foundation (evidence any agent could fabricate), an instability with no convergence guarantee (the expiry × single-integration rebase treadmill), and two missing subsystems (economics; tenancy — which contradicted the stated multi-project roadmap). A constitution containing a proven contradiction cannot ratify as written.

But every demonstrated defect admitted a **bounded** amendment: no primitive required forcible removal, no invariant required abandonment, the skeleton required no rework. Three reasons for RATIFY-WITH-AMENDMENTS over REJECT:

1. Every fix was clarification- or contract-grade, not architectural.
2. The corpus repeatedly contained its own fixes, unused (the Evidence provenance field anticipated the decorrelation amendment; "verification seams" anticipated the livelock fix; §8 already routed amendments as goals, anticipating the ontology collapse).
3. **The independence test converged.** Re-deriving from PAEOS-0's axioms alone, via the blackboard + truth-maintenance-system lineage, reproduced the same skeleton — store, evidence-with-expiry, ephemeral stanced agents, tournaments — and diverged in exactly the two places the adversarial attacks independently found (justification graphs; an explicit economics layer). Two unrelated methods locating identical gaps in an otherwise-convergent structure is the strongest available evidence the skeleton is forced by the axioms and the defect list is complete.

## What survived attack outright

The verifiability × reversibility router (no superior ceremony basis was constructible); the evolution loop's scar/falsifier/pruning discipline; the narrow waist and null-adapter conformance strategy; the founder ABI and clean-intent invariant; the genesis-authority bootstrap with scheduled expiry; demand-paging; Skills-as-Policy. Every element the corpus claims as novel held.

## The amendment ledger (19; 12 blocking before PAEOS-4)

| # | Fixes | Amendment | Class |
|---|---|---|---|
| A-01 | kernel-sentence overclaim | Two categories: reconciled objects (Goal, Policy) vs immutable records (Artifact, Evidence) | BLOCKING |
| A-02 | ontology collapse | Incident, Decision, Amendment become **Goal subtypes** (`goal.kind`); required fields preserved; I7/I8 rebind | BLOCKING |
| A-03 | untyped work product | **Artifact** base type (content-addressed + provenance); **Trunk** defined as integrator-owned ref | BLOCKING |
| A-04 | role compression | Role = **(stance × domain)**; seven names kept as conventional bindings | recommend pre-4 |
| A-05 | Compiler judgment | Compiler deterministic over the **explicit link graph**; link-authoring is a Generate-stance duty | BLOCKING |
| A-06 | lattice contradiction | **Probationary integration** for `goal.kind=amendment`: executed → integrated-provisional → verified \| reverted; integration arms the falsifier | BLOCKING |
| A-07 | livelock | Evidence binds to the goal's **declared read-set** (justification graph), not trunk state; sibling read-set overlap = decomposition admission criterion | BLOCKING |
| A-08 | correlated verification | I3′: non-mechanical verification must be **provenance-decorrelated** (different model family, or mechanical augmentation with recorded deficit) | BLOCKING |
| A-09 | forgeable evidence | Execution-class Evidence **emitted by the EXEC syscall**, adapter-signed; agents cannot author it | BLOCKING |
| A-10 | no conflict rule | Default-deny: live refuting evidence blocks promotion until superseded or expired | do at genesis |
| A-11 | spec-gaming | Decomposition audit gains **spec-sufficiency** check | deferrable |
| A-12 | budget non-conservation | **Conservation law**: Σ(child budgets) ≤ parent − decomposition cost; roots founder-set; Evidence records cost | BLOCKING (law) |
| A-13 | prune/re-admit oscillation | Pruning writes **tombstones**; re-admission requires evidence exceeding the original scar | deferrable |
| A-14 | quadrant drift | Classification **is Evidence** — bound and expiring under I2; quadrant-relevant changes force re-route | recommend genesis |
| A-15 | unaudited root goal | **Root-goal ceremony**: adversarial interrogation of every root Goal before decomposition | deferrable |
| A-16 | SPAWN semantics | SPAWN contract requires **speculation-branch isolation**; sequential emulation must branch-isolate; conformance-tested | BLOCKING |
| A-17 | missing tenancy | Policy **namespaces** (`scope ∈ {kernel, workload:<id>}`); kernel-promotion requires scars in ≥2 tenants | BLOCKING (field) |
| A-18 | learn-by-dying in irreversible regime | **Vicarious scars**: imported/anticipated scars satisfy I7 for irreversible hazards, with stricter falsifiers | BLOCKING |
| A-19 | hidden assumptions | Genesis-record clauses: single-founder; parchment (founder-sovereignty limit); NL-as-policy-encoding + falsifier; I12 falsifier | BLOCKING (honesty) |

## The ratified kernel shape (input to PAEOS-4)

Four primitives (Artifact, Goal, Evidence, Policy) · ten axioms + one conservation law + two derived guarantees · three stances × four domains · three primitive syscalls + one optimization · evidence as a justification graph with adapter-signed execution records · namespaced policy for multi-tenancy · probationary integration for policy changes. Smaller than what was submitted, and stronger — which is what a constitution should look like after meeting its court.

## Honesty clause carried forward (the parchment finding)

Every enforcement mechanism in PAEOS is ultimately founder-revocable; against the founder, enforcement is *detection plus convention*, nothing more. This is the condition of all constitutions, and PAEOS states it in its preamble rather than obscuring it behind words like "forbidden" and "mechanically enforced."

*Filed by the PAEOS-3.5 constitutional review. Survived with 19 amendments, 12 blocking.*
