# PAEOS-8.1 — Runtime Clarifications

> Status: normative clarification layer. Role: eliminate the eight implementation
> ambiguities in `reviews/8-divergence-audit.md` so that two independent teams produce
> compatible runtimes. **This document introduces no new architecture, ontology, lifecycle
> stage, agent class, or authority.** It only fixes the single legal interpretation of
> behaviour that prior documents left open. Where a clause below conflicts with prior
> frozen text, this document governs for the named clause only (see Z-1, which makes that
> precedence rule itself normative).
>
> RFC-2119 keywords (MUST, MUST NOT, SHALL, SHALL NOT, MAY) are normative.

---

## Z-1 — Authoritative-source precedence

**1. Problem Summary.** The frozen `spec/PAEOS-4-kernel.md` and the ratified review
amendments (PAEOS-5.5 B-01/B-02/B-06, and downstream) both read as authoritative and
contradict each other in places (e.g. who writes `status`). No document states which text
governs on conflict, and the amendments were never merged into the kernel text.

**2. Why Independent Teams Diverge.** Team-A implements `PAEOS-4` §5.3 literally (no actor
may write `status` ⟹ nothing promotes). Team-B implements B-01 (`status` is
kernel-maintained). Both cite a frozen document; nothing adjudicates.

**3. Constitutional Amendment.**
> **Z-1.1** The specification SHALL be interpreted as a single ordered corpus. Precedence,
> highest first: (a) this document (PAEOS-8.1) for the clauses it names; (b) ratified
> review amendments (PAEOS-3.5 A-01..A-19, PAEOS-5.5 B-01..B-08 and pins SC-13..SC-24,
> PAEOS-7 series); (c) the frozen kernel `PAEOS-4`; (d) all other documents.
> **Z-1.2** Where a higher-precedence clause conflicts with a lower one, the higher clause
> governs and the lower is void **only to the extent of the conflict**; all
> non-conflicting text remains in force.
> **Z-1.3** Before implementation begins, the ratified amendments in tier (b) MUST be
> merged inline into a single reissue, **PAEOS-4 v1.1**, and every implementation MUST
> build from PAEOS-4 v1.1, not the original frozen text. PAEOS-4 v1.1 SHALL contain no
> normative content beyond the mechanical application of tier-(b) amendments.

**4. Affected Documents.** `PAEOS-4` §14 (add precedence clause); reissue as
`PAEOS-4 v1.1`; `PAEOS-5.5` (marked as tier-b source); this document (tier-a).

**5. Compatibility.** No invariant changes; this defines *reading order* for text that
already exists. It preserves append-only history (K4) because v1.1 is a new document, not
an edit of the frozen original, and the merge is mechanical (no discretion).

---

## Z-2 — Meta-schema definition

**1. Problem Summary.** PAEOS-5.5 B-03 requires a hardcoded meta-schema (sentinel
`schema: "sha256:meta.v1"`) to validate the genesis batch, and states it is "part of the
kernel spec text" — but no document contains it.

**2. Why Independent Teams Diverge.** Each team invents its own meta-schema shape ⟹
different validation of the G1+G2 batch ⟹ incompatible founding stores that each pass C1
in isolation.

