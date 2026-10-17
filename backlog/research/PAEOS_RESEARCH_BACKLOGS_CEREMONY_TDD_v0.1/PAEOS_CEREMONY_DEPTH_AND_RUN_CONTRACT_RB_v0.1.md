# PAEOS Ceremony Depth Determination & Run Ceremony Contract
## Research Backlog Item — v0.1

**Research ID:** RB-CEREMONY-DEPTH-001  
**Status:** **D1 EXTRACTED (2026-08-19) — doctrine EXISTS in the canonical Engineering Lifecycle; proceed to L02 ceremony-contract design (Step 3).**  
**Priority:** CRITICAL  
**Domain:** L02 Triage / Ceremony Depth / Constitutional Lifecycle / Architectural Assurance  
**Related Work:** `operations/ENGINEERING_LIFECYCLE.md` (v1.3, canonical L01–L19 baseline), `operations/WORKFLOW_STATE_MACHINE.yaml` (derived form), `PAEOS_CEREMONY_DEPTH_DOCTRINE_EXTRACTION_v1.md` (**D1**) in this directory, Two-Axis Conformance Map v1, Architectural Conformance Firewall.
**Authority note (2026-08-19):** "Canonical 19-Layer Freeze" is NOT an authority (demoted/archived; see `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` Entry 146). Use `ENGINEERING_LIFECYCLE.md` v1.3.

---

# 1. Research Thesis

PAEOS is constitutionally defined around a canonical 19-layer engineering lifecycle, but not every objective necessarily requires substantive execution of every layer.

Canonical ceremony-depth rules appear to permit some obligations to be lawfully discharged for sufficiently low-risk, reversible, cheaply verifiable work.

This distinction is fundamental:

> A canonical layer being discharged is not equivalent to that layer being skipped.

A valid discharge must be:

- authorized by the correct ceremony-depth decision;
- permitted for the selected trace/depth;
- explicitly recorded;
- supported by the required evidence or discharge artifact;
- visible to the ledger and Architectural Conformance Firewall.

The current implementation appears not to have consistently represented this distinction.

The research objective is therefore:

> Determine exactly how ceremony depth is constitutionally selected, represented, escalated, discharged, evidenced, and verified across the canonical PAEOS lifecycle.

---

# 2. Primary Research Question

## RQ-1

How should PAEOS determine the ceremony depth required for an objective while ensuring that:

1. low-risk work is not subjected to unnecessary reasoning ceremony;
2. high-risk work cannot under-classify itself to save cost;
3. all canonical layer obligations remain auditable;
4. discharged obligations remain constitutionally evidenced;
5. runtime execution can be mechanically checked against the run-specific ceremony contract?

---

# 3. Canonical Recovery Requirement

Before designing a new ceremony-depth algorithm, recover the existing canonical doctrine.

Research MUST inspect authoritative sources including, as applicable:

- Constitution;
- canonical PAEOS lifecycle documents;
- execution architecture specifications;
- kernel lifecycle/state definitions;
- ratified IPs and amendments;
- CER rules;
- trace definitions;
- existing L02 TRIAGE contracts;
- existing ceremony-depth references.

The research must extract:

- who assigns ceremony depth;
- when ceremony depth is assigned;
- which trace/depth classes exist;
- what each class means;
- what factors determine classification;
- which layers may be discharged under each class;
- which layers are never dischargeable;
- required discharge evidence;
- escalation rules;
- whether de-escalation is permitted;
- conflict-resolution authority.

If authoritative sources conflict, record:

`CANONICAL CONFLICT — REQUIRES RESOLUTION`

Do not silently reconcile contradictions.

---

# 4. Key Distinction: Canonical Obligation vs Substantive Execution

The research must formalize the following distinction:

```text
CANONICAL LAYER OBLIGATION
          |
          +---- SUBSTANTIVE EXECUTION
          |       -> normal canonical artifacts/evidence
          |
          +---- LAWFUL DISCHARGE
                  -> explicit discharge reason
                  -> ceremony decision reference
                  -> required evidence/stub
```

A third state must exist for invalid behavior:

```text
MANDATORY OBLIGATION
        |
        +---- neither executed nor lawfully discharged
                     |
                     -> CONSTITUTIONAL NON-CONFORMANCE
```

---

# 5. Candidate Run Obligation States

Research whether each layer obligation should be represented using a status model such as:

- `EXECUTE_REQUIRED`
- `EXECUTED_CONFORMANT`
- `DISCHARGE_PERMITTED`
- `DISCHARGED_CONFORMANT`
- `DISCHARGE_EVIDENCE_MISSING`
- `MANDATORY_BUT_SKIPPED`
- `NOT_APPLICABLE`
- `ESCALATED_TO_EXECUTION`
- `UNKNOWN`

