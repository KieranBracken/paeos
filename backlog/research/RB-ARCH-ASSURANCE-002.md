# PAEOS Minimum Architectural Conformance Firewall
## Research Backlog Item — v0.1

**Research ID:** RB-ARCH-ASSURANCE-002  
**Parent Research:** RB-ARCH-ASSURANCE-001 — PAEOS Architectural Assurance & Constitutional Architecture  
**Status:** PRE-IMPLEMENTATION / MUST PASS THROUGH PAEOS WORKFLOW  
**Priority:** CRITICAL / CONSTRUCTION PRECONDITION  
**Domain:** Architectural Assurance / Constitutional Governance / Verification Court / Seal Integrity  
**Scope:** Minimum Level-4 architectural-conformance machinery required before unrestricted continuation of canonical L09–L19 self-construction

---

# 1. Research Thesis

PAEOS now possesses an initial static architectural verifier capable of inspecting Python import relationships and enforcing at least:

- Kernel isolation;
- core module dependency acyclicity.

This is meaningful progress, but it does not yet establish full architectural conformance.

A Python import graph is not equivalent to:

- the canonical 19-layer execution graph;
- the authority graph;
- the information-flow graph;
- the evidence/provenance graph;
- or the constitutional architecture.

Furthermore, detecting an architectural violation is insufficient unless that detection is mechanically connected to the authority that controls whether a candidate implementation may be accepted and sealed.

The immediate research thesis is therefore:

> **Before PAEOS continues unrestricted autonomous construction of the remaining canonical layers, it requires a minimum fail-closed Architectural Conformance Firewall capable of mechanically rejecting implementations that violate the canonical architecture.**

This backlog item does **not** attempt to complete the entire Architectural Assurance research programme.

It asks:

> **What is the minimum machine-enforced architectural assurance capability required to safely protect construction of the remaining PAEOS architecture?**

---

# 2. Current Trigger

The current `runtime/arch_verifier.py` establishes an initial architectural-analysis capability.

However, the latest Level-4 implementation plan identified four canonical invariant classes:

1. Kernel Isolation;
2. Information Barrier;
3. Layer DAG;
4. Authority Flow.

The reported implementation currently demonstrates:

- Kernel Isolation;
- Python module import DAG checking.

This creates several unresolved questions:

1. Is Information Barrier conformance mechanically enforced?
2. Is Authority Flow mechanically enforced?
3. Is the canonical 19-stage lifecycle itself mechanically checked?
4. Does an architectural violation actually prevent Court acceptance or cryptographic sealing?
5. Are architectural rules external constitutional facts, or merely assumptions hard-coded into `arch_verifier.py`?
6. Can the verifier and architecture rules be modified together in a way that silently weakens enforcement?

These must be resolved before Level 4 can legitimately be considered complete.

---

# 3. Primary Research Question

## RQ-1

**What minimum architecture-conformance system must PAEOS possess before autonomous construction of L09–L19 can safely continue without relying on an LLM's interpretation of architectural correctness?**

---

# 4. Required Conformance Domains

The research must explicitly distinguish at least five architectural graphs.

## 4.1 Code Dependency Graph

Represents physical implementation dependencies.

```text
module
  │
  └── IMPORTS ──► module
```

Used to detect:

- kernel → runtime dependency violations;
- forbidden package relationships;
- circular imports;
- unwanted implementation coupling.

This is the domain partially implemented by the existing `arch_verifier.py`.

---

## 4.2 Canonical Execution Graph

Represents the actual PAEOS lifecycle.

```text
StageId
   │
   ├── ALLOWED_NEXT
   ├── REQUIRES
   └── PRODUCES
        │
        ▼
      StageId
```

This graph MUST NOT be conflated with Python import topology.

A repository may contain a perfectly valid acyclic import graph while executing an invalid lifecycle.

The verifier must be capable of distinguishing:

```text
VALID CODE GRAPH
      +
INVALID EXECUTION GRAPH
```

