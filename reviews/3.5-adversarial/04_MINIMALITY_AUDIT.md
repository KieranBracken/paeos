# 04 — Minimality Audit (Investigation 15)

Compression is evidence of understanding. Results: **6 primitives → 4. 12 invariants → 10 axioms + 2 theorems. 7 roles → 3 stances × 4 domains. 4 syscalls → 3 primitive + 1 optimization.**

---

## Primitives: 6 → 4

Per F2/F3 (see 01): Incident, Decision, Amendment retype as Goal subtypes; the untyped work product becomes the explicit base type.

**Final ontology: Artifact (base), Goal (kinds: work | incident | decision | amendment), Evidence, Policy (kinds: constitution | protocol | skill | role).**

Net honest accounting: the review *removed* three primitives and *added* one the spec was silently using. Four is likely the floor: Goal cannot absorb Evidence (one reconciles, one is a record — F1's category split), and Policy cannot be a Goal (policies persist and load; goals terminate).

## Invariants: 12 → 10 (+2 theorems)

- **I5 (crash-only agents) is a theorem, not an axiom.** Proof: I4 (all state is append-only artifacts) + I6 (contexts are compiled deterministically from artifacts) ⟹ any killed agent's successor recompiles the same context from the same store and continues. Nothing about restartability needs independent assertion. Keep it in the text as a *derived guarantee* — it is the property users care about — but PAEOS-4 should mark it derived, because derived rules are free (they cost no enforcement machinery).
- **I10 (constraint monotonicity) is derivable** from A4 + I8: loosening an inherited constraint reverses a founder commitment; reversing founder judgment is A4-channel-4 territory, which is precisely what a Decision (founder-assigned goal, post-F2) is for. Mark as candidate theorem; keep the explicit statement only because the validator needs a named check.
- The remaining ten (with F-series amendments applied: I1+A-09/A-10, I2+A-07, I3′=A-08, I7+A-18 below, plus the new conservation law A-12) are pairwise non-derivable — each removal was tested by constructing the failure it would permit, and all ten constructions succeeded. The set is tight.
- **One addition the audit endorses despite the compression mandate:** A-12 (budget conservation) enters as a new invariant. A minimality audit that refuses a demonstrated missing conservation law is optimizing for count, not for truth.

## Roles: 7 → 3 × 4

Per F4's table: {Generate, Falsify, Select} × {work, goal-structure, policy, trunk}. The seven names survive as conventional bindings; the kernel schema stores (stance, domain). This also *fills four cells the corpus assigned ad hoc or left empty* — e.g., Falsify×Policy (the pruning pass) becomes a first-class role binding instead of a Steward moonlighting duty.

## Syscalls: 4 → 3 + 1

SPAWN is theoretically reducible: SPAWN(role, context) ≡ EXEC(null-adapter, compiled-context) — PAEOS-3's degraded mode says as much. The audit recommends **keeping SPAWN in the contract** as the one permitted optimization point (native runtimes implement it with real concurrency and isolation, per H7/A-16), while recording its EXEC-reducibility as the *proof that the waist is minimal*: three irreducible capabilities (read, append, execute), one derived convenience.

## The Constitution, compressed as demonstration

The audit's requirement was to show the kernel survives compression without expressive loss. The ten-axiom constitution in ~120 words:

> A goal's status changes only on evidence (I1). Evidence binds to the read-set it observed and expires when that changes (I2′). Non-mechanical verification must be provenance-decorrelated from generation (I3′). History is append-only (I4). Agents act only on contexts compiled deterministically from the explicit link graph (I6′). No policy without a scar and falsifier; unfired policy is pruned to a tombstone (I7′). Founder-assigned goals terminate in policy or a recorded exception (I8). One integrator per trunk (I9). The kernel assumes only read, append, execute (I11′). The kernel has a size cap (I12). Budgets conserve under decomposition (I13-new). Derived guarantees: crash-only agents; constraint monotonicity.

Nothing in PAEOS-1/2/3's behavior is lost under this statement plus the four-object ontology. Compression succeeded, which is the strongest internal evidence that the underlying design is understood rather than accreted.
