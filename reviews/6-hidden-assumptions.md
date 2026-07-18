# PAEOS — Hidden Assumption Register ("Axiom Archaeology")

Scope: PAEOS-0..4 frozen and assumed correct. Inclusion criterion: an assumption enters
this register ONLY if its falsity invalidates part of the derivation. Cosmetics,
alternatives, terminology: excluded. Assumptions already catalogued (H1–H10, SC-*) are
excluded unless a strictly deeper layer exists beneath them.

Method: (§A) independent re-derivations from foreign first principles, diffing their
*forced dependency graphs* against PAEOS's — anything a foreign derivation is forced to
state that PAEOS never states is a candidate hidden premise; (§B) categorical sweep;
(§C) the self-referential (Gödelian) layer.

**Register history:** Pass 1 (Ω-01..18): control theory, distributed consensus,
epistemology. Pass 2 at maximum effort (Ω-19..27): four further bases — mechanism
design, evolutionary biology, information theory, organization theory — chosen because
each is forced to state a premise none of the first three were, plus a sweep of the two
under-mined categories (logical decidability, temporal envelopes). Pass-2 inclusion bar
unchanged and applied per-entry: name the derivation step (document + section) that
falsity invalidates, dedup against Ω-01..18 / H1–H10 / SC-01..24 / 3.5 / 5.5 findings.

---

## §A The comparative derivations

### A.1 Control-theoretic derivation
Model PAEOS as: plant (codebase/world) + controller (agents) + reference (intent) +
sensors (evidence) + feedback (lattice). A control derivation CANNOT proceed without
stating: sensor noise model, actuator error, loop delay, stability margins. PAEOS states
none of them. Diff yields Ω-01, Ω-02 (via sensor-fault ambiguity), and the general form
of the 3.5-F8 livelock (which was one instance of an unstated delay-margin analysis).

### A.2 Distributed-consensus derivation
Model PAEOS as: unreliable computing agents agreeing on shared state. This derivation is
forced to state a fault model for EVERY component — including the machinery that checks
the others. PAEOS assigns fault models to agents (untrusted) and adapters (trusted-but-
verified) but silently assigns the kernel binary itself a fault probability of zero.
Diff yields Ω-13.

### A.3 Epistemological derivation (Popper/Duhem/Quine)
PAEOS is mechanized falsificationism. The philosophy of science's hard-won caveats are
exactly the assumptions PAEOS inherited without stating: theory-ladenness of observation
(Ω-03), holism of refutation (Ω-02), the demarcation of what observations mean across
paradigm shifts (Ω-17).

### Diff table (what foreign derivations force vs what PAEOS states)

| Forced by | Premise | Stated in PAEOS? |
|---|---|---|
| Control | sensor noise model | **NO** → Ω-01 |
| Control | loop delay / stability margin | partially (F8 fix was one instance) |
| Control | actuator (agent) error model | yes (A3, untrusted agents) |
| Distributed | fault model for the checker itself | **NO** → Ω-13 |
| Distributed | membership/attestation | genesis trust roots only (adapters, not kernel) |
| Epistemology | observation is theory-laden | **NO** → Ω-03 |
| Epistemology | refutation is holistic, not local | **NO** → Ω-02 |
| Epistemology | meaning stability across paradigms | **NO** → Ω-17 |

### A.4 Mechanism-design derivation (pass 2)
Model PAEOS as: a market of policies competing for survival under a measured objective.
This derivation CANNOT proceed without stating whether the objective is
incentive-compatible under optimization pressure — Goodhart's condition. PAEOS never
states it. The evolution loop is an optimizer over the evidence regime; mechanism design
forces the question "what happens to a proxy when you select on it?" Diff yields Ω-19,
and retroactively sharpens Ω-11 (see cross-note there).

### A.5 Evolutionary-biology derivation (pass 2)
Model PAEOS as: a population of heritable units (policies) under selection (evidence)
with replication (versioning). Biology is forced to state three things PAEOS never does:
whether selection is ergodic (path-independence of outcomes), whether fitness is
exogenous (frequency-independence), and whether credit is assignable to units
(decomposable fitness). Diff yields Ω-20 and Ω-21.

