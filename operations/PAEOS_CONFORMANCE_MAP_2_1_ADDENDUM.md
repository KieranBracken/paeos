# PAEOS Conformance Map — Step 2.1 Addendum (v1.0)

Status: ADDENDUM to `PAEOS_TWO_AXIS_CONFORMANCE_MAP_v1.md`, per founder review 2026-08-19.
Scope: reclassifications, atomic conflict split, seal-terminology resolution. No code changes.
Sources: `operations/ENGINEERING_LIFECYCLE.md` (v1.3, canonical L01–L19 baseline), `operations/WORKFLOW_STATE_MACHINE.yaml` (derived machine-executable form), map v1, kernel/seal.py, and the archived verbatim extraction `operations/archive/PAEOS_19_LAYER_LIFECYCLE_EXTRACTION_v1.md` (derived, no independent authority).

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
| L12 IMPLEMENT | CONFORMANT_EXECUTED | capability CONFORMANT (post-remediation); transition MALFORMED (same basis) |
| L13 VERIFY | CONFORMANT_EXECUTED | capability **CONFORMANT** — the deterministic Court is a faithful implementation of EL L13 prose (mechanical/self-approving, A-09); former C-01a resolved mechanically by EL-wins (see §2). transition MALFORMED until L02 ceremony + discharge stubs exist |
| L19 | CONFORMANT_EXECUTED (machinery tested) | capability IMPLEMENTED/TESTED; autonomous runtime evolution **UNPROVEN**; R5 evidence outstanding |

> Addendum reclassification (2026-08-19): the prior line "CANONICAL_CONFLICT — IMPLEMENTATION
> PRESENT until C-01a adjudicated" is superseded. Under the corrected hierarchy the EL prose wins
> over the derived WSM YAML, so no founder adjudication is needed for L13 (see §2).

## 2. Atomic conflict split — resolved mechanically by hierarchy (2026-08-19)

> Prior text treated C-01a/C-01b/C-01c as requiring founder adjudication. The corrected source
> hierarchy (`ENGINEERING_LIFECYCLE.md` v1.3 = canonical baseline; WSM = derived form; EL prose
> wins; ratified amendments win where they exist) resolves them without founder action:

- **C-01a — L13 authority.** RESOLVED: EL L13 prose ("Auditor/Runtime (mechanical) + Adversary",
  "mechanical evidence is self-approving via EXEC signature", A-09) is canonical and wins over the
  derived WSM YAML (role `builder`, `sonnet`). The deterministic Court is a faithful implementation
  of that prose, not a conflict. Optional L19 blessing of the Court as canonical L13 → candidate
  `proposals/PAEOS-IP-0014` (non-blocking; awaiting founder).
- **C-01b — L15 role/artifacts.** RESOLVED: EL prose wins → role = **Runtime + Builder**; artifacts =
  the prose list (Inventory Atlas, roadmaps, architecture diagrams, knowledge graph, decision logs).
  The WSM's narrower `implementation_atlas` list is the derived form and is subordinate.
- **C-01c — required-artifact differences** elsewhere in Part A vs B. RESOLVED: EL prose wins on any
  divergence; a full sweep is noted for reference repair only (not a founder decision).
- **C-02 — secondary-source numbering** (backlog reconstructions; "stage 11/12/14" IPs).
  RESOLVED: NOT a constitutional conflict — none are founder-ratified authorities. Outcome:
  mark stale/superseded, repair references. No ratification needed.
- **C-03 — narrowed** to genuinely unresolved ceremony edge cases ONLY: how v/r are evaluated,
  escalation, partial escalation, de-escalation, whether substantive execution can replace a
  lawful discharge. These now live in **RB-CEREMONY-DEPTH-001** (research), not a conflict register.

## 3. Seal terminology (resolved; documentation clarification, not a founder decision)

> 2026-08-19: previously headed "founder to confirm". Both `SealRecord` and the L16 disposition
> are independently well-defined in canonical sources (the EL L16 prose and kernel/seal.py), so
> this is a terminology clarification, not an irreducible constitutional choice. No founder action
> is required for the distinction itself; only the optional L13-Court ratification (IP-0014) and
> any L16 promotion machinery remain open implementation/R4 items.

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

1. **No L02 coding yet.** The v/r mechanics ARE defined in the EL corpus (`(verifiability ×
   reversibility)`, Trace-A/B, auto-discharge rule, `assigned_at: L02`). `RB-CEREMONY-DEPTH-001`
   therefore performs canonical extraction + edge-case closure (how v/r is evaluated, escalation,
   de-escalation), not greenfield design. Implement existing law; do not legislate.
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
