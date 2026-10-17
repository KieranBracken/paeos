# 05 — Independent Re-derivation (Investigation 13)

Procedure: start from PAEOS-0's six axioms only. Derive an architecture without consulting PAEOS-1. Compare last.

---

## The independent derivation

**From A2 (artifacts durable, context ephemeral):** all coordination must pass through a shared persistent medium; agents cannot coordinate peer-to-peer without creating invisible state. The classical name for this is a **blackboard architecture**: a shared store that specialists read from and post to, with no direct agent-to-agent channels.

**From A1 (generation cheap, verification scarce):** posts to the blackboard are cheap and untrusted; what is expensive is establishing which posts are *true*. Therefore the medium cannot be a pile of assertions — it must be a **truth-maintenance system (TMS)**: every claim carries explicit **justifications** (links to the observations and prior claims it depends on), and when a justification is retracted or its ground changes, belief in the claim is automatically withdrawn. Belief revision is mechanical, not remembered.

**From A6 (unenforced rules decay):** the justification graph must be machine-checked — an untyped blackboard rots.

**From A3 (stance decorrelation):** specialists must be spawnable in opposing stances against the same claim, and a claim believed only on one stance's testimony is weakly believed. Competing specialists posting rival solutions, with selection among them, follows directly.

**From A5 (runtimes churn):** specialists are ephemeral functions of (blackboard state → posts); everything durable lives on the blackboard; the invocation substrate is pluggable.

**From A1 again, second consequence:** cheap generation with scarce verification is a **resource-allocation problem** — the classical blackboard literature calls this the *control problem* and treats it as the hardest part of the architecture. Deciding which knowledge source fires next, and how much scarce verification to spend where, requires an explicit **control/economics layer**: budgets, bids, or priorities attached to pending work. (Agoric-systems lineage: computation as a market for scarce resources.)

**From A4:** one external oracle injects goals, preferences, and world-truth the system cannot generate; its bandwidth is the scarcest resource of all, so the control layer must price it highest.

Independent result: **a typed blackboard + justification-based truth maintenance + pattern-triggered ephemeral specialists in opposing stances + an explicit control/economics layer + one human oracle.**

## Comparison

| Independent derivation | PAEOS-1 | Verdict |
|---|---|---|
| Typed blackboard | Typed append-only artifact store | **Same abstraction** |
| TMS claims + justifications | Evidence + hash bindings + expiry (I2) | **Same abstraction — but the independent form is superior in one respect (below)** |
| Belief revision on retraction | Status regression on expiry | Same |
| Pattern-triggered specialists | Demand-paged roles / compiled contexts | Same |
| Opposing stances, weak single-stance belief | I3 / A3 stance diversity | Same — and the TMS framing independently demands what A-08 adds (discounting correlated testimony) |
| Competing posts + selection | Tournaments + Judge | Same |
| Control/economics layer | **Absent** (spend caps mentioned, unmodeled) | **Independent derivation superior — confirms F13/F16** |
| Justification *graph* (claim→claim dependencies) | Hash binding to content state | **Independent superior — fine-grained invalidation; confirms A-07 as the fix for F8** |
| — | Constitutional evolution loop (scars, amendments, pruning) | **PAEOS superior — blackboard tradition never solved learning; this is PAEOS's genuine novelty** |
| — | Verifiability × reversibility ceremony router | **PAEOS superior — the control literature allocates effort but never derived a ceremony basis** |
| — | Narrow-waist portability contract + conformance | **PAEOS superior** |
| — | Founder ABI as four typed channels + decay theorem | **PAEOS superior** |

## Findings

1. **Convergence on the skeleton.** Working forward from the axioms alone, without the corpus, reproduces PAEOS-1's core: store, evidence-with-expiry, ephemeral stanced agents, tournaments. Two derivations reaching the same skeleton by different paths is the strongest available evidence that the skeleton is forced by the axioms rather than invented. This finding is the review's principal argument **for** ratification.
2. **The two divergences are exactly the review's two largest holes.** The independent path makes first-class what PAEOS left implicit: (a) justification graphs — which is precisely the A-07 fix for the F8 livelock (bind evidence to declared dependencies, invalidate along edges, not by global hash overlap); (b) the control/economics layer — which is precisely F13/F16. That the independent derivation and the adversarial attacks located the *same* two gaps by different methods elevates both from "findings" to "certainties."
3. **PAEOS's additions above the classical skeleton are real contributions, not decoration.** The evolution loop (scar-gated, falsifiable, prunable policy), the ceremony router, the narrow waist, and the founder ABI have no precedent in the blackboard/TMS lineage and survive attack. They are the parts to protect.

**Conclusion:** both architectures collapse into the same abstraction; where they differ, adopt the independent derivation's evidence model (justification graph) and its demand for an explicit economics layer, and retain PAEOS's four novel superstructures unchanged.