### A.6 Information-theoretic derivation (pass 2)
Model PAEOS as: channels moving intent downward and truth upward through a lossy medium
(artifacts). Information theory is forced to state channel capacities and whether the
recorded signal is a sufficient statistic for the source. PAEOS states neither for its
most loaded channel — the founder — nor for its central medium claim ("everything
load-bearing is a file"). Diff yields Ω-22 and Ω-23.

### A.7 Organization-theory derivation (pass 2)
Model PAEOS as: a producing organization whose communication structure is the goal tree.
Conway's law forces: the produced artifact mirrors the producing structure, whether or
not that structure was chosen for the artifact's benefit. PAEOS chose its decomposition
criterion for verification economics and never asked what shape that stamps on the
product. Diff yields Ω-24.

### Diff table, pass 2

| Forced by | Premise | Stated in PAEOS? |
|---|---|---|
| Mechanism design | proxy incentive-compatibility under selection | **NO** → Ω-19 |
| Evolutionary biology | ergodicity of learning (order-independence) | **NO** → Ω-20 |
| Evolutionary biology | fitness exogeneity / decomposable credit | **NO** → Ω-21 |
| Information theory | founder-channel capacity vs demand | **NO** → Ω-22 |
| Information theory | artifacts as sufficient statistic for rationale | **NO** → Ω-23 |
| Organization theory | product structure mirrors process structure | **NO** → Ω-24 |
| Logic sweep | all goals verifiable in principle | **NO** → Ω-25 |
| Temporal sweep | domain volatility below loop bandwidth | **NO** → Ω-26 |
| Legal sweep | one-offs remain rare and non-load-bearing | **NO** → Ω-27 |

---

## §B The register

Format: statement · where it hides · what breaks if false · disposition
(EXPLICIT = promote to stated constitutional assumption with falsifier;
MECHANISM = a cheap mechanical guard exists; LIMIT = irreducible, state in preamble).

### Ω-01 — Evidence channels are noiseless **[most operationally severe]**
- **Hides in:** K1/§8 truth model — evidence is boolean supports/refutes with no error
  rate; default-deny treats any refutation as true refutation. The entire corpus contains
  no concept of a *flaky check*.
- **If false (it is false — flaky tests are the most common verification pathology in
  existence):** spurious refutation blocks promotion indefinitely (default-deny);
  spurious support promotes wrongly; expiry+re-verify under noise produces stochastic
  thrash the F8 analysis never modeled, because F8 assumed deterministic invalidation.
  K1's guarantee — the kernel's last line of defense — silently assumes P(false
  evidence)≈0 for execution-class evidence.
- **Disposition:** EXPLICIT + MECHANISM (evidence needs a repeatability semantic before
  the truth model is well-defined; the derivation's correctness claims are conditional
  on a noise bound that must be stated).

### Ω-02 — Refutation localizes blame (Duhem–Quine violation)
- **Hides in:** Evidence.claim binding — refuting evidence attaches to the claim it
  names. When a check fails, the derivation assumes the *artifact* is wrong, never the
  check, the environment, the fixture, or the claim's phrasing.
- **If false:** K1 default-deny blocks the wrong object; incident mining mis-attributes
  scars; policies grow from misdiagnosed failures — the evolution loop learns wrong
  lessons with full constitutional legitimacy.
- **Disposition:** LIMIT (holism is irreducible) + MECHANISM (refutation should be
  contestable — currently only supersession by new evidence exists, which presumes
  someone notices).

### Ω-03 — A shared interpretation function exists for natural-language claims
- **Hides in:** every evidence_spec, every delta, every claim. The lattice treats NL
  claims as stable propositions with determinate extensions. Deeper layer beneath H5
  (which covered policy *encoding*, not claim *semantics*).
- **If false:** "satisfying evidence" is relative to the reader-model's interpretation;
  two conformant kernels with different models disagree on whether the same evidence
  satisfies the same spec — semantic non-portability beneath the byte-identical
  manifests §6.1 so carefully pinned.
- **Disposition:** EXPLICIT. The real portability boundary is the interpretation
  function, and it lives in the models, not the kernel.

### Ω-04 — Verification is compositional
- **Hides in:** AggregationContract — parent truth = f(children's evidence). The
  decomposition criterion ("distribute verifiability") assumes every goal admits
  decomposition into independently evidencable leaves whose verification *composes*.
- **If false:** emergent properties — end-to-end performance, security-of-the-whole,
  UX coherence, architectural integrity itself — are precisely non-compositional; the
  goal tree systematically under-verifies the properties PAEOS-0 promised to maximize.
  The corpus's own answer (Trace-B ceremony at high-fanout nodes) governs *decisions*,
  not *emergent outcomes*.
- **Disposition:** EXPLICIT + MECHANISM (whole-system evidence must attach to non-leaf
  goals; the schema permits it — the derivation never required it).

### Ω-05 — All evidence decay is state-correlated
- **Hides in:** K2 — expiry fires ONLY on read-set (store-state) change. External-class
  evidence binds to store objects, not to the world it describes.
- **If false (it is):** market/user/dependency truths never expire mechanically; a goal
  verified on external evidence stays verified while the world moves. The store is
  assumed to be a sufficient statistic for reality.
- **Disposition:** MECHANISM (temporal validity on external-class evidence) — but the
  assumption must be stated because §8's authority ordering ranks external evidence
  HIGHEST while giving it the WEAKEST expiry.

### Ω-06 — The inference substrate is stationary
- **Hides in:** the entire evolution loop. Tournaments, firing records, falsifier
  watches, and skill-version comparisons attribute outcome deltas to policy/context
  deltas. Hosted models drift silently under fixed names.
- **If false (it is):** the system's comparative epistemology is confounded — a skill
  "wins" because the model changed; a falsifier "fires" because inference shifted;
  constitutional amendments ratify noise. The learning loop's validity assumes a fixed
  reference intelligence that does not exist.
- **Disposition:** EXPLICIT + MECHANISM (provenance already records model family; no
  invariant conditions comparative conclusions on matched provenance — the F9 pattern
  again: the field exists, nothing consumes it).
- **Pass-2 sharpening (via Ω-21):** stationarity fails even with a frozen model — the
  store itself is a moving environment (skills, exemplars, protocols shift the context
  every policy is evaluated in). Substrate drift (Ω-06) and population drift (Ω-21) are
  two independent confounds on the same attribution logic.

### Ω-07 — Stance/model decorrelation is achievable (A3 is empirical, not axiomatic)
- **Hides in:** A3 → K3. Treated as an axiom; it is a measurable hypothesis. Cross-family
  models share training corpora, RLHF conventions, and failure modes.
- **If false in degree:** K3 buys less than derived; tournament fan-out N is mis-priced;
  adversarial pairs give correlated absolution. The one axiom never given a falsifier.
- **Disposition:** EXPLICIT + falsifier (measure agreement-on-error rates across the
  adapter's declared families; K3's value is that number, not a constant).

### Ω-08 — A1's cost asymmetry is permanent and uniform
- **Hides in:** the router itself. Verification-scarce/generation-cheap sets the entire
  ceremony economy. K10 got a falsifier (H6); the router's foundation did not.
- **If false (cheap formal verification, expensive generation, per-domain inversion):**
  quadrant ceremony allocations invert; the matrix survives but every protocol binding
  is wrong.
- **Disposition:** EXPLICIT + falsifier on A1 itself.

### Ω-09 — Budget dimensions are orthogonal and non-fungible
- **Hides in:** §10 per-dimension conservation. Reality trades tokens for wall-clock for
  founder-decisions continuously.
- **If false:** conservation per-dimension either blocks rational trades or is routed
  around informally (unaccounted fungibility = invisible economics).
- **Disposition:** EXPLICIT (declare non-fungibility a deliberate simplification with
  its failure signature: chronic single-dimension exhaustion incidents).

### Ω-10 — All costs are goal-attributable
- **Hides in:** Evidence.cost / K11. Reactor overhead, index rebuilds, cache warmth,
  liveness recomputation belong to no goal.
- **If false (it is):** conservation governs a shrinking fraction of real spend as the
  system grows; the economics the founder sees are systematically understated.
- **Disposition:** EXPLICIT (a system-overhead ledger outside K11, or K11 governs only
  marginal cost — say which).

### Ω-11 — Failures are observable (scars are felt)
- **Hides in:** the entire failure-driven method (PAEOS-0 M2). Incidents exist only when
  something *notices*. Latent defects passing weak evidence specs generate no signal
  until external eruption — whose reporting depends on founder Inject bandwidth.
- **If false:** the evolution loop is complete only over the *visible* failure
  distribution; the invisible distribution — the dangerous one — never teaches.
- **Disposition:** EXPLICIT + LIMIT (Ω-11 is why A-11 spec-sufficiency audits and Ω-04
  whole-system evidence matter more than their small size suggests).
- **Pass-2 sharpening (via Ω-19):** worse than passive blindness — selection *actively
  migrates* failure into the unobservable region. Policies that fail visibly get pruned;
  policies that fail invisibly survive and reproduce. Under sustained evolution the
  system does not merely miss latent failure modes; it **evolves toward them**.

### Ω-12 — Founder taste is a coherent partial order
- **Hides in:** Judge resolution against the taste corpus. Contradictory exemplars
  (humans drift, moods vary, contexts differ) give Judges undefined behavior — no
  conflict rule exists for taste (A-10 covered evidence, not exemplars).
- **Disposition:** MECHANISM (exemplar conflicts are detectable; surface as Curate-verb
  feedback) + EXPLICIT.

### Ω-13 — The kernel binary is non-Byzantine
- **Hides in:** everything. Validator, reactor, compiler, syscalls are assumed to
  execute their spec faithfully. Genesis attests the *spec* hashes; nothing attests the
  *implementation*. Conformance tests run through the binary they test (Thompson's
  Trusting-Trust, unaddressed at the binary level — the reproducible-constitution audit
  covers rules, not code).
- **If false:** every guarantee in the corpus is void simultaneously.
- **Disposition:** EXPLICIT + MECHANISM (reproducible builds + implementation hash in
  the genesis record + cross-implementation differential conformance — the null adapter
  was already the seed of this; two independent kernels checking each other is the real
  defense).

### Ω-14 — Self-certification limit (the Gödelian core)
- **Hides in:** the closed loop of self-hosting. Evidence soundness is judged by
  machinery whose soundness is judged by the same machinery. The system cannot prove its
  own evaluation layer sound from inside. The designated external oracle is the founder —
  but PAEOS-2 §5's decay theorem *deliberately atrophies* founder involvement. The
  soundness anchor and the minimize-intervention objective are in structural tension
  that no document states.
- **If unacknowledged:** a corrupted evaluation regime ratifies itself indefinitely;
  every internal audit — including the reproducible-constitution test — runs under the
  corrupted regime.
- **Disposition:** LIMIT — must be stated in the constitutional preamble: *the founder's
  periodic soundness audit is not an inefficiency to be optimized away; it is the
  system's Gödel escape hatch, and the decay theorem explicitly does not apply to it.*

### Ω-15 — Entrenchment is completely specified (it is not)
- **Hides in:** §14.5's frozen-surface list vs §9.4. Amendments can amend the amendment
  machinery. Whether amendment-lifecycle semantics (provisional, revert, falsifier
  arming) are a "frozen surface" is not stated — a legal ordinary amendment could soften
  the very probation that makes amendments safe.
- **Disposition:** MECHANISM (one sentence: §3.4, §9.4, and §13 are §14.5 surfaces).

### Ω-16 — Justification graphs are well-founded
- **Hides in:** K2 transitive liveness. Nothing forbids basis cycles; liveness recursion
  over a cycle is undefined.
- **Disposition:** MECHANISM (validator acyclicity check — trivial, missing).

### Ω-17 — Intent semantics are stable across model generations
- **Hides in:** the ten-year story. Year-1 root goals interpreted by year-6 models under
  year-6 policies. The intent-conservation audit checks structural citation (clause
  refs), not semantic fidelity. Structure survives; meaning drifts.
- **Disposition:** EXPLICIT + MECHANISM-lite (periodic founder re-ratification of live
  root goals — an Inject-channel act, cheap, currently nowhere required).

### Ω-18 — A minimum model-capability floor exists
- **Hides in:** every role body. Conformance certifies *adapters*; no test certifies
  that a given *model* meets the floor (schema-valid output, stance adherence, evidence
  reasoning). A weak model fails inside the contracts, not against them.
- **Disposition:** MECHANISM (a model-floor probe suite run per (adapter, model family),
  results into capabilities()).

---

## §B.2 Pass-2 entries

### Ω-19 — Selection metrics stay aligned under selection pressure (Goodhart) **[corrupts learning, no malice required]**
- **Hides in:** PAEOS-0 M6/M7 (tournament evolution, prune-what-doesn't-pay), PAEOS-1 §8
  evolution loop, K6 firing records, §9.5 pruning. The loop *selects* policies by
  evidence-measured outcomes and the derivation assumes selected-because-measured-better
  ⟹ actually-better.
- **If false (Goodhart's law says it is, under sustained pressure):** the policy
  population drifts toward whatever the evidence regime rewards — no agent games
  anything; survival *is* the optimizer. Invalidates PAEOS-0 M6's convergence claim and
  PAEOS-2 §9's maturation curve: a system "cooling" as scars accumulate is
  observationally indistinguishable from a system that has finished optimizing its own
  metrics. Distinct from A10 (one compromised agent gaming a spec) and from Ω-11's base
  form (passive blindness): this is systemic, honest, and emergent.
- **Disposition:** LIMIT + MECHANISM. The only non-Goodhartable signal in the
  architecture is founder-injected external evidence (§8 ranks it highest — correctly,
  it turns out, for a reason the corpus never gives). Defense is metric refresh:
  evidence regimes must themselves face periodic adversarial rotation, and the founder
  ground-truth channel must never be fully substituted by internal proxies. Note where
  this lands: on the founder channel, again (see §C synthesis).

### Ω-20 — Learning is order-independent (ergodicity of scar-derivation)
- **Hides in:** PAEOS-0 M2 (failure-driven derivation), K6, PAEOS-3 §1 (scar corpus
  seeds the constitution). The derivation treats the scar-derived constitution as *the*
  justified rule-set — implicitly assuming the same rules emerge regardless of the order
  incidents arrive.
- **If false (it is — early rules change behavior, which changes which later failures
  can even occur):** the constitution is one sample from a path-dependent distribution
  of possible constitutions, with no detector for having landed in a bad basin. The
  reproducible-constitution audit (PAEOS-3 §4) is weaker than believed: re-deriving from
  the same corpus replays the same path — it checks internal consistency, not basin
  quality.
- **Disposition:** EXPLICIT + LIMIT. Basin escape requires exogenous perturbation — and
  A-18's vicarious scars are, unnoticed by their own derivation, exactly that mechanism:
  importing other systems' incidents samples other paths. A-18 acquires a second,
  stronger justification here.

### Ω-21 — Policy fitness is intrinsic (frequency-independence, decomposable credit)
- **Hides in:** K6 firing records and §9.5 pruning (per-policy metrics), tournament
  verdicts (§9.3). Each policy's value is measured as if independent of the policy
  population it runs inside.
- **If false (it is — skills preempt, complement, and mask one another):** quiet firing
  records misread co-dependence: skill A never fires *because* B preempts it; prune B
  and A becomes load-bearing. Tournament outcomes are context-relative and
  non-transitive across policy-population changes. Invalidates §9.5's pruning semantics
  and the comparability assumption under every firing-record decision.
- **Disposition:** EXPLICIT + MECHANISM — prunes should be probationary, exactly as
  amendments already are (A-06 machinery, reused): tombstone provisionally, watch for
  displaced-failure incidents, finalize or revert. Existing machinery, unapplied.

### Ω-22 — Founder-channel capacity exceeds system demand at all scales
- **Hides in:** PAEOS-2 §5/§7 (decay theorem, five-verb equilibrium), K7, A4. The
  derivation bounds founder interventions *per class* (decay) but never compares
  aggregate demand (decisions + taste + ground truth + root ratification, scaling with
  goal-tree breadth and tenant count) against a constant-capacity human channel.
- **If false at scale (multi-workload roadmap multiplies demand against one founder):**
  the failure is not loud queue-blockage but silent starvation — Judges proceed on stale
  taste, external evidence ages (Ω-05 compounds), and quality drifts without a single
  alarm. Invalidates PAEOS-2 §7's claim that the equilibrium is stable as the system
  grows.
- **Disposition:** EXPLICIT — state the operating envelope. The meter already exists:
  the `decisions` budget dimension (K4 §10) is, unnoticed, a founder-bandwidth gauge;
  chronic exhaustion is the overdemand alarm.
- **Dedup:** H9 was availability (binary); Ω-14 is channel *quality* (soundness); this
  is channel *rate*. Three distinct layers of the same component — see §C synthesis.

### Ω-23 — The load-bearing part of thinking is writable
- **Hides in:** A2/P2 ("everything load-bearing is a file"), K4/K5, D1's "zero loss"
  claim. The derivation assumes artifacts can be a sufficient statistic for the
  reasoning that produced them.
- **If false (tacit knowledge — unarticulated design intuition, negative results never
  written, the search path behind a conclusion — resists serialization):** D1's
  crash-only guarantee holds only for recorded state; in-flight reasoning of a killed
  agent is lost, and the derivation *defines this loss as zero* rather than measuring
  it. Repeated crash/restart and every cold agent-spawn pay a hidden re-derivation tax.
  Invalidates the strong reading of D1 and the epistemic completeness claim of
  PAEOS-1 §0 ("nothing else exists").
- **Disposition:** EXPLICIT + note: the tax is partially budget-visible (re-derivation
  burns tokens), so the meter exists even though the loss is unnamed.

### Ω-24 — Verification seams coincide with good product architecture (Conway)
- **Hides in:** PAEOS-2 §6 ("concentrate irreversibility, distribute verifiability"),
  and PAEOS-4.5 §13, which *celebrates* the isomorphism ("the implementation plan and
  the bootstrap goal tree are the same object") without noticing it is Conway's law
  operating on PAEOS itself.
- **If false (cross-cutting concerns — security, performance, observability — famously
  do not decompose along testable seams):** the produced systems are shaped like their
  audit trails: optimized for evidencability, not runtime quality — directly against
  PAEOS-0's stated objective of maximal architectural quality. The one assumption in
  this register that attacks the mission statement itself.
- **Disposition:** EXPLICIT + MECHANISM-lite: the (F,GOALSTRUCT) decomposition audit
  gains one question — "is this seam a good product boundary, or only a good audit
  boundary?" Related to Ω-04 but distinct in causal direction: Ω-04 says wholes are
  under-*verified*; Ω-24 says wholes are mis-*shaped*.

### Ω-25 — Every goal is verifiable in principle (Popper asymmetry in the lattice)
- **Hides in:** K1 / §3.2 (`verified` = evidence spec fully satisfied by live evidence);
  EvidenceReq's finite `min_count` semantics.
- **If false (safety and absence properties — "never leaks PII", "no regression
  anywhere" — are universally quantified, hence falsifiable-only):** such goals can
  never legally reach `verified` by finite observation. In practice authors substitute
  bounded proxies ("passes suite S"), and the lattice then treats bounded evidence as
  discharging an unbounded intent — **the intent–spec gap is where every Ω-11 latent
  failure lives, and the kernel neither names nor tracks it.** Invalidates §3.2's
  implicit completeness over goal-space: `verified` means "bounded spec satisfied,"
  never "universal intent proven," and no document says so.
- **Disposition:** EXPLICIT (the strongest of the pass-2 sweep): state the reading of
  `verified` and name the gap as a standing, unmonitored quantity that A-11 audits
  should size.

### Ω-26 — Domain volatility is below loop bandwidth (sampling envelope)
- **Hides in:** the reconciliation model itself; K2 expiry assumes re-verification can
  complete between relevant world changes. F8's analysis bounded *internal* invalidation
  (λp ≥ μ); no bound was ever stated for *external* change rate vs loop latency.
- **If false (domains faster than the loop — volatile markets, churning APIs):**
  perpetual regression; `integrated` stability is unreachable; the system is a filter
  asked to track a signal above its Nyquist rate. Complementary to Ω-05: Ω-05 says
  external change goes *undetected*; Ω-26 says even when detected, too-fast change
  prevents convergence. Two sides of one unstated operating envelope.
- **Disposition:** EXPLICIT — PAEOS is valid for domains whose relevant change rate is
  below its re-verification bandwidth; say so.

### Ω-27 — One-off records remain rare and non-load-bearing
- **Hides in:** K7's escape clause ("amendment OR explicit one-off record"). The decay
  theorem (PAEOS-2 §5) depends on interventions closing their class; the one-off is the
  *legal* path that closes nothing.
- **If false (one-offs are cheaper than amendments, so pressure flows toward them):**
  a shadow common law accretes — and worse, one-offs are not Policy, so they never load
  into compiled contexts: precedent exists in the record but does not govern behavior.
  Heavy one-off use voids the decay theorem while satisfying K7 to the letter.
- **Disposition:** MECHANISM (cheap, existing machinery): Steward audits one-off rate
  per class; recurrence of "one-offs" of a kind is mechanically an incident.

---

## §C Ranking by invalidation blast radius (both passes)

1. **Ω-13 / Ω-14 / Ω-22** — the trust-and-capacity core: if false/ignored, everything
   else is moot. Pass 2 completed this tier: three independent derivations load the same
   component (see synthesis below).
2. **Ω-01** — invalidates daily operation of the truth model; most certain to manifest
   in week one of real use.
3. **Ω-06 / Ω-19 / Ω-21 / Ω-20** — the learning-corruption tier: substrate drift,
   Goodhart selection, frequency-dependent fitness, and path dependence are four
   independent reasons the evolution loop's conclusions can be wrong while every
   individual step is constitutionally legal. The most insidious tier: it corrupts
   *learning*, not operation, and pass 2 tripled its size.
4. **Ω-04 / Ω-11 / Ω-24 / Ω-25** — the mission tier: wholes under-verified (Ω-04),
   failures selected into invisibility (Ω-11 sharpened), products shaped like audit
   trails (Ω-24), safety intent mistaken for bounded evidence (Ω-25). Jointly these
   invalidate the claim that the goal tree protects architectural quality — the stated
   objective of the enterprise.
5. **Ω-03 / Ω-17 / Ω-02 / Ω-23** — the semantic stratum: bound what "portable,"
   "verified," and "recorded" can ever mean for NL-mediated systems.
6. **Ω-07 / Ω-08** — invalidate the router's pricing, not its structure.
7. **Ω-05, Ω-09, Ω-10, Ω-12, Ω-15, Ω-16, Ω-18, Ω-26, Ω-27** — regional envelopes and
   escape valves, each cheaply stateable or mechanizable.

## §C.1 The pass-2 synthesis: everything converges on the founder channel
Three derivations that share no premises arrive at the same component. Ω-14
(epistemology): the founder is the only external soundness oracle. Ω-19 (mechanism
design): founder-injected ground truth is the only non-Goodhartable signal. Ω-22
(information theory): that same channel has fixed, small capacity, and demand grows
with the system. Conclusion the corpus never draws: **the founder channel is
simultaneously the system's soundness anchor, its only unfakeable metric, and its
scarcest resource — and the decay theorem must therefore be re-read.** "Minimize founder
intervention" is safe only as "spend the channel on nothing but soundness, taste, and
ground truth"; spent to zero, the system loses its Gödel escape hatch (Ω-14), its
Goodhart immunity (Ω-19), and its freshness (Ω-05/Ω-22) in a single economy. The
five-verb ABI was righter than its own derivation knew — and it is a *budget*, not a
convenience.

## Closing observation (revised after pass 2)
The register still splits in two, and pass 2 moved the boundary. Payable incompleteness
— sentences the derivations owed and can still pay — now includes Ω-05, 09, 10, 12, 15,
16, 18, 21, 24, 26, 27 and the mechanism-halves of others. The irreducible walls between
PAEOS and the world now number nine: noise (Ω-01), holism (Ω-02), meaning (Ω-03), drift
(Ω-06), trust (Ω-13), self-reference (Ω-14), Goodhart (Ω-19), path dependence (Ω-20),
and the unwritable remainder of thought (Ω-23). A correct PAEOS does not eliminate
these; it names them in its preamble, assigns each a watchdog, and prices the one
resource — the founder channel — that all of its watchdogs ultimately draw on. The
derivations' only real sin was silence, and the silence had a shape: every hidden
assumption either flattered the metrics or flattered the medium.