and rejecting the latter.

---

## 4.3 Authority Graph

Represents which powers may perform which actions.

Potential relationships:

```text
ROLE
 │
 ├── MAY_READ
 ├── MAY_WRITE
 ├── MAY_PROPOSE
 ├── MAY_VERIFY
 ├── MAY_ADJUDICATE
 ├── MAY_COMMIT
 └── MAY_EVOLVE
```

The system must detect authority inversion such as:

- Builder adjudicating its own evidence;
- Planner modifying constitutional state;
- operational runtime mutating constitutional law;
- Adversary writing implementation code;
- detection stages authoring institutional memory;
- non-kernel components directly committing protected state.

---

## 4.4 Information-Flow Graph

Represents which artifacts/context may cross subsystem boundaries.

Potential relationships:

```text
ARTIFACT
   │
   ├── PRODUCED_BY
   ├── READABLE_BY
   ├── SEALED_FOR
   └── FORBIDDEN_TO
```

This must enforce information barriers such as:

- Adversary isolation from Builder-private reasoning;
- sealed-bundle-only access where required;
- prohibition of hidden shared scratch state;
- no unintended context leakage across supposedly independent reviewers.

---

## 4.5 Evidence & Provenance Graph

Represents proof lineage.

```text
RUN
 │
 ▼
CLAIM
 │
 ▼
EVIDENCE
 │
 ├── PRODUCED_BY
 ├── BINDS_TO_RUN
 ├── BINDS_TO_ARTIFACT
 ├── REPRODUCED_BY
 └── ADJUDICATED_BY
```

Architectural conformance results themselves must have provenance.

A conformance PASS should not be an ephemeral boolean.

It should be attributable to:

- exact architecture specification/version;
- exact candidate artifact;
- exact run;
- exact verifier version;
- exact invariant set;
- exact result.

---

# 5. Requirement A — Complete the Missing Architectural Invariants

Research and implement, if justified, mechanical enforcement for all invariant classes promised by the existing Level-4 design.

## ARCH-INVARIANT-01 — Kernel Isolation

Existing hypothesis:

> `kernel/` MUST NOT depend upward upon `runtime/` or `ops/`.

Confirm existing implementation correctly detects all relevant Python import forms.

---

## ARCH-INVARIANT-02 — Information Barrier

Mechanically enforce architectural isolation requirements.

At minimum investigate:

- `runtime/review/` → Builder-private modules;
- private scratch/context imports;
- forbidden direct state access;
- bypasses through generic helper modules;
- indirect forbidden dependencies.

The system must determine whether checking only direct imports is sufficient.

---

## ARCH-INVARIANT-03A — Code Dependency DAG

Maintain module-level cycle detection where architecturally justified.

Do not call this the "19-layer DAG."

It is specifically:

> **implementation dependency acyclicity**

unless the canonical architecture states otherwise.

---

## ARCH-INVARIANT-03B — Canonical Lifecycle DAG

Add a separate validator for the actual PAEOS stage topology.

The validator must compare executable runtime transitions against the canonical lifecycle.

Investigate:

- legal `StageId` transitions;
- mandatory predecessors;
- conditional paths;
- trace classes;
- optional vs mandatory stages;
- restart/evolution edges;
- terminal conditions.

It must be possible to detect:

```text
L03 → L08
```

as invalid even when the Python import graph is valid.

---

## ARCH-INVARIANT-04 — Authority Flow

Mechanically represent and enforce architectural authority boundaries.

Minimum questions:

- Who can mutate constitutional state?
- Who can append protected ledger state?
- Who can produce evidence?
- Who can adjudicate evidence?
- Who can author institutional memory?
- Who can commit institutional memory?
- Who can issue a seal?
- Who can propose architectural evolution?
- Who can ratify architectural evolution?

The research must determine which authority relationships are statically checkable and which require runtime verification.

---

# 6. Requirement B — Make Architectural Conformance Seal-Gating