These are candidate semantics, not predetermined final API names.

---

# 6. L02 as Ceremony Compiler

Investigate whether L02 should be understood as compiling:

```text
Canonical 19-layer architecture
            +
Objective characteristics
            +
Risk / reversibility / uncertainty
            +
Verification characteristics
            +
Constitutional floors
            |
            v
RUN CEREMONY CONTRACT
```

The resulting Run Ceremony Contract should potentially define:

- selected trace/depth;
- classification evidence;
- substantive stages required;
- stages lawfully dischargeable;
- evidence required for each discharge;
- independent-review requirements;
- Court requirements;
- escalation triggers;
- architecture version against which the decision was made.

---

# 7. Ceremony Classification Factors

Recover canonical factors first.

Where the constitution leaves discretion, research whether the following are appropriate inputs:

## Reversibility
- Can the change be safely rolled back?
- Is rollback deterministic?
- Does rollback restore all persistent state?

## Verification Strength
- Can correctness be deterministically reproduced?
- Are strong automated tests possible?
- Is verification cheap relative to the consequence of failure?

## Blast Radius
- single local function;
- subsystem;
- cross-subsystem;
- kernel/TCB;
- ecosystem-wide.

## Architectural Impact
Does the change alter:
- layer topology;
- dependencies;
- authority;
- information barriers;
- evidence obligations;
- persistence;
- governance;
- canonical architecture?

## Constitutional / TCB Impact
Does it touch:
- constitution;
- kernel;
- Court;
- Seal;
- Architecture Registry;
- verifier;
- amendment machinery;
- capability broker;
- institutional memory authority?

## Irreversibility
Does it involve:
- destructive migration;
- permanent state mutation;
- external irreversible side effect;
- constitutional ratification;
- cryptographic identity changes?

## Uncertainty
- known local repair;
- ambiguous cause;
- multiple viable architectures;
- novel research problem;
- external unknowns.

## Consequence of Undetected Error
What happens if the implementation is wrong but verification incorrectly passes?

---

# 8. Ceremony Floors

Research mandatory minimum-ceremony conditions.

Candidate rule: Certain properties must impose a minimum depth regardless of aggregate score.

Examples to investigate:

- constitutional mutation;
- architecture modification;
- TCB modification;
- verifier modification;
- authority expansion;
- Court weakening;
- Seal changes;
- irreversible migration;
- institutional-memory authority changes;
- unknown/high-consequence external side effects.

The system must not permit:

```text
high-impact constitutional change
        +
"looks simple"
        ->
lowest ceremony
```

---

# 9. Determinism vs Model Judgment

Research the appropriate balance between:

### Deterministic policy
Explicit rules determine minimum ceremony.

### Structured model judgment
An LLM evaluates uncertainty or semantic impact within bounded fields.

### Hybrid classification

```text
deterministic floors
        +
structured risk assessment
        +
model analysis
        +
policy validation
        ->
ceremony depth
```

The research should prefer designs where the model cannot simply declare its own work "easy."

---

# 10. Ceremony Escalation

Ceremony depth MUST be capable of escalating during execution if newly discovered facts invalidate the initial classification.

Example:

```text
Trace-A
   |
"local timeout fix"
   |
implementation discovers capability-broker change required
   |
CEREMONY ESCALATION
   |
higher trace/depth
   |
previously discharged obligations become active
```

Research:
- who can trigger escalation;
- whether escalation is automatic;
- required evidence;
- whether the run restarts or continues;
- how prior discharge stubs are superseded;
- ledger representation.

---

# 11. Ceremony De-Escalation

Research whether decreasing ceremony after a run begins should ever be permitted.

Default research hypothesis:

> Upward escalation should be easy and fail-safe; downward relaxation should require stronger justification and should never be under unilateral Builder control.

Determine canonical rule.

---

# 12. Discharge Stub Contract

A lawfully discharged layer must not disappear silently.

Research a machine-readable artifact such as:

```yaml
layer: L06
obligation: TRADEOFF
status: DISCHARGED
ceremony_depth: TRACE_A
run_id: ...
architecture_version: ...
triage_decision_ref: ...
legal_basis: ...
reason: ...
evidence_refs:
  - ...
timestamp: ...
```

Determine:
- required fields;
- signature/provenance;
- CAS storage;
- ledger representation;
- whether stubs are Court evidence;
- whether stubs become Seal provenance.

---

# 13. Ceremony Depth and the Architectural Firewall

The Runtime Lifecycle Trace Verifier must not naïvely compare:

```text
expected = all 19 layers
observed = executed stages
```