**3. Constitutional Amendment.**
> **Z-2.1** The meta-schema is defined normatively as follows and MUST be embedded, byte
> for byte after JCS canonicalization, identically in every conformant implementation. Its
> content hash MUST equal the sentinel `sha256:meta.v1` (the sentinel's literal value is
> the JCS-SHA-256 of the object in Z-2.2; implementations MUST verify this equality at
> build time).
> **Z-2.2** The meta-schema validates exactly two object shapes and no others:
> ```
> meta.v1 := {
>   "$id": "sha256:meta.v1",
>   "validates": ["policy/schema-artifact", "genesis-record"],
>   "common_header": {                       # per PAEOS-4 §2.2
>     "id":      {"type": "ULID", "required": true},
>     "type":    {"enum": ["policy","genesis-record"], "required": true},
>     "version": {"type": "uint", "required": true, "const": 1},
>     "prev":    {"type": ["null"], "required": true},
>     "schema":  {"const": "sha256:meta.v1", "required": true},
>     "created": {"type": "rfc3339-ms-utc", "required": true},
>     "author":  {"$ref": "provenance", "required": true}
>   },
>   "policy/schema-artifact": {              # kind=schema-artifact only
>     "kind":     {"const": "schema-artifact", "required": true},
>     "scope":    {"const": "kernel", "required": true},
>     "body":     {"type": "json-schema", "required": true},
>     "loading":  {"const": "always", "required": true}
>   },
>   "genesis-record": { "$ref": "PAEOS-4 §13.1 field list", "required_all": true }
> }
> ```
> **Z-2.3** An object presenting `schema: "sha256:meta.v1"` whose `type` is neither a
> schema-artifact Policy nor the GenesisRecord MUST be rejected `SCHEMA_VIOLATION`.

**4. Affected Documents.** `PAEOS-4` §13.1 (append meta-schema appendix), §2.2 (reference
it); `PAEOS-4.5` §1.4 (validator embeds it); `genesis/G1.md`, `genesis/G2.md` (cite Z-2.2).

**5. Compatibility.** Preserves the validator↔store genesis-cycle break (PAEOS-5.5 §02
cycle-1) exactly as designed; adds no new object type (schema-artifact and genesis-record
already exist); is pure specification of an already-required artifact.

---

## A-1 — Parent (non-leaf) goal promotion

**1. Problem Summary.** `AggregationContract` is defined (PAEOS-4 §2.5) and the
`integrated` entry condition records "parent aggregation input," but no T-rule promotes a
parent, and it is unstated whether a non-leaf goal also needs its own `evidence_spec`
satisfied or whether aggregation substitutes for it.

**2. Why Independent Teams Diverge.** Team-A: the reactor auto-promotes a parent when its
children satisfy the contract, and aggregation IS the parent's evidence. Team-B: a
re-dispatched agent promotes the parent, and the parent needs independent evidence beyond
its children. Different control flow and different `verified` semantics for every non-leaf
goal.

**3. Constitutional Amendment.**
> **A-1.1** For a non-leaf goal (a goal with ≥1 child), the `AggregationContract` SHALL
> discharge its `evidence_spec`. Such a goal MUST NOT require independent evidence beyond
> the satisfaction of its contract. Its `evidence_spec` field, though present per §2.5,
> is satisfied exactly when A-1.3 holds.
> **A-1.2** A new automatic transition **T6 (AGGREGATE)** is added to §3.3: *the reactor
> MUST re-evaluate a non-leaf goal's AggregationContract whenever any child's status
> changes, and MUST promote the parent to `verified` when A-1.3 holds, and MUST regress it
> (per T1) when A-1.3 ceases to hold.* T6 is a reactor action; no agent performs it.
> **A-1.3** Contract satisfaction is defined per rule: `all-children-verified` ⟺ every
> child status ∈ {verified, integrated}; `quorum(n)` ⟺ ≥ n children status ∈
> {verified, integrated}; `weighted(W)` where `W` is a list of `(child_id, weight:uint)`
> ⟺ Σ weights of children status ∈ {verified, integrated} ≥ ⌈(Σ all weights)/2⌉ + 1,
> unless the contract states an explicit `threshold`, in which case that threshold governs.
> **A-1.4** A non-leaf goal reaches `integrated` per the ordinary rule (§3.2): its own
> verified state (A-1.2) plus the Integrator's single-threaded merge (K8). Promotion to
> `verified` (T6) MUST NOT itself perform integration.

**4. Affected Documents.** `PAEOS-4` §2.5 (define `weighted` sub-format + `threshold`
option; A-1.1), §3.2 (non-leaf `verified` entry references A-1.3), §3.3 (add T6),
§4 (K1 note: non-leaf evidence is the contract).

