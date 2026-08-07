# PAEOS Divergence Audit — "Could two teams implement this identically?"

Date: 2026-07-20. Question: could an independent team implement PAEOS with **zero founder
questions**, and would two competent teams produce **compatible** implementations?
Scope: only defects in the listed categories (contradiction, undefined concept, circular
dependency, missing contract, ambiguous transition, undefined authority, impossible
acceptance, missing persistence/interface/runtime). Style/opinion/alternatives excluded.
Each defect was verified against the actual text (greps recorded in session), not memory.

**Verdict: NO — 3 Blockers, 5 Majors would cause divergence.** None requires redesign;
all are bounded amendments. Details below, then the rejected candidates (to show the line).

---

## BLOCKERS

### Z-1 — Two documents both claim authority and contradict each other
- **Category:** internal contradiction.
- **File/section:** `spec/PAEOS-4-kernel.md` §5.3 (frozen) vs `reviews/5.5-implementation-audit/01_IMPLEMENTATION_BLOCKERS.md` B-01/B-02/B-06 + `reviews/7-skills-as-capabilities.md` CAP-1.
- **Divergence:** §5.3 (frozen text) says no actor may write `status`; B-01 says the kernel writes it. §2.3 says provenance is a field; B-02 says it's server-stamped and unforgeable. The 5.5 amendments are labeled "BLOCKING, must integrate before Wave 1" but are **not integrated into the frozen spec**. Team-A implements the literal frozen §5.3 (no one writes status → nothing promotes); Team-B implements B-01. There is no precedence rule stating which text governs when they conflict.
- **Smallest amendment:** produce **PAEOS-4 v1.1** = the frozen text with the 12 blocking 5.5 amendments + CAP-1 merged inline, and add one precedence clause to §14: "where a ratified review amendment and prior frozen text conflict, the amendment governs." One release, no new design.
- **Belongs in:** **PAEOS-7** (the amendment-integration release).

### Z-2 — The meta-schema is promised in the kernel text but does not exist
- **Category:** missing implementation contract.
- **File/section:** referenced in `reviews/5.5-implementation-audit/02_MODULE_GRAPH.md` §cycle-1 and `genesis/G2.md` as *"the meta-schema is part of the kernel spec text, embedded identically in every conformant implementation"* — but no kernel file contains it. `spec/PAEOS-4-kernel.md` §2.2/§13 never define the shape the sentinel `sha256:meta.v1` resolves to.
- **Divergence:** the meta-schema validates the G1+G2 genesis batch (GenesisRecord + schema artifacts). Two teams embed **different** meta-schemas → different genesis validation → different founding store → conformance C1 passes on each in isolation but the stores are incompatible. This defeats PAEOS-4's own cross-implementation-compatibility purpose at commit zero.
- **Smallest amendment:** add one appendix to §13.1 — the literal JSON-schema (field lists + types) for exactly two shapes: schema-kind Policy artifact, and GenesisRecord. It is short; only its *absence* is the defect.
- **Belongs in:** **PAEOS-7**.

### A-1 — Parent goals have no promotion mechanism
- **Category:** missing runtime behavior + ambiguous state transition.
- **File/section:** `spec/PAEOS-4-kernel.md` §2.5 (`AggregationContract`, line 136), §3.2 (integrated entry: "parent aggregation input recorded", line 210), §3.3 (T1–T5).
- **Divergence:** a child reaching `integrated` "records parent aggregation input," but **no T-rule promotes the parent**, and two questions are undefined: (1) *who* evaluates the AggregationContract and writes the parent's promotion — the reactor automatically, or a re-dispatched agent? (2) Does a non-leaf parent *also* need its own `evidence_spec` satisfied (which §2.5 makes REQUIRED-non-empty for **all** goals, per K1), or does the AggregationContract *substitute* for it? Team-A: reactor auto-promotes a parent when children satisfy the contract, aggregation = the parent's evidence. Team-B: parent needs independent evidence beyond children and waits for an agent. These produce entirely different control flow and different `verified` semantics for every non-leaf goal — i.e., most of the tree.
- **Smallest amendment:** add **T6**: "the reactor promotes a non-leaf goal when its AggregationContract is satisfied by children's states"; and one sentence in §2.5: "for a non-leaf goal the AggregationContract discharges its evidence_spec — no separate evidence is required." (Also pins the `weighted([...])` sub-format as weights over child ids.)
- **Belongs in:** **PAEOS-7**.

## MAJORS

### C-1 — Budget accrual during `blocked` / founder-wait is undefined
- **Category:** missing runtime behavior.
- **File/section:** `spec/PAEOS-4-kernel.md` §10 (Budget), §3.3 T5.
- **Divergence:** §10.3 debits `spent_direct` at EXEC/SPAWN call time, but `wall_clock_s` and `decisions` have no accrual rule while a goal sits `blocked` awaiting a founder Decision (batched, possibly days per PAEOS-2 §7). Team-A charges wall-clock during the wait → every escalated goal eventually hits BUDGET_EXCEEDED and auto-incidents just from waiting. Team-B pauses the clock. Opposite behaviors on the most sensitive path (founder escalation).
- **Smallest amendment:** §10.6 — "wall_clock and decisions accrue only while actively dispatched; time in `blocked` is not charged; a Decision debits 1 from the nearest ancestor's `decisions` dimension at escalation."
- **Belongs in:** **PAEOS-7**.