The Architecture Verifier must not merely exist as an optional analysis utility.

Research the correct constitutional integration point.

Candidate shape:

```text
Candidate Build
      │
      ▼
Ordinary Verification Court
      │
      ▼
Architectural Conformance
      │
      ├── PASS ─────────► continue toward Seal
      │
      └── FAIL ─────────► REMAND / BLOCK
```

Required property:

> **A candidate known to violate a mandatory architectural invariant MUST be mechanically incapable of receiving a valid PAEOS seal through the ordinary execution path.**

The research must determine whether this belongs:

- inside the Verification Court;
- immediately before Seal;
- as a dedicated architectural evidence obligation;
- or through another existing canonical gate.

Do not introduce another sequential lifecycle layer unless the canonical architecture requires one.

---

# 7. Requirement C — Negative Seal-Blocking Integration Tests

Unit-testing the verifier alone is insufficient.

The implementation must demonstrate causal authority.

Required negative tests should include equivalents of:

```text
test_kernel_runtime_dependency_prevents_seal
test_forbidden_information_flow_prevents_seal
test_illegal_stage_transition_prevents_seal
test_authority_inversion_prevents_seal
test_missing_architecture_conformance_result_prevents_seal
```

The important assertion is not merely:

```text
verifier.detects_violation == True
```

It is:

```text
architecture_violation
      ↓
seal unavailable
```

The system must fail closed.

---

# 8. Requirement D — Separate Architectural Law From the Verifier

Architectural truth must not ultimately exist only as Python conditionals inside:

```text
runtime/arch_verifier.py
```

Otherwise a worker modifying architecture could modify the verifier simultaneously and redefine what "valid" means.

Research a machine-readable canonical architecture representation.

Potential conceptual structure:

```text
CanonicalArchitectureSpec

version

layers
transitions
dependencies
authorities
information_barriers
evidence_requirements
persistence_rules
forbidden_edges
required_edges
constitutional_invariants
evolution_rules
```

The verifier should ideally:

```text
READ architectural law
        ↓
OBSERVE implementation/runtime
        ↓
COMPARE
        ↓
PASS / VIOLATION
```

rather than:

```text
DEFINE architecture
        +
VERIFY architecture
```

within the same mutable code artifact.

---

# 9. Requirement E — Define Authority Over the Architecture Manifest

If a machine-readable architectural specification is introduced, determine:

1. Where it lives.
2. Whether it belongs inside the constitutional trust boundary.
3. Who may read it.
4. Who may propose changes.
5. Who may ratify changes.
6. How changes are versioned.
7. How changes are sealed.
8. How runtime compatibility is verified.
9. Whether changing the manifest invokes the HARD-LOOP / constitutional amendment path.
10. Whether PAEOS may ever automatically modify it.

The verifier and its source of architectural truth must not be mutable under the same ordinary Builder authority.

---

# 10. Requirement F — Conformance Result as Evidence

Architectural conformance should produce a structured artifact.

Candidate form:

```text
ArchitectureConformanceReport

run_id
candidate_artifact_hash
architecture_spec_hash
verifier_version
checked_invariants

violations:
  - invariant_id
  - observed_edge
  - expected_constraint
  - evidence_location
  - severity

result:
  PASS | FAIL
```

Research whether this should enter:

- CAS;
- Court evidence;
- ledger;
- Seal provenance;
- all of the above.

The goal is that a future auditor can answer:

> **Which architectural rules did this exact sealed artifact prove compliance with?**

---

# 11. Requirement G — Runtime Conformance, Not Merely Static Conformance

Static AST analysis cannot prove all architectural properties.

Research the minimum runtime evidence needed to validate:

- actual stage order;
- stage reachability;
- stage bypasses;
- authority use;
- write-scope behavior;
- evidence flow;
- information barriers;
- termination;
- restart transitions.

Potential mechanism:

```text
Declared Architecture
        │
        ▼
Expected Trace
        │
        ▼
Observed Runtime Trace
        │
        ▼
Trace Conformance
```