**5. Compatibility.** Preserves K1 (promotion still requires evidence — children's
verified evidence IS the evidence); preserves I3 (children were independently verified);
preserves K8/I9 (integration remains single-threaded, T6 only sets `verified`); adds no
new state (uses existing lattice) and no new actor (reactor already owns T1–T5).

---

## C-1 — Budget accrual during `blocked`

**1. Problem Summary.** §10 debits `spent_direct` at EXEC/SPAWN call time, but no rule
governs `wall_clock_s` and `decisions` accrual while a goal is `blocked` awaiting a founder
Decision (batched, possibly days per PAEOS-2 §7).

**2. Why Independent Teams Diverge.** Team-A charges wall-clock during the wait ⟹ every
escalated goal eventually hits BUDGET_EXCEEDED from waiting alone and auto-incidents.
Team-B pauses the clock. Opposite behaviour on the founder-escalation path.

**3. Constitutional Amendment.**
> **C-1.1** The `wall_clock_s` dimension MUST accrue only while a goal is **actively
> dispatched** (an agent is spawned against it or an EXEC is in flight). Time during which
> a goal carries the computed `blocked` flag (T5) or is awaiting a Decision resolution
> MUST NOT be charged to `wall_clock_s`.
> **C-1.2** The `decisions` dimension MUST be debited exactly 1 from the nearest ancestor
> goal that holds an allocation in that dimension, at the moment a `Goal(kind=decision)` is
> spawned (escalation), and MUST NOT be debited again on resolution.
> **C-1.3** `blocked` is a computed flag, not a lattice state (§3.3 T5); it SHALL NOT
> alter `status` and SHALL NOT by itself cause BUDGET_EXCEEDED.

**4. Affected Documents.** `PAEOS-4` §10.3 (accrual timing), add §10.6 (C-1.1..C-1.3);
§3.3 T5 (cross-reference C-1.3).

**5. Compatibility.** Preserves K11 conservation (charging *less* never violates
Σ-children ≤ parent); preserves the A-12 economics (decisions remain a priced, conserved
dimension); introduces no new dimension or object.

---

## D-1 — Trunk multiplicity and boundary

**1. Problem Summary.** `trunk/<name>` is a reserved ref (§2.1) with one Integrator each
(K8), but nothing defines how many trunks exist, who creates one, or what `<name>`
partitions.

**2. Why Independent Teams Diverge.** Team-A: a single `trunk/main` ⟹ all integration
serialized. Team-B: a trunk per workload or subtree ⟹ integration parallelizes. A
first-order difference in the concurrency model.

**3. Constitutional Amendment.**
> **D-1.1** There MUST be exactly one trunk per **workload**, named `trunk/<workload-id>`.
> The kernel-bootstrap workload uses `trunk/kernel`.
> **D-1.2** A trunk is created by the genesis batch (for `trunk/kernel`) or at the
> authoring of a workload root goal (for `trunk/<workload-id>`); no other event creates a
> trunk. Every goal integrates to the trunk of its workload (the `workload` field, §2.5),
> and MUST NOT integrate to any other trunk.
> **D-1.3** Additional trunks within a workload MUST NOT exist unless introduced by an
> Amendment. K8's "one Integrator per trunk" therefore serializes integration **per
> workload**, and integration MAY proceed in parallel **across** workloads.

**4. Affected Documents.** `PAEOS-4` §2.1 (trunk creation + naming), §2.5 (workload→trunk
binding), K8/§I9 (scope is per-workload); `PAEOS-4.5` §05 storage model (ref namespace).

**5. Compatibility.** Preserves K8/I9 (coherence is still single-threaded within the unit
that shares a trunk); preserves A-17 tenancy (trunk boundary = workload boundary, already
the namespace unit); adds no new concept — `workload` and `trunk` both already exist.

---

## E-1 — Concurrent provisional amendments to one policy

