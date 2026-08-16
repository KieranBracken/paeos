# 02 — Invariant Attacks (Consistency, Evidence Model, Stability, Router)

Investigations 2, 4, 5, 6.

---

## F7 — Formal contradiction: Amendments cannot satisfy the lattice ordering **[CONFIRMED — ARCHITECTURAL, SEVERITY: HIGHEST]**

**Violated principle:** Internal consistency of I1 + the evidence lattice (PAEOS-1 §2).

**Proof:**
1. PAEOS-1 §2 fixes the lattice order: `… → verified → integrated`, and I1 requires promotion to `verified` via evidence satisfying the object's evidence spec.
2. PAEOS-1 §1.6: an Amendment *"carries its own evidence spec ('we'll know this amendment worked if…')"* — evidence obtainable only by **operating under the amended policy**.
3. A policy operates only when loaded into compiled contexts (I6), which happens only after the policy delta is applied to the live Policy store — i.e., after **integration**.
4. Therefore for policy-goals: `verified` requires `integrated`; the lattice requires `verified` **before** `integrated`. Contradiction. ∎

**Why it matters:** The evolution loop — the mechanism the whole self-hosting argument rests on — is unimplementable as specified. PAEOS-3 S3's exit criterion ("one complete Incident → Amendment → recompiled-context cycle") cannot be satisfied without violating I1 or the lattice.

**Classification:** Architectural.

**Smallest amendment (A-06 — "probationary integration"):** Policy-kind goals follow an inverted tail: `executed → integrated-provisional → verified | reverted`. Provisional integration **arms the falsifier**: the amendment's evidence spec becomes a live watch; refuting evidence triggers mechanical revert. This is one new lattice state reachable only by `goal.kind ∈ {amendment}`.

---

## F8 — Livelock: I2 × I9 create a rebase treadmill with no convergence guarantee **[CONFIRMED — ARCHITECTURAL]**

**Violated principle:** Reconciliation must converge (implicit in PAEOS-1 §0); A1 (verification is the scarce resource being burned).

**Argument:** Let λ = trunk integration rate, p = probability an integration expires a pending `verified` goal's evidence (binding overlap), μ = re-verification rate. A pending goal completes only if it survives from re-verification to integration without invalidation. Expected invalidations per attempt = λp/μ. **If λp ≥ μ, the verified queue does not drain**: every integration regresses the queue faster than it re-verifies, and throughput collapses as parallelism rises — the more Builders you add, the higher λ, the worse the treadmill. PAEOS mechanized the rebase treadmill into an invariant.

**Corpus evidence of the gap:** binding granularity is explicitly deferred — PAEOS-1 §10: *"evidence-binding granularity (file vs hunk)"* is a bootstrap parameter. But the **existence of a stability condition** is structural, not tunable: no parameter choice rescues a system whose decompositions produce high binding overlap.

**Classification:** Architectural (the fix constrains decomposition admission, not just tuning).

**Smallest amendment (A-07):** (a) Evidence binds to the goal's **declared read-set** (justification graph — see 05), not to trunk state; (b) elevate PAEOS-2 §6's "verification seams" from heuristic to **admission criterion**: a decomposition whose siblings' read-sets overlap above threshold is rejected by the decomposition audit; (c) the Integrator may batch integrations to bound λp.

---

## F9 — I3 is weaker than the axiom that motivated it **[CONFIRMED — ARCHITECTURAL]**

**Violated principle:** A3, by the corpus's own words.

**Evidence:** PAEOS-0: *"An AI reviewing another AI's diff with the same training distribution shares its blind spots — this is verification theater."* I3 requires only *"evidence from a stance other than the builder's."* Same model + different stance = same training distribution — exactly the configuration PAEOS-0 calls theater. Sharper: PAEOS-1 §1.2 already requires Evidence provenance to record *"which model — required by A3, because a judge must be able to discount correlated evidence"* — **the field exists; no invariant consumes it.**

**Why it matters:** In the verification-expensive quadrants (where no mechanical check exists), I3 as written permits fully correlated verification, and those are precisely the quadrants where verification is the only defense.

**Classification:** Architectural.

**Smallest amendment (A-08):** I3′: where the evidence spec cannot be satisfied mechanically, verification evidence must be **provenance-decorrelated** — different model family where the runtime offers one; otherwise mechanical-check augmentation, with the correlation deficit recorded on the Evidence. Adapters declare available diversity; conformance notes the degraded mode.

---

## F10 — Evidence authentication does not exist: I1 is forgeable **[CONFIRMED — ARCHITECTURAL]**

**Violated principle:** I1's purpose; A6 (mechanical enforcement).