Determine whether event-ledger records can provide the observed runtime graph.

---

# 12. Requirement H — Exact 19-Layer Conformance

The system must be capable of distinguishing:

```text
"This code contains implementations named after all 19 layers"
```

from:

```text
"The canonical lifecycle actually executes and governs all required 19 layers."
```

Research mechanical checks for:

- existence;
- reachability;
- correct ordering;
- required predecessors;
- required successors;
- required evidence;
- correct authority;
- correct artifact production;
- correct persistence;
- correct gating;
- absence of bypass paths.

This is necessary to prevent another SoftLoop-style false-completeness event.

---

# 13. Requirement I — Bootstrap vs Canonical Architecture Awareness

PAEOS must understand that a deliberately reduced bootstrap can be valid without being canonically complete.

The architecture verifier therefore requires status semantics such as:

```text
BOOTSTRAP_VALID
CANONICAL_PARTIAL
CANONICAL_CONFORMANT
ARCHITECTURALLY_INVALID
```

or a better research-derived equivalent.

The system must not incorrectly classify:

> valid bootstrap

as:

> invalid system

nor:

> valid bootstrap

as:

> completed canonical PAEOS.

---

# 14. Requirement J — Verifier Integrity / Self-Protection

Research how the architecture verifier itself is protected against weakening.

Threat scenario:

```text
Builder changes architecture
        +
Builder changes arch_verifier
        ↓
new architecture magically passes
```

Investigate:

- TCB placement;
- hard-loop review;
- independent verifier versioning;
- mutation tests;
- golden invariant fixtures;
- dual verifier implementations;
- architecture-spec hashes;
- independent adversarial verification.

Changing architectural law or its enforcement must receive stronger scrutiny than ordinary implementation work.

---

# 15. Requirement K — Architecture Differential

For every architecture-affecting change, determine whether PAEOS should compute:

```text
Architecture BEFORE
        ↓
      diff
        ↓
Architecture AFTER
```

The differential should identify:

- added dependencies;
- removed dependencies;
- new authority edges;
- removed authority edges;
- changed execution transitions;
- new persistence paths;
- changed evidence relationships;
- altered information barriers.

This would allow the Court to evaluate not merely absolute validity, but the architectural meaning of the change.

---

# 16. Requirement L — No Silent Architecture Expansion

A model must not be able to create:

- a new canonical stage;
- a new constitutional authority;
- a new privileged persistence path;
- a new bypass edge;
- a new kernel dependency;
- a new constitutional mutation route

through an ordinary implementation task.

Such changes must be detectable as:

```text
ARCHITECTURE CHANGE
```

and routed through the appropriate constitutional/evolutionary process.

---

# 17. Research Question — What Is Static vs Dynamic?

Classify every proposed architectural invariant into:

### STATIC

Can be proven from code/configuration without executing PAEOS.

Example:

```text
kernel imports runtime
```

### DYNAMIC

Requires runtime trace evidence.

Example:

```text
L06 was bypassed during execution
```

### HYBRID

Requires both static architecture and runtime evidence.

Example:

```text
Role.ADVERSARY is statically denied Builder-private access
AND
runtime traces demonstrate the barrier was actually enforced.
```

This classification should drive verifier architecture.

---

# 18. Required Adversarial Scenarios

Before acceptance, deliberately construct violations and confirm they fail closed.

At minimum:

## Scenario A — Kernel Dependency Violation

Inject:

```text
kernel/example.py → import runtime.example
```

Expected:

```text
ARCH-INVARIANT-01 FAIL
Seal blocked
```

---

## Scenario B — Information Barrier Violation

Allow Adversary to depend on or read Builder-private context.

Expected:

```text
ARCH-INVARIANT-02 FAIL
Seal blocked
```

---

## Scenario C — Lifecycle Bypass

Construct:

```text
L05 → L08
```

while skipping mandatory intermediate stages.

Expected:

