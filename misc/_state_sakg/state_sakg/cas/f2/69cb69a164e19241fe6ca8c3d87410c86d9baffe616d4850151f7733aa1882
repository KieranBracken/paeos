# Constitutional Governance Analysis — Institutional-Memory Ownership (IP-0004 / IP-0005)

**Date**: 2026-07-30 · **Channel**: CER-2/CER-4 governance · **Author role**: Auditor (recommends;
does not legislate — CER-5) · **Status**: analysis for founder decision. No implementation modified.

Scope: execute the six-phase constitutional governance process the founder directed over the two
implementation-surfaced proposals — **PAEOS-IP-0005** (ownership of institutional-memory *creation*)
and **PAEOS-IP-0004** (Ephemeral Execution Context vs. Institutional Memory). Derivation is from the
corpus only; each conclusion is falsified before it is kept (CER-1).

---

## Phase 1 — Are *Trigger*, *Author*, *Commit* constitutionally distinct?

**Conclusion: YES — three distinct acts, three distinct owners, three distinct clause bases, at three
distinct lifecycle positions.** A single subsystem owning all three is *forbidden* by the corpus's own
separation-of-powers (MR / §5.1).

| Act | Subsystem owner | Lifecycle stage | Constitutional basis |
|---|---|---|---|
| **Trigger** — a lesson is *warranted* | The **adjudicating power**: Verification Court (in-lifecycle); Kernel incident/quarantine (post-seal) | **VERIFY (11)** / **ADVERSARIAL_REVIEW (12)** / **G-Seal reject (14)** / **post-seal incident (§4.5)** | **FR-4** (failure is an *adjudicated fact*, not an opinion); **§4.3** (Court); **§4.4** ("a reject is a lesson, not a deletion"); **§7.3** (post-seal regression ⇒ the *gate* is examined) |
| **Author** — the artifact's *content* (root cause + detection signature; or a checklist/skill delta) | The **Evolution Layer** (writing hand: **Documentation** role) | **RETROSPECT (15) → EVOLVE (16) → MEMORY_UPDATE (17)** | **§3.2** (Evolution Layer owns 15–19); **§7.1** (15 extracts root cause; 17 writes the scar); **§5** (Documentation "only *records* what the powers decided"); **CER-5** (recommend-not-legislate) |
| **Commit** — the durable, indexed, append-only write | The **Kernel** (single writer) | **MEMORY_UPDATE (17)**, gate **G-Memory** | **FR-5** (single-writer append-only); **§3.7** ("scar *writes* serialize through the kernel at stage 17; no agent may delete"); **§3.4(a)** (every mutation ends in a kernel append); **§6** rule 4 ("agents propose, the kernel commits") |

**Falsification attempts (all fail to collapse the distinction):**
- *"The remand IS the lesson — trigger = author."* No. A remand is a verdict *on this artifact*; §7.1
  requires RETROSPECT to extract a *reusable root cause + detection signature* — a different asset. The
  Court says "this failed"; the Evolution Layer says "here is the transferable guard."
- *"The Evolution Layer writes the scar — author = commit."* No. §3.7 + §6 rule 4 + §3.4(b) make the
  authored draft *inert* until the **kernel** accepts it at G-Memory. Same shape as the ledger: agents
  produce, only the kernel appends.
- *"Trigger is the kernel, not the Court."* The kernel *records* the verdict; the Court *reaches* it.
  For the trigger act the owner is the *adjudicating* power (Court at 11/12, seal-authority reject at
  14, kernel-incident post-seal) — nuance preserved, distinction intact.

The three acts are distinct. This is the foundational finding.

---

## Phase 2 — Relationship of IP-0004 and IP-0005

**Conclusion: HIERARCHICAL.** IP-0005 is **foundational**; IP-0004 is its **operational corollary**
(not a code "implementation," but the derived operational-state complement).

- **IP-0005 (foundational)** establishes the *constitutional authority structure* of institutional
  memory: the Trigger→Author→Commit trilogy of Phase 1. It is a general principle spanning multiple
  corpus documents.
- **IP-0004 (dependent)** answers the question IP-0005 *forces*: "if operational execution may not
  author or commit institutional memory, what *may* it retain across retries within one run?" It names
  that category — **Ephemeral Execution Context** — and confines it (Axiom 1: destroyed at run-scope
  end, never enters institutional memory; Axiom 2: explicitly defers memory authority to IP-0005).

**Not** the other classes: they are not *duplicates* (authority-of-memory vs category-of-transient-
state are different subjects); not *conflicting* (IP-0004 Axiom 2 aligns to IP-0005 by construction);
not *independent* (strip IP-0005 and IP-0004 loses its constitutional anchor); "overlapping" understates
it — the overlap is *structured as dependency*, which is hierarchy.

**Falsification:** *"They are independent — one is about memory, one about retries."* Fails: IP-0004's
sole justification is preventing operational execution from violating IP-0005's memory authority. A
dependency that fundamental is a hierarchy, not independence.

**Direction of the hierarchy:** IP-0005 → IP-0004 (foundational principle → the operational complement
it necessitates).

