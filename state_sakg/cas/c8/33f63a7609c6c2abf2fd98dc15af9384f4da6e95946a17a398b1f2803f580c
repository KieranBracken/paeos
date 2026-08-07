# 03 — Hidden Assumptions (Investigations 3, 7, 8, 14)

Each entry: the assumption / where it hides / essential vs accidental / required action.

---

## H1 — Single founder **[ESSENTIAL — MUST BECOME EXPLICIT]**

A4 says "the founder," singular, everywhere. The Decision queue has one resolver; the taste corpus has one curator; constraint loosening has one authority. Two founders with divergent taste break Judge semantics silently (whose exemplar wins?) and Decision semantics loudly. This is fine — but it is a **constitutional assumption**, not a derived fact, and the corpus never states it. Multi-founder PAEOS requires a governance layer the derivation never attempted. **Action:** add to the genesis record: "PAEOS assumes a singular intent source; plurality of founders is out of scope and voids the A4 derivations."

## H2 — The founder is Leviathan; PAEOS is parchment **[INHERENT LIMIT — MUST BECOME EXPLICIT]**

Investigation 3's deepest result. The clean-intent invariant declares founder direct edits to be Incidents; the validator can detect them (commit provenance); but the founder owns the machine, the store, and the validator. **No self-imposed constitution binds a sovereign who hosts it.** Every enforcement mechanism in the corpus is ultimately founder-revocable. This is not a defect unique to PAEOS — it is the condition of all constitutions — but the corpus's language ("forbidden," "mechanically enforced") obscures that against the founder, enforcement is *detection plus convention*, nothing more. **Action:** state it in the Constitution's preamble. A system honest about scars must be honest about this one waiting to happen.

## H3 — Founder removal is conditional, and one sentence overclaims **[OVERCLAIM — RHETORICAL, ONE-LINE FIX]**

Investigation 7. The corpus is internally consistent: PAEOS never claims the founder disappears — A4 makes intent and ground truth constitutionally permanent, and PAEOS-2 §5 states the decay theorem *"for a stationary problem domain."* But PAEOS-2's one-sentence version says the founder's role *"converges by construction"* — dropping the stationarity condition. Taste is high-dimensional and non-stationary; every new aesthetic territory re-opens starvation. Also confirmed hidden labor: **nothing audits the root Goal** — intent conservation checks children against parents, but the root has no parent; garbage intent flows unchallenged into a perfectly governed tree. **Action:** restore the stationarity caveat; add root-goal ceremony (A-15 in 06): Trace-B adversarial interrogation of every root Goal before decomposition — the founder still decides, but the system must challenge.

## H4 — Content-hashing and append-only history are constitutional; git is not **[ACCIDENTAL/ESSENTIAL SPLIT — MUST BE SEPARATED]**

PAEOS-3 says "the store is git"; PAEOS-1's kernel needs only: content-addressing (Evidence bindings, I2), append-only history (I4), and named refs (Trunk, per F3). Git is one adapter-level realization. The corpus blurs this repeatedly. **Action:** kernel declares the three store properties; git moves explicitly to the reference adapter.

## H5 — Natural language as the policy encoding **[ESSENTIAL FOR NOW — MUST BECOME EXPLICIT WITH FALSIFIER]**

Every Policy is markdown prose compiled into model contexts. Hidden assumption: **the executing intelligence's native instruction format is natural language.** True for current LLMs; not a law of nature. **Action:** constitutional assumption with falsifier: "Policies are expressed in the lingua franca of the executing models; if model families diverge from NL instruction-following, the Compiler's lowering step absorbs the change" — which the narrow waist already permits (context-lowering is an adapter duty).

## H6 — Token scarcity is the scar behind I12 **[ESSENTIAL — RECORD THE FALSIFIER]**

The kernel size cap is derived from "every line taxes every prompt" (PAEOS-0 M5). If context becomes effectively free, I12's stated justification collapses, though weaker ones (attention dilution, drift) remain. The corpus requires every invariant to carry a falsifier (I7) — I12's is precisely "context economics change." **Action:** record it; no structural change.

## H7 — SPAWN degradation is NOT semantically identical **[CONFIRMED DEFECT — CONTRACT FIX]**

PAEOS-1 §6 / PAEOS-3 §5 claim sequential self-invocation is "slower, semantically identical." False in one load-bearing case: **tournaments.** Parallel candidates are isolated by concurrency; sequential candidates can READ predecessors' speculated artifacts in the store, destroying the decorrelation that justifies the tournament (A3). The degraded mode silently converts best-of-N into a Markov chain of anchored attempts. **Action (A-16):** the SPAWN contract must include **speculation-branch isolation**; sequential emulation must isolate via branches. This is a conformance-test item, not just guidance.

## H8 — Model heterogeneity is assumed available **[RUNTIME-DEPENDENT — PARAMETERIZE]**

A-08 (provenance-decorrelated verification) requires a second model family; Claude Code without external API keys, or an enterprise-locked runtime, may not offer one. Portability survives only if the invariant is parameterized by adapter-declared diversity (as A-08 specifies). Noted so PAEOS-6 adapters must declare it.

## H9 — Founder availability **[ACCEPTED — FAILS SAFE]**

The Decision queue assumes the founder returns. Founder absence freezes exactly the irreversible+unverifiable quadrant and nothing else — the system degrades to autonomous Trace-A work indefinitely. This is correct behavior (fail-safe on the axis that needs accountability). No action beyond documentation.

## H10 — Single-instance, single-tenant store **[CONFIRMED GAP — ARCHITECTURAL]**

Investigation 8's largest find, and it contradicts the stated roadmap. The corpus derives one store, one trunk-family, one constitution. The roadmap (PAEOS as OS for Sentium, Orca-strator, Inspiration Engine, …) is **multi-tenant** — and the corpus is silent on whether Sentium's Incidents amend the constitution that governs Orca-strator. Both defaults fail: full sharing pollutes tenants with each other's scars; full isolation forfeits transfer learning, which is half the point of a portable OS. **Action (A-17):** policy namespaces — `scope ∈ {kernel, workload:<name>}` on every Policy, with a promotion protocol: a workload-local rule is eligible for kernel scope when independently scarred in ≥2 tenants. Schema-level; must precede PAEOS-4.

## Assumptions examined and found genuinely essential (no action)

- **Filesystem + shell (READ/WRITE/EXEC):** the narrow waist already reduces these to minimal contracts; any runtime that cannot offer file-and-exec equivalents cannot host an engineering OS at all.
- **LLM nondeterminism:** tournaments exploit output variance; if future models become deterministic-and-correct, tournament machinery idles gracefully (N=1 is a degenerate tournament). No invariant breaks.
- **Directories/markdown:** presentation-level; the schemas (PAEOS-4) are the real contract.
- **Linear time:** reconciliation is order-insensitive by design (crash-only); no hidden dependence found beyond append-only ordering, which H4 makes explicit.