### D-1 — Trunk multiplicity and boundary are undefined
- **Category:** undefined concept.
- **File/section:** `spec/PAEOS-4-kernel.md` §2.1 (`trunk/<name>`), K8/§I9 ("one Integrator per trunk").
- **Divergence:** nothing defines how many trunks exist, who creates one, or what `<name>` partitions. Team-A: a single `trunk/main` → all integration fully serialized (K8 throughput bottleneck). Team-B: a trunk per workload or per subtree → integration parallelizes across trunks. This is a first-order difference in the concurrency model and throughput, and it changes what "coherence" I9 even protects.
- **Smallest amendment:** §2.1 — "one trunk per workload root; `<name>` = workload id; all descendants integrate to their workload trunk; additional trunks require an Amendment."
- **Belongs in:** **PAEOS-7**.

### E-1 — Concurrent provisional amendments to the same policy are unordered
- **Category:** ambiguous state transition.
- **File/section:** `spec/PAEOS-4-kernel.md` §3.2 (`provisional`, line 207), §9.4; `SPEC-CLARIFICATIONS.md` SC-07 (PolicyDelta.expected_prev).
- **Divergence:** two amendments target policy P; both go `provisional`, both "apply delta to Policy store." SC-07's `expected_prev` gives optimistic concurrency — but is it checked against the last **integrated** version or the last **provisional** one? If provisional, a not-yet-final delta blocks others and a later revert must unblock them (unspecified). Team-A serializes on provisional state; Team-B serializes only on integrated. Divergent amendment throughput and divergent behavior when a provisional amendment reverts.
- **Smallest amendment:** §9.4 — "expected_prev is checked against the last integrated policy version; a second provisional amendment to the same policy blocks (IDENTITY_CONFLICT) until the first finalizes or reverts."
- **Belongs in:** **PAEOS-7.5** (implementation-audit granularity).

### F-1 — The render grammar is unspecified (known, unresolved)
- **Category:** missing interface definition.
- **File/section:** `spec/PAEOS-4-kernel.md` §6.3 (`rendered: text`), §6.1 (byte-identical manifest only); logged as `reviews/5.5 B-05` which defers to backlog node F-RENDER (a task, not a contract).
- **Divergence:** §6.1 pins the *manifest* byte-identical but not the *rendered* prompt. Two teams render the same manifest into different prompt text → different agent behavior → the compiled-context determinism (K5) the whole system rests on is not actually guaranteed across implementations.
- **Smallest amendment:** pin the grammar in §6.3 (not just defer to F-RENDER): section order = resolution order; one header line per manifest entry `## <slot> <id>@<version>`; verbatim body; fixed delimiter; nothing else emitted.
- **Belongs in:** **PAEOS-7.5**.

### G-1 — The 19 operational states have no defined mapping to the 5 kernel lattice states
- **Category:** missing implementation contract.
- **File/section:** `operations/WORKFLOW_STATE_MACHINE.yaml` (states L01–L19 + DONE) vs `spec/PAEOS-4-kernel.md` §3 (declared→…→integrated). The YAML references lattice states only as prose strings in `entry`/`exit`, never as a formal mapping.
- **Divergence:** a team implementing the YAML literally builds a 19-state FSM parallel to the kernel's 5-state lattice, with no defined correspondence — e.g., during L01–L11 is the goal `declared`? Does L12 write `status=speculated` or `executed`? Is L13→L14 the `executed→verified` transition? Team-A treats L-states as workflow metadata on a `declared` goal; Team-B maps each L to a lattice transition and writes status accordingly. The two produce different store states for identical work.
- **Smallest amendment:** add a `lattice_mapping:` block to the YAML: L01–L11→declared · L12→speculated/executed · L13–L14→executed→verified · L15–L16→verified→integrated · L17–L19→evolution loop. One block.
- **Belongs in:** **PAEOS-8** (this is the operational/lifecycle layer, not the kernel).

---

## Candidates checked and REJECTED (not defects — would NOT cause divergence)

- **Evidence-binding granularity (file vs hunk):** explicitly a bootstrap parameter (§10-open / SC). A *deliberately open knob* both teams read as "choose one and record it" — convergent by instruction, not divergent.
- **Classification rubric thresholds, fan-out N, CAP, DL, Steward cadence:** all declared AMENDABLE genesis parameters. Open-by-design ≠ ambiguous.
- **SC-01..12:** each already carries a *binding resolution* (encodings, signing, ULIDs, TriggerExpr, etc.). A team follows the resolution; no divergence.
- **CAP-1 CapabilityRef grammar:** CAP-1 is an un-integrated *candidate* (reviews/7), not frozen — out of scope for "implement the frozen system." (When integrated, its CapabilityRef namespace must be pinned; noted for PAEOS-7, not a current defect.)
- **Self-hosting criterion / Ω-25 unverifiable safety properties:** a named limitation with a stated reading ("verified = bounded-spec satisfied"), not an ambiguity — both teams implement the same bounded check.

## Disposition summary

| # | Defect | Sev | Target |
|---|---|---|---|
| Z-1 | Authoritative-source contradiction | Blocker | PAEOS-7 |
| Z-2 | Meta-schema content missing | Blocker | PAEOS-7 |
| A-1 | Parent aggregation promotion | Blocker | PAEOS-7 |
| C-1 | Budget accrual while blocked | Major | PAEOS-7 |
| D-1 | Trunk multiplicity/boundary | Major | PAEOS-7 |
| E-1 | Concurrent provisional amendments | Major | PAEOS-7.5 |
| F-1 | Render grammar unspecified | Major | PAEOS-7.5 |
| G-1 | L-state ↔ lattice-state mapping | Major | PAEOS-8 |

All eight are bounded amendments (a clause, a table, an appendix, or a merge release). The
frozen architecture is not implicated — no primitive, invariant, role, or loop needs
change. The honest headline: **the corpus is not yet implementable without questions, but
every open question has a one-amendment answer**, and five of the eight cluster into a
single PAEOS-7 integration release.