**1. Problem Summary.** Two amendments may target policy P; both enter `provisional` and
"apply delta to Policy store." SC-07's `expected_prev` gives optimistic concurrency, but it
is unstated whether `expected_prev` is checked against the last *integrated* or last
*provisional* version, and how a revert interacts.

**2. Why Independent Teams Diverge.** Team-A serializes on the provisional version (second
amendment blocks). Team-B checks against the last integrated version (both apply, last
writer wins). Divergent amendment throughput and divergent behaviour on revert.

**3. Constitutional Amendment.**
> **E-1.1** A `PolicyDelta.expected_prev` (SC-07) MUST be checked against the target
> policy's **current head version at delta-application time**, where a `provisional`
> amendment's applied delta DOES advance the head (the delta is live, per §3.2). A stale
> `expected_prev` MUST fail `IDENTITY_CONFLICT`.
> **E-1.2** Consequently, at most one amendment to a given policy MAY be in `provisional`
> at a time; a second amendment targeting the same policy MUST block (`IDENTITY_CONFLICT`)
> until the first reaches `integrated` or `reverted`.
> **E-1.3** On T3 revert of a provisional amendment, the delta is un-applied and the policy
> head returns to its pre-provisional version; any amendment that blocked on E-1.2 MAY then
> retry against the restored head.

**4. Affected Documents.** `PAEOS-4` §9.4 (E-1.1..E-1.3), §3.2 (`provisional` advances
head), §3.3 T3 (revert restores head); `SPEC-CLARIFICATIONS.md` SC-07 (expected_prev
semantics).

**5. Compatibility.** Preserves A-06 probationary integration (single provisional at a
time is the safe reading); preserves K4 append-only (revert is a new version restoring
prior body, not a history rewrite); uses only the existing IDENTITY_CONFLICT error (§11).

---

## F-1 — Render grammar

**1. Problem Summary.** §6.1 pins the compiled-context *manifest* byte-identical but not
the *rendered* prompt (§6.3); PAEOS-5.5 B-05 deferred the grammar to a backlog task rather
than specifying it, so K5 determinism is not guaranteed across implementations.

**2. Why Independent Teams Diverge.** Two teams render the same manifest into different
prompt text (section order, delimiters, headers) ⟹ different agent behaviour.

**3. Constitutional Amendment.**
> **F-1.1** `render(manifest) → text` MUST be a total, deterministic function producing
> byte-identical output for identical manifests across all conformant implementations.
> **F-1.2** The rendering grammar SHALL be exactly: sections emitted in **manifest order**
> (which is resolution order, §6.2); each manifest entry rendered as one header line
> `## <slot> <id>@<version>\n`, followed by the entry's verbatim body bytes, followed by a
> single `\n`; sections separated by the fixed delimiter `\n---\n`; no other bytes emitted
> (no preamble, no trailer, no whitespace normalization of bodies).
> **F-1.3** Adapter context-lowering (PAEOS-4 §12.1) MAY wrap this rendered text in a
> declared, hashed adapter preamble but MUST NOT alter the rendered bytes between the
> first and last section.
> **F-1.4** Golden `rendered` fixtures (backlog F-RENDER) MUST be produced from F-1.2 and
> are conformance-binding (C-suite).

**4. Affected Documents.** `PAEOS-4` §6.1 (add rendered to the determinism guarantee),
§6.3 (F-1.2 grammar); `PAEOS-4.5` §1.8 (compiler emits per F-1.2); `PAEOS-5.5` B-05
(resolved); backlog `F-RENDER` (goldens per F-1.2).

**5. Compatibility.** Preserves K5/I6 (this is what makes compiled-context determinism
real, not aspirational); preserves K9 narrow waist (adapters still only lower, F-1.3);
adds no new mechanism — it specifies an already-required function.

---

## G-1 — Operational L-states ↔ kernel lattice states

**1. Problem Summary.** The 19 operational states (`operations/WORKFLOW_STATE_MACHINE.yaml`,
L01–L19) reference the 5 kernel lattice states (§3) only as prose strings, never as a
formal mapping. A team implementing the YAML literally builds a parallel FSM disconnected
from the kernel `status` field.