---

## Phase 3 — Should PAEOS distinguish (A) transient run-scoped execution state from (B) cross-run institutional memory?

**Conclusion: YES — the distinction is real, load-bearing, and currently *unnamed*.**

**Derivation from the existing taxonomy.** §3.5/§6 already classify *persisted* data two ways:
**durable / source-of-truth** (ledger + CAS, single-writer kernel) and **derived / disposable**
(projections — goal state, work queues, *scar indices*, cost counters — "losing a projection is a
rebuild, not a data loss"). FR-3 additionally relies on a *third*, implicit category: builder
**scratch / scratchpad / reasoning lineage** — session-scoped, isolated, *never institutional*. So the
corpus already recognizes transient session-scoped state — but only as the *agent's private reasoning*,
never as a named *runtime* category.

**The gap.** "Run-scoped operational state that may inform a retry (a `retry_hint`, a compiler
diagnostic, a backoff flag) but must never become a cross-run guard" is:
- **not durable** (it is not source-of-truth, not committed to the ledger),
- **not a projection** (it is not *derived from* the ledger and is *not rebuildable* — it dies with the
  run), and
- **not agent scratch** (it is *runtime-level* operational state on the kernel-minted TaskPackage, not
  the agent's private reasoning).

It is a genuine fourth category with no name. Left unnamed, operational subsystems conflate it with
institutional memory — which is exactly the divergence that surfaced these proposals (a within-run
remand promoted to a cross-run scar), a **CER-5 authority violation** and a **T3 poisoning vector**
(run-local noise elevated to a standing guard).

**Derived architecture (two categories, cleanly separated):**

| | (A) **Ephemeral Execution Context** | (B) **Institutional Memory** |
|---|---|---|
| Scope / lifetime | one `run_id`; **destroyed** at run-scope end | cross-run; permanent (append-only) |
| Carrier | kernel-minted **TaskPackage** (PAEOS-7.6 §5) — already run-scoped | **Scar Store / ledger / CAS** |
| Owner | operational runtime (SoftLoop, stages 1–14) | Trigger (Court) → Author (Evolution, 15–17) → Commit (Kernel) |
| Promotion rule | may inform a retry; **may never become memory except via the trilogy** | authored/committed only by the Phase-1 owners |

**Terminology (Phase-3 rule: don't invent unless required; recommend via proposal if existing is
insufficient).** Existing terms are insufficient: "projection" is a ledger-derived view (wrong);
"scratch" is agent-private reasoning (wrong scope). A new term is *required*, and IP-0004 already
supplies it through the proper channel: **"Ephemeral Execution Context."** I recommend adopting it — it
is complementary to (not a duplicate of) "scratch": scratch is the agent's; EEC is the runtime's.

**Falsification:** *"Isn't this just 'projections are disposable'?"* No — a projection is *rebuilt from
the ledger*; EEC is *never in the ledger* and is *unrebuildable*. Different category. *"Could EEC be a
backdoor to smuggle a lesson past the Evolution Layer?"* Only if it could persist or be read cross-run
— which Axiom 1 forbids by construction (destroyed at scope end, carried on a non-persisted
TaskPackage). The distinction *closes* the hole rather than opening one.

---

## Phase 4 — Constitutional impact of ratifying IP-0005

| Target | Impact | Classification | Basis |
|---|---|---|---|
| **PAEOS-4** (frozen kernel) | **None required.** IP-0005 governs the *runtime FR-6 memory-creation flow*; it does not alter **K6** (constitutional clauses carry a scar+falsifier — a *genesis* scar, founder-authored, a different layer from runtime failure-memory), **K7** (one-off vs amendment), or any K-invariant. *Optionally*, elevating the Trigger→Author→Commit trilogy to a **named kernel invariant** would be a constitutional amendment — founder's discretion, **not** required for ratification. | **no change** (optional: constitutional amendment) | K6/K7 untouched; MR/§5.1 already supply the principle |
| **PAEOS-7** (runtime architecture) | Sharpen §3.2/§3.7/§4.4/§5/§7.1 to state exclusivity: institutional memory is *authored only in stages 15–17 by the Evolution Layer*; *detection stages 11/12 emit triggers only*; *commit stays kernel-serialized at G-Memory*. Consistent with existing text (no contradiction). | **execution architecture clarification** | already implied by §3.7; made explicit |
| **PAEOS-8** (implementation playbook) | Add the corrective task (**B2.G**) to §10; note memory-ownership in Phase-2 scope. | **execution architecture clarification** | playbook = the executable plan |
| **PAEOS-9** (execution architecture) | Would document the EEC-vs-institutional-memory distinction (Phase 3) and the trilogy in the execution model. *Provisional* — PAEOS-9 is founder-owned/uncommitted; I cannot see its final text. | **execution architecture clarification** | founder-owned doc |
| **Runtime implementation** | Relocate the SoftLoop inline scar → Evolution Layer; (optional) add an EEC field to TaskPackage per IP-0004 Axiom 1. | **implementation change** | `SoftLoop.run`, `evolution.py`, `selfhost.py` |
| **Engineering Lifecycle** (`operations/` + methodology) | Minor note: memory authoring is stages 15–17 exclusive. Already consistent with §7.1. | **execution architecture clarification** (borderline **no change**) | §7.1 already says 15/17 |

**Net:** ratifying IP-0005 requires **no constitutional (PAEOS-4) amendment** — it is a *faithful
clarification* of PAEOS-7/8 plus one implementation change. That it needs no kernel amendment is itself
evidence it was *derived*, not invented (CER-6).

---

## Phase 5 — Recommendation

**Outcome 3 — Ratify BOTH, in dependency order (IP-0005 first, then IP-0004), and keep them separate.**

**Constitutional justification.** IP-0005 is *derived from* the constitution (Phase 1 proof stands under
falsification); ratifying it adopts a faithful clarification that strengthens PAEOS (CER-1) at zero
kernel-amendment cost (Phase 4). IP-0004 is the operational corollary IP-0005 *forces* (Phase 2); its
Axioms are consistent with CER-5 and §3.7 and *close* the category error that caused the divergence
(Phase 3). Both **recommend**; neither **legislates** — the founder ratifies (CER-5).

**Why not merge (outcome 5), though they are a matched pair?** Falsifying my own preference: merging is
tempting for atomicity, but it **loses a real distinction of kind** — IP-0005 is a *cross-document
constitutional clarification* (PAEOS-4/7/8/9 assessment, a general principle); IP-0004 is a *specific
architectural mechanism* (new terminology + a concrete TaskPackage carrier). They warrant *different
review depth* and should be *independently auditable*, per the corpus's single-source discipline (CER-2).
The founder's own refinement already structured them as two complementary proposals; merging would undo
it. Keep separate; ratify as a pair.

**Why not reject one (outcome 4)?** Neither is falsified; each carries load the other cannot. Rejecting
IP-0004 would leave "what may execution retain?" unanswered and invite the same conflation to recur;
rejecting IP-0005 would leave the divergence uncorrected and the trilogy unstated.

---

## Phase 6 — Implementation consequences (identified, NOT performed)

- **Earliest B-stage that must change:** a **new task B2.G — "relocate institutional-memory authoring
  to the Evolution Layer / stage 17."** It is the earliest *forward* task; the *origin* of the
  divergence is the already-ratified **B1.F / B1-SOFTLOOP** (which introduced the inline scar) — history
  is not rewritten (FR-5); B2.G supersedes the behaviour forward.
- **Affected runtime component(s):**
  - `runtime/orchestrator/__init__.py` — `SoftLoop.run`: remove the inline `propose_scar` on remand;
    (optional, per IP-0004 Axiom 1) attach an **Ephemeral Execution Context** (`retry_hint`) to the
    TaskPackage instead of a scar.
  - `runtime/evolution.py` (B2.F) — becomes the **sole** memory author (already built; no change needed
    beyond being wired in).
  - `runtime/selfhost.py` — wire the Evolution Layer as the post-run pass; surface IMPROVE_RUNTIME
    proposals.
  - `runtime/task_package.py` — (optional) add an EEC field if Axiom 1 is implemented.
  - Tests: `tests/runtime/test_soft_loop.py`, `tests/runtime/test_selfhost.py` — assertions move from
    the loop's coarse scar to the Evolution Layer's precise, goal-tagged scar.
- **Behavioural change:** the SoftLoop no longer authors/commits institutional memory. A remand yields
  an *ephemeral*, run-scoped signal (destroyed at scope end) and returns `REMANDED`; the **scar** is
  authored only by the Evolution Layer (15–17) and committed by the kernel (G-Memory, 17). Recurrence
  detection becomes correct (no false first-occurrence trigger — the original IP-0004 symptom).
  Institutional memory becomes single-owner.
- **Migration impact: negligible.** No durable institutional-memory corpus exists yet (scars live in an
  in-memory `ScarStore`); the ledger is append-only and untouched (no rewrite). This is the *ideal*
  moment to make the change — **before** durable memory accrues — which is itself an argument to ratify
  now (CER-1, forward-looking).

---

## Summary for the founder

1. **Trigger / Author / Commit are constitutionally distinct** (Phase 1) — Court / Evolution Layer (15–17) / Kernel (G-Memory 17), each with its own clause basis.
2. **IP-0005 ⊐ IP-0004 (hierarchical):** foundational principle → operational complement (Phase 2).
3. **Yes, distinguish transient run-scoped state from cross-run memory** (Phase 3); adopt IP-0004's required new term **"Ephemeral Execution Context"** (existing terminology is insufficient).
4. **IP-0005 needs no PAEOS-4 amendment** — clarifications to PAEOS-7/8/9 + one implementation change (Phase 4).
5. **Recommendation: ratify both, in order, kept separate** (Phase 5).
6. **Earliest task to change: new B2.G**; migration impact negligible; ratifying now is cheapest (Phase 6).

*This analysis recommends; it does not legislate. No implementation was modified; no ratified behaviour was touched (CER-5/CER-6).*