```text
CANONICAL-LIFECYCLE FAIL
Seal blocked
```

---

## Scenario D — Authority Inversion

Permit Builder to exercise adjudication or constitutional mutation authority.

Expected:

```text
AUTHORITY-FLOW FAIL
Seal blocked
```

---

## Scenario E — Verifier Missing

Disable architectural verification entirely.

Expected:

```text
NO CONFORMANCE EVIDENCE
Seal blocked
```

---

## Scenario F — Verifier Weakening

Modify the verifier to remove an invariant while simultaneously introducing a violation.

Expected:

```text
HARD-LOOP / ARCHITECTURE ENFORCEMENT CHANGE DETECTED
Ordinary build path blocked
```

---

## Scenario G — Bootstrap Misclassification

Run the intentionally reduced Phase-1 SoftLoop.

Expected:

```text
Recognised as partial/bootstrap architecture
NOT declared canonical-complete
```

---

# 19. Required Deliverables

## D1 — Architectural Graph Taxonomy

Define separate:

- code graph;
- lifecycle graph;
- authority graph;
- information-flow graph;
- evidence/provenance graph.

---

## D2 — Canonical Architecture Schema

Machine-readable representation of architectural law.

---

## D3 — Completed Minimum Invariant Set

Mechanical enforcement for:

- Kernel Isolation;
- Information Barrier;
- Code Dependency constraints;
- Canonical Lifecycle transitions;
- Authority Flow.

---

## D4 — Seal-Gate Integration

Architectural conformance becomes a mandatory fail-closed condition for sealing architecture-affecting changes.

---

## D5 — Runtime Trace Conformance

Mechanism comparing expected canonical lifecycle against observed ledger/runtime trace.

---

## D6 — Architecture Conformance Report

Run-bound, artifact-bound, architecture-version-bound output suitable for CAS/Court/Seal provenance.

---

## D7 — Negative Seal Tests

Integration tests proving each architectural violation blocks sealing.

---

## D8 — Verifier Integrity Model

Rules governing modification of:

- architecture specification;
- conformance verifier;
- invariant definitions.

---

## D9 — Bootstrap Classification Model

Formal distinction between:

- valid bootstrap;
- partial canonical implementation;
- complete canonical conformance;
- architectural invalidity.

---

## D10 — Resume Decision

A final evidence-backed determination:

```text
SAFE_TO_RESUME_L09_L19_AUTONOMOUS_CONSTRUCTION
```

or:

```text
NOT_SAFE_TO_RESUME
```

with unresolved blockers listed.

---

# 20. Acceptance Criteria

This backlog item is NOT complete because:

```text
pytest passes
```

or:

```text
arch_verifier reports zero violations
```

or:

```text
an AI reviewer declares Level 4 complete
```

It is complete only when all of the following are demonstrated.

- [ ] Kernel isolation violation is mechanically detected.
- [ ] Kernel isolation violation prevents sealing.
- [ ] Information barrier violation is mechanically detected.
- [ ] Information barrier violation prevents sealing.
- [ ] Module dependency checking is clearly separated from lifecycle checking.
- [ ] Canonical StageId transitions are machine-readable.
- [ ] Executable runtime transitions are compared against canonical transitions.
- [ ] Illegal stage transitions prevent sealing.
- [ ] Authority rules are machine-readable or otherwise independently authoritative.
- [ ] Authority inversion is mechanically detected.
- [ ] Authority inversion prevents sealing.
- [ ] Missing architecture-conformance evidence fails closed.
- [ ] Conformance reports bind to exact `run_id`.
- [ ] Conformance reports bind to exact candidate artifact hash.
- [ ] Conformance reports bind to exact architecture-spec version/hash.
- [ ] Runtime traces are validated against expected architecture where static analysis is insufficient.
- [ ] Bootstrap execution cannot be mislabeled canonical-complete.
- [ ] Architectural-rule changes are distinguished from ordinary implementation changes.
- [ ] A Builder cannot silently weaken the verifier and architecture in one ordinary change.
- [ ] Negative integration tests prove all critical paths fail closed.
- [ ] `pytest` passes.
- [ ] `pyright` passes.
- [ ] AST assurance checks pass.
- [ ] Existing Verification Court negative tests remain green.
- [ ] An independent adversarial review attempts to bypass the architecture gate.
- [ ] The resulting evidence supports or rejects `SAFE_TO_RESUME_L09_L19_AUTONOMOUS_CONSTRUCTION`.