Instead it should resolve:

```text
Canonical Architecture
        |
        v
Ceremony Contract
        |
        v
Run-specific obligations
        |
        +---- substantive execution
        |
        +---- lawful discharge
        |
        v
Observed runtime trace + discharge artifacts
        |
        v
CONFORMANT / NON-CONFORMANT
```

Research the exact integration.

---

# 14. Ceremony Depth and Semantic Contracts

A discharge must satisfy the canonical discharge contract for the layer.

An executed layer must satisfy the substantive semantic contract.

The verifier should therefore be able to distinguish:

```text
Stage executed but semantically empty
```

from:

```text
Stage lawfully discharged with correct evidence
```

The former must not automatically be considered stronger.

---

# 15. Ceremony Depth and Cost Governance

Ceremony depth is partly an economic mechanism.

Research how it should interact with:
- model cost;
- token budget;
- latency;
- compute budget;
- verification cost;
- risk.

Important constraint:

> Economic pressure MUST NOT be permitted to lower ceremony below the constitutionally required minimum.

Cost may influence choices above the minimum.

---

# 16. Adversarial Scenarios

## A — Builder Self-Underclassification
Builder labels an architectural change Trace-A.

Expected:
- deterministic floor overrides classification.

## B — Missing L02 Decision
Run proceeds without a recorded ceremony decision.

Expected:
- lifecycle conformance fails closed.

## C — Missing Discharge Stub
Stage is dischargeable but no evidence stub exists.

Expected:
- obligation remains unsatisfied.

## D — Illegal Discharge
A non-dischargeable layer is marked discharged.

Expected:
- architecture violation.

## E — Mid-Run Scope Expansion
Implementation discovers TCB impact.

Expected:
- ceremony automatically escalates.

## F — Cost Pressure
Budget becomes low.

Expected:
- system may stop/remand;
- system must not silently reduce constitutional ceremony.

## G — Model Misclassification
LLM says "simple" despite deterministic high-risk signals.

Expected:
- deterministic policy wins.

---

# 17. Required Deliverables

## D1 — Canonical Ceremony Doctrine Extraction
Authoritative definition of existing trace/depth rules with citations.

## D2 — Ceremony Classification Model
Inputs, floors, authority, decision mechanics.

## D3 — Run Ceremony Contract Schema
Machine-readable per-run obligations.

## D4 — Discharge Stub Schema
Machine-readable lawful-discharge evidence.

## D5 — Escalation Protocol
Rules for mid-run ceremony escalation.

## D6 — Lifecycle Verifier Integration
How ceremony contracts drive expected runtime traces.

## D7 — Court/Seal Integration
How ceremony decisions and discharge evidence affect Court adjudication and Seal provenance.

## D8 — Negative Test Matrix
Fail-closed tests for invalid ceremony behavior.

---

# 18. Acceptance Criteria

Research is not complete until it can answer:

- [ ] Who constitutionally determines ceremony depth?
- [ ] At which canonical stage is it determined?
- [ ] What trace/depth classes actually exist?
- [ ] What exact factors distinguish them?
- [ ] What deterministic minimum-ceremony floors exist?
- [ ] Which layers may be discharged under each class?
- [ ] What evidence is required for each discharge?
- [ ] Is missing discharge evidence constitutional non-conformance?
- [ ] Can ceremony escalate mid-run?
- [ ] Who may trigger escalation?
- [ ] Can ceremony ever decrease?
- [ ] How is the decision recorded?
- [ ] How does the Architecture Firewall consume it?
- [ ] How does Court verify it?
- [ ] How does Seal provenance represent it?
- [ ] How are historical runs without ceremony records classified?
- [ ] Canonical conflicts are explicitly identified rather than silently resolved.

---

# 19. Anti-Goals

Do NOT:
- add new lifecycle stages merely to implement ceremony selection;
- let Builder unilaterally choose the cheapest trace;
- treat skipped and discharged as synonymous;
- infer canonical ceremony rules from current runtime shortcuts;
- rewrite the constitution during research;
- implement code before canonical extraction is complete.

---

# 20. Desired End State

For every PAEOS run:

```text
Objective
    |
    v
L02 / canonical ceremony authority
    |
    v
Run Ceremony Contract
    |
    +---- EXECUTE Lx
    |
    +---- DISCHARGE Ly + evidence stub
    |
    v
Observed run
    |
    v
Architecture Firewall
    |
    +---- all obligations satisfied -> continue
    |
    +---- missing/illegal obligation -> REMAND / NO SEAL
```

PAEOS should be able to prove not merely that stages were skipped or executed, but:

> Every canonical obligation was satisfied at the ceremony depth legally required for the exact run.