**2. Why Independent Teams Diverge.** Team-A treats L-states as workflow metadata on a
`declared` goal (kernel status untouched until L16). Team-B maps each L-state to a lattice
transition and writes `status` at each. Different store states for identical work.

**3. Constitutional Amendment.**
> **G-1.1** The operational lifecycle L01–L19 SHALL be **metadata layered over** the kernel
> lattice, not a replacement for it. A goal's authoritative promotion is governed solely by
> the kernel lattice and its invariants (K1, T1–T6); L-states MUST NOT be treated as
> lattice states and MUST NOT gate kernel promotion except through the evidence they
> produce.
> **G-1.2** The binding mapping (added as `lattice_mapping:` to
> `WORKFLOW_STATE_MACHINE.yaml`) is: **L01–L11 ⟹ `declared`** (framing/understanding/review
> occur before any candidate exists); **L12 ⟹ `speculated` then `executed`** (build then
> run); **L13–L14 ⟹ `executed` → `verified`** (verification + independent audit are the
> promoting evidence); **L15–L16 ⟹ `verified` → `integrated`**; **L17–L19 ⟹ the evolution
> loop** (they operate on incidents/amendments, not the goal's own status).
> **G-1.3** Where an L-state and the kernel lattice appear to disagree, the **kernel lattice
> governs** (per Z-1 precedence: kernel over operational doctrine). An L-state transition
> that would violate a kernel invariant MUST NOT occur.

**4. Affected Documents.** `operations/WORKFLOW_STATE_MACHINE.yaml` (add `lattice_mapping:`
per G-1.2); `operations/ENGINEERING_LIFECYCLE.md` (§ceremony-depth cross-reference);
`methodology/PAEOS-CONSTITUTIONAL-ENGINEERING-LIFECYCLE.md` §6a (crosswalk consistent).

**5. Compatibility.** Preserves the entire kernel (the lifecycle is declared subordinate,
not authoritative — consistent with the lifecycle docs' own "not part of the kernel spec"
statement); introduces no new lifecycle stage (maps existing L-states); preserves
router-not-pipeline (ceremony depth already governs which L-states fire).

---

## Implementation Readiness Verdict

**Yes.** After PAEOS-8.1 is ratified and PAEOS-4 v1.1 is issued per Z-1.3, two independent
engineering teams can implement compatible PAEOS runtimes without asking the founders any
question, for these reasons:

- **Every divergence point now has exactly one legal interpretation.** Z-1 fixes reading
  order; Z-2 pins the one meta-schema; A-1 defines the single promotion rule (T6) and the
  single evidence semantics for non-leaf goals; C-1, D-1, E-1 make budget accrual, trunk
  boundary, and provisional-amendment ordering deterministic; F-1 makes rendered context
  byte-identical; G-1 subordinates the operational FSM to the kernel lattice with a fixed
  mapping.
- **Every kernel behaviour is deterministic:** promotion (K1 + T1–T6), rendering (F-1),
  validation (Z-2), integration scope (D-1), and amendment ordering (E-1) are all
  single-valued functions of store state.
- **Every authority boundary is explicit and unchanged:** no new agent class, no new
  authority, no ontology change — every amendment is a clarification of behaviour the
  existing roles already own.
- **Every implementation contract is complete:** the previously "promised but absent"
  artifacts (meta-schema, render grammar) are now written; the previously "referenced but
  unmechanized" behaviours (parent promotion, budget-during-block, trunk creation) now have
  normative rules.

**Residual condition (not a blocker, a sequencing requirement):** implementation MUST begin
from **PAEOS-4 v1.1** (the mechanical merge mandated by Z-1.3), not the original frozen
text. Producing v1.1 is a mechanical, question-free operation defined entirely by the
tier-(b) amendment list. Once v1.1 exists, no open question remains, and implementation MAY
begin immediately.

The architecture is unchanged. Only the ambiguities are gone.