**Evidence:** The syscall contract (PAEOS-1 §6) gives every agent unrestricted WRITE. Nothing in the corpus distinguishes Evidence *produced by* EXEC from Evidence an agent simply *writes*, claiming an execution occurred. A Builder under spend-cap pressure can author an Evidence record asserting "tests passed" and promote its own goal. I1 gates on a category the kernel cannot verify the authenticity of.

**Classification:** Architectural (syscall contract).

**Smallest amendment (A-09):** Execution-class Evidence is **emitted by the EXEC syscall itself** (adapter-signed provenance); agents cannot author it via WRITE. The validator rejects execution-class Evidence lacking syscall provenance. Verdict/critique evidence remains agent-authored but is a distinct, lower-authority class — which A-08 already forces judges to weigh.

---

## F11 — No conflict rule: opposing live Evidence is unadjudicated **[CONFIRMED — SMALL]**

I1 says promotion requires satisfying evidence; the corpus never states what a live **refuting** record does. As written, a goal can promote past standing refutation. **Amendment (A-10):** default-deny — any live refuting evidence blocks promotion until superseded or expired.

## F12 — Spec-gaming: nothing audits evidence-spec sufficiency **[CONFIRMED — SMALL]**

The Decomposer authors children's evidence specs (PAEOS-1 §4); the Adversary's decomposition audit checks intent conservation and seams but **not spec strength**. A throughput-optimizing Decomposer writes weak specs and the whole lattice inflates. **Amendment (A-11):** add spec-sufficiency to the decomposition audit: "construct an implementation that satisfies this spec while violating the parent's intent; if you can, the spec fails."

## F13 — Budget non-conservation: decomposition is a money printer **[CONFIRMED — ARCHITECTURAL]**

**Evidence:** PAEOS-2 §1: spend caps are *"set by the router quadrant"* per goal. Nothing charges children against the parent. A Decomposer splitting one goal into k children mints k fresh quadrant-assigned budgets; recursion makes total spend unbounded. This is one face of a broader hole — **the corpus has physics but no economics**: "verification budget," "queue pressure," and "blocked-work cost" are all load-bearing (PAEOS-2 §§4,7) yet no kernel field represents cost or capacity. **Amendment (A-12):** conservation law — Σ(child budgets) ≤ parent budget − decomposition cost; root budgets are founder-set (the appetite); Evidence records its production cost. Scheduling/priority policy beyond conservation is deferrable to evolution.

## F14 — Amendment oscillation: prune/re-admit cycles have no hysteresis **[CONFIRMED — SMALL]**

Rule fires → incident class vanishes → firing record goes quiet → pruned (I7) → incidents recur → re-admitted → … The firing-record mechanism *causes* the cycle. **Amendment (A-13):** pruning writes a **tombstone**; re-admission of a tombstoned rule requires evidence strictly exceeding the original scar, and the tombstone is itself the hysteresis memory.

## F15 — Classification is not intrinsic: goals change quadrant, and the router never looks again **[CONFIRMED — ARCHITECTURAL, CHEAP FIX]**

**Evidence:** Verifiability is a function of the current check inventory (the Steward's own duty is to migrate classes between quadrants — PAEOS-2 §9), and reversibility decays after integration (Hyrum's law: once users depend on behavior, everything trends irreversible). Yet classification happens once, at dispatch (PAEOS-1 §1.1). A goal correctly routed as reversible can become irreversible mid-flight and finish under Trace-A ceremony.

**Smallest amendment (A-14):** classification **is Evidence** — bound and expiring under I2 like everything else. Quadrant-relevant changes (new dependents, new checks) expire the classification and force re-route. Reuses existing machinery; no new mechanism.

## F16 — Router incompleteness: it decides HOW, nothing decides WHEN **[CONFIRMED — folds into F13]**

Investigation 6 sought a superior basis to verifiability × reversibility. **None was demonstrated** for the ceremony decision — every candidate axis (value, urgency, criticality) governs a *different* decision: priority. The router is correct but the decision surface is incomplete: PAEOS has no scheduling basis at all ("roadmap = an ordering over the Goal tree" is asserted, never derived). Resolved by the economics amendment (A-12) plus an evolution-phase scheduling policy; no router change required.

## Rejected attacks (proof failed)

- **I6 vs founder free-text** (taste exemplars, ground truth): founder inputs enter the store as versioned artifacts and are compiled like anything else. No violation.
- **Steward birth circularity**: resolved by genesis authority + demand paging; the post-ratification self-amendment path routes through Trace-B ceremony including founder Decision (PAEOS-1 §8). No deadlock constructed.
- **Evidence cycles (verdict citing verdict)**: provenance chains make cycles detectable; no self-sustaining cycle that survives A-08/A-10 was constructed. Implementation concern only.
- **Taste-corpus self-reinforcement**: the corpus is founder-curated only (PAEOS-2 §7); no automatic feedback path from system output into the corpus exists in the spec. No defect.
