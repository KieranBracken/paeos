# PAEOS Conformance Map — Step 2.1 Addendum (v1.0)

Status: ADDENDUM to `PAEOS_TWO_AXIS_CONFORMANCE_MAP_v1.md`, per founder review 2026-08-19.
Scope: reclassifications, atomic conflict split, seal-terminology resolution. No code changes.
Sources: Freeze v1.0 (`PAEOS_CANONICAL_19_LAYER_FREEZE_v1.md`), map v1, kernel/seal.py.

## 1. Capability vs. transition status split

Map v1 conflated "component exists and works" with "the run reached it lawfully." Corrected
model — every layer now carries TWO statuses:

- `component_capability_status` — does the implemented component satisfy its stage contract?
- `runtime_transition_status` — was the run's path to it constitutionally valid (lawful L02
  ceremony decision + required predecessor evidence present)?

Consequences (corrections to map v1):

| Layer | v1 status | Corrected |
|---|---|---|
| L08 DESIGN, L09 CRITIQUE | CONFORMANT_EXECUTED | capability CONFORMANT; transition MALFORMED until L02 exists (no ceremony decision, no discharge stubs on any path) |
| L12 IMPLEMENT, L13 VERIFY | CONFORMANT_EXECUTED | capability CONFORMANT (post-remediation); transition MALFORMED (same basis) |
| L13 | CONFORMANT_EXECUTED | **CANONICAL_CONFLICT — IMPLEMENTATION PRESENT** until C-01a adjudicated (see §2) |
| L19 | CONFORMANT_EXECUTED (machinery tested) | capability IMPLEMENTED/TESTED; autonomous runtime evolution **UNPROVEN**; R5 evidence outstanding |

## 2. Atomic conflict split (C-01 decomposed; C-02/C-03 narrowed)

- **C-01a — L13 authority.** Prose vs. YAML disagree on the verification authority semantics.
  The deterministic Court is a strong candidate interpretation but is NOT ratified canonical
  semantics until the founder adjudicates. Suggested outcome: ratify Court as canonical L13
  implementation (it is stricter), via amendment.
- **C-01b — L15 role/artifacts.** Residual prose-vs-YAML divergence on Documentation & Ledger
  responsibilities/artifacts. Founder adjudication; side-by-side clauses in Freeze Part A/B.
- **C-01c — required-artifact differences** anywhere else in Part A vs. Part B. Sweep pending.
- **C-02 — secondary-source numbering** (backlog reconstructions; "stage 11/12/14" IPs).
  Reclassified: NOT a constitutional conflict — none are founder-ratified authorities. Outcome:
  mark stale/superseded, repair references. No ratification needed.
- **C-03 — narrowed** to genuinely unresolved ceremony edge cases ONLY: how v/r are evaluated,
  escalation, partial escalation, de-escalation, whether substantive execution can replace a
  lawful discharge. The settled law (L02 assigns; v×r basis; Trace-A/B sets; stubs mandatory)
  is NOT in conflict and is removed from C-03.

## 3. Seal terminology (resolved conceptually; founder to confirm)

- **Kernel `SealRecord`** (kernel/seal.py) = a cryptographic evidence attestation over
  bundle+verdict+adversary+ledger head. It is the L13→L14→L15 chain anchor.
- **Canonical L16 disposition** = promotion decision among Merge / Seal / Reject /
  Research-Only / Dormant.
- Conclusion: they are DIFFERENT semantic objects. `SealRecord` ≠ L16 Seal disposition. The
  runtime implements the attestation, not the disposition (`promote_to=null` on all 25 seals
  is consistent with L16 never executing). Historical seal disposition (Entry 141 queue) must
  therefore assess ONLY the attestation's evidentiary validity; L16 disposition absence is a
  separate R4 gap, not a defect of past seals.

## 4. Other founder-directed corrections adopted

1. **No L02 coding yet.** If v/r mechanics are not already defined in the corpus,
   `RB-CEREMONY-DEPTH-001` adjudicates the design first. Implement existing law; do not legislate.
2. **L07 is a ceremony-routing consequence**, not an isolated reorder patch. Trace-A: L06+L07
   discharge with stubs. Trace-B: substantive L07 requires substantive L06 matrix. The
   unconditional MITIGATION→DESIGN path disappears once the ceremony contract executes.
3. **A-08 fail-closed.** Runtime must ENFORCE BuilderFamily ≠ AuditorFamily. Single-family
   availability ⇒ L14 halts/remands/waits; never silently degrades to same-family audit.
   Trace-A does not exempt L14 — canonical Trace-A path executes L14 in full.
4. **ADE / MISSION_CONTROL: frozen authority, re-evaluated, not deleted.** Possible L05/L06
   capability invocable on Trace-B; self-hosting objective-source machinery. Dead: their old
   out-of-band justification.

## 5. Revised sequence to R4 (founder-approved order)

Step 3 founder decisions (atomic conflicts C-01a/b/c, seal-terminology confirmation) →
RB-CEREMONY-DEPTH-001 → implement canonical L02 ceremony contract → discharge evidence stubs →
runtime executes ceremony-resolved obligation graph (NOT more hard-coded SoftLoop stages) →
A-08 fail-closed enforcement → prove canonical Trace-A → prove warranted Trace-B → R4
conformance decision.
