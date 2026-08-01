# PAEOS-IP-0009 — Name the Constitutional Evolution Loop (a second lifecycle)

Status: **AWAITING FOUNDER** · Filed: 2026-08-01 · Channel: CER-2
Level: **architectural clarification** (names an existing process; **invents no mechanism** — CER-6).
Source finding: the Phase-3 architectural review (`reviews/phase3_architectural_review.md`, Phase 4).
Supersedes: none. Companion to: IP-0010 §6 (the invariants registry, which recommended this proposal;
note IP-0008 was re-used for the ratified WorkerTransport architecture, so the invariants registry is
now IP-0010).

## 1. Problem

Phase 3 was dominated by a process the constitution does **not name**: *build a task → CER-1
falsification exposes a constitutional gap → an Improvement Proposal → founder ratification → an
architectural refinement → the next build.* Every Phase-3 amendment (IP-0004..0008, B2.K, B2.O, the
`EvidenceSource`/`WorkerTransport` boundaries) came out of this loop. It is **not** the 19-stage
goal-execution lifecycle: that lifecycle executes *one goal* (intake→…→seal→retrospect); this loop
governs how PAEOS's *own architecture and constitution* evolve, across many goals and sessions. Two
distinct processes are currently described with one vocabulary, which obscures that PAEOS runs **two
lifecycles**, and leaves the dominant Phase-3 activity without a canonical form, entry/exit criteria,
or a home.

## 2. First-principles derivation

- The constitution already contains every *mechanism* the loop uses: **FR-2** (adversarial ratification
  + human sign-off), the **§7.4 amendment path**, **CER-1** (mandatory falsification), **CER-2**
  (proposals), **CER-5** (runtime recommends, founder ratifies), stage **18** (IMPROVE_RUNTIME).
- What is *absent* is the recognition that these compose into a **continuous loop with its own phases**,
  operating at a different granularity than a goal. The 19-stage lifecycle's stage 18 emits a proposal
  *for one goal*; the Evolution Loop is the *cross-goal* control system that turns accumulated
  proposals + falsifications into ratified architectural change and feeds it back into the next build.
- Derived phases (all from existing law, no new step): **(a) Implement** (a task, under the 19 stages);
  **(b) Falsify** (CER-1 — attack the current architecture, not just accept the task); **(c) Surface**
  (CER-2 — an Improvement Proposal / Debt, never a silent change); **(d) Ratify** (CER-5/FR-2 — founder
  decides); **(e) Refine** (integrate the amendment as an execution-architecture clarification or a new
  task); **(f) Re-enter** (the refinement changes the substrate the next Implement builds on).
- This is a *control loop* (measure → falsify → correct) over the constitution itself — exactly the
  PAEOS-0 axiom "unenforced rules decay / every cycle attempts to falsify the constitution," but named
  as a lifecycle rather than a maxim.

## 3. Falsification attempts

- **"This is just stage 18 / the amendment path — already in the constitution."** Partly: the
  *mechanism* is. But stage 18 is *per-goal* and emits a proposal; the Evolution Loop is the *system
  that closes the loop across goals* — ratification, refinement, and re-entry are not stage-18 steps,
  they are founder + CER-driven and span sessions. Distinct granularity ⇒ distinct lifecycle. Survives.
- **"Naming it adds ceremony without value."** The value is disambiguation: today "lifecycle" means the
  19 stages, yet most Phase-3 work lived in the *other* loop; a name lets reviews, roadmaps, and CER
  reflections reference it precisely (and prevents conflating goal-execution metrics with
  constitutional-evolution metrics). Survives.
- **"It risks becoming a second constitution."** No — it introduces **no mechanism, no authority, no
  invariant**; it is a *descriptive* name over existing law. If it ever grows mechanism, that is a
  separate, ratified amendment. Survives.
- **"Two lifecycles is over-modelling; it's one lifecycle with a self-improvement tail."** The tail
  (stages 15–19) improves *within a goal's budget/scope*; the Evolution Loop changes the *kernel-
  adjacent architecture and the constitution itself* (hard loop, founder-gated) — a different blast
  radius and a different authority. FR-2/§7.4 already separate hard from soft self-improvement;
  IP-0009 only names the hard-loop *as a recurring process*. Survives.

## 4. Architectural impact

- **None on running code.** This is a naming + a short companion description (candidate:
  `methodology/CONSTITUTIONAL-EVOLUTION-LOOP.md`, mirroring the 19-stage lifecycle doc), cross-linked
  from `operations/ENGINEERING_LIFECYCLE.md` and the CER section.
- Clarifies that PAEOS has **two lifecycles**: *goal execution* (PAEOS-7 §4, the 19 stages) and
  *constitutional evolution* (this loop). Reviews and roadmaps gain a precise referent.

## 5. Dependencies

- Depends on: the existing amendment path (§7.4), CER-1..6, FR-2. Relates to IP-0008 (its invariants
  registry is a *product* of the Evolution Loop's Refine phase).
- No dependency on any unbuilt code; purely descriptive.

## 6. Classification

- **Architectural clarification** (not constitutional amendment, not implementation). It changes no
  kernel invariant, no authority, no mechanism. Needs founder ratification as an operational/spec
  clarification (CER-2/CER-5). No PAEOS-4 change.

## 7. Recommendation

**Ratify** the name and a one-page companion characterisation of the Constitutional Evolution Loop
(phases a–f above), cross-linked from the lifecycle/CER docs. It recommends; it changes nothing until
ratified. **No mechanism is invented; no code changes; no constitutional edit.**