---

# 21. Explicit Non-Goals

Do NOT use this backlog item as justification to immediately construct:

- a full general-purpose ontology of all software architecture;
- the entire SAKG;
- the entire Concept Graph;
- a new L20;
- a giant distributed Architecture Court;
- unrestricted recursive architecture evolution;
- a permanent multi-model council for every ordinary change;
- a comprehensive formal-proof theorem prover.

Those may become justified by the parent Architectural Assurance research.

This backlog exists to implement or derive only the:

> **minimum architectural firewall required to safely finish PAEOS itself.**

---

# 22. Relationship to Existing Level-4 Work

Do not discard the existing `runtime/arch_verifier.py`.

Treat it as the first experimental implementation of:

> **static code dependency conformance**

and evaluate which pieces should survive.

The research workflow must be allowed to conclude that:

- parts are correct;
- parts require expansion;
- parts are architecturally misplaced;
- some checks belong elsewhere;
- or the implementation must be redesigned.

Existing work is evidence, not authority.

---

# 23. Construction Constraint

This research item itself MUST pass through the PAEOS workflow.

Do not instruct the worker:

> "Implement the architecture described above exactly."

Instead, PAEOS must:

1. RE_DERIVE the architectural-assurance requirement;
2. IDEATE competing mechanisms;
3. RESEARCH relevant approaches;
4. perform TRADEOFF analysis;
5. perform MITIGATION;
6. DESIGN the selected minimum architecture;
7. CRITIQUE it;
8. PLAN it;
9. IMPLEMENT it;
10. VERIFY it;
11. perform independent/adversarial review;
12. satisfy all currently available governance/evidence/seal requirements.

The hypotheses in this backlog are candidate requirements and failure cases.

They are not permission to bypass PAEOS's own reasoning process.

---

# 24. Stop Condition

Once the minimum firewall is proven, **stop expanding Architectural Assurance temporarily**.

Resume construction of the canonical PAEOS spine.

The intended sequence is:

```text
Existing Level 2/3 Assurance
           │
Existing Level 4A static verifier
           │
           ▼
RB-ARCH-ASSURANCE-002
Minimum Architectural Conformance Firewall
           │
           ▼
Independent falsification
           │
           ▼
Checkpoint / Seal
           │
           ▼
RESUME CANONICAL PAEOS CONSTRUCTION
L09 → ... → L19
           │
           ▼
Full self-hosting
           │
           ▼
Return to broader
RB-ARCH-ASSURANCE-001
           │
           ▼
Advanced Architectural Assurance
```

This prevents Architectural Assurance itself from becoming an endless side project that delays completion of PAEOS.

---

# 25. Desired End State

Before PAEOS resumes unrestricted self-construction, the following must be true:

```text
AI proposes implementation
        ↓
PAEOS executes workflow
        ↓
Tests verify behavior
        ↓
Court verifies evidence
        ↓
Adversary challenges implementation
        ↓
Architecture Firewall independently checks:
    code dependencies
    lifecycle topology
    authority flow
    information barriers
    provenance
        ↓
ANY REQUIRED CHECK FAILS
        ↓
NO SEAL
```

The objective is not to make architectural error theoretically impossible.

The objective is:

> **An architecturally invalid implementation must not be able to silently masquerade as successful PAEOS construction merely because its code runs, its tests pass, its models agree, or its local verifier reports success.**

Only after this property is demonstrated should unrestricted autonomous construction of the remaining canonical PAEOS layers resume.