schema: paeos.sakg.s-probe/v1
mission: RB-0005-mission-zero-sakg-discovery
probe: S-PROBE extraction feasibility spike
method: deterministic field-presence rubric; no semantic inference; absent fields are loss
verdict: NO-GO
loss_ratio: 0.503
field_total: 153
weighted_loss: 77.0
node_types: Decision, Problem, Option, Constraint, Objective, TradeOff, Mechanism, Pattern, Component, Outcome, Scar, EvidenceRef

## methodology
A field is extractable only when the sealed record states a direct marker and value; partial means related context exists but the SAEOS-1 field is not losslessly reconstructable; absent means no defensible signal was found.

## goal: gate-a
source: reviews/tasks/PAEOS_GATE_A_FOUNDER_COURT_DISPOSITION_38B5395.md
source_sha256: 2e42f4823c970b4e0379182b8c31c1e5eae0730d905d57ab04a127e6d9641bfe
source_disposition: COURT_SEALED

- Decision.id: extractable
- Decision.context: extractable
- Decision.options: partial
- Decision.chosen: extractable
- Decision.rationale: partial
- Decision.constitutional_basis: partial
- Problem.id: partial
- Problem.statement: extractable
- Problem.scope: partial
- Problem.evidence: partial
- Option.id: partial
- Option.description: partial
- Option.status: partial
- Option.evidence: partial
- Constraint.id: partial
- Constraint.statement: absent
- Constraint.source: extractable
- Constraint.evidence: partial
- Objective.id: partial
- Objective.statement: partial
- Objective.metric: partial
- TradeOff.id: partial
- TradeOff.axis: partial
- TradeOff.alternatives: partial
- TradeOff.resolution: partial
- TradeOff.evidence: partial
- Mechanism.id: partial
- Mechanism.description: partial
- Mechanism.evidence: partial
- Pattern.id: partial
- Pattern.name: partial
- Pattern.recurrence: partial
- Pattern.evidence: partial
- Component.id: partial
- Component.name: partial
- Component.interface: partial
- Component.evidence: partial
- Outcome.id: partial
- Outcome.status: extractable
- Outcome.window: partial
- Outcome.measurement: partial
- Outcome.evidence: partial
- Scar.id: absent
- Scar.root_cause: absent
- Scar.detection_signature: partial
- Scar.guard_action: absent
- Scar.severity: absent
- EvidenceRef.hash: absent
- EvidenceRef.uri: absent
- EvidenceRef.kind: extractable
- EvidenceRef.reverification: partial

field_counts: extractable=7, partial=37, absent=7

## goal: gate-b
source: reviews/tasks/PAEOS_GATE_B_FOUNDER_COURT_DISPOSITION_993B6CC.md
source_sha256: 8c8214b39deee9c4d125f98ea5a3dd83c04d1b639432274028da3eaf5b723ed9
source_disposition: COURT_SEALED

- Decision.id: extractable
- Decision.context: extractable
- Decision.options: partial
- Decision.chosen: extractable
- Decision.rationale: partial
- Decision.constitutional_basis: partial
- Problem.id: partial
- Problem.statement: absent
- Problem.scope: absent
- Problem.evidence: partial
- Option.id: partial
- Option.description: partial
- Option.status: partial
- Option.evidence: partial
- Constraint.id: partial
- Constraint.statement: extractable
- Constraint.source: extractable
- Constraint.evidence: partial
- Objective.id: partial
- Objective.statement: partial
- Objective.metric: partial
- TradeOff.id: partial
- TradeOff.axis: absent
- TradeOff.alternatives: absent
- TradeOff.resolution: partial
- TradeOff.evidence: partial
- Mechanism.id: absent
- Mechanism.description: absent
- Mechanism.evidence: partial
- Pattern.id: partial
- Pattern.name: absent
- Pattern.recurrence: partial
- Pattern.evidence: partial
- Component.id: partial
- Component.name: partial
- Component.interface: absent
- Component.evidence: partial
- Outcome.id: partial
- Outcome.status: extractable
- Outcome.window: partial
- Outcome.measurement: partial
- Outcome.evidence: partial
- Scar.id: partial
- Scar.root_cause: partial
- Scar.detection_signature: partial
- Scar.guard_action: partial
- Scar.severity: partial
- EvidenceRef.hash: absent
- EvidenceRef.uri: absent
- EvidenceRef.kind: extractable
- EvidenceRef.reverification: absent

field_counts: extractable=7, partial=33, absent=11

## goal: gate-c
source: reviews/tasks/PAEOS_GATE_C_FOUNDER_COURT_DISPOSITION_F0BE9AB.md
source_sha256: 74aeee262656e5dd14b762849b99399a344f684362bef4c0e258c4f4eac2c978
source_disposition: COURT_SEALED

- Decision.id: extractable
- Decision.context: extractable
- Decision.options: partial
- Decision.chosen: extractable
- Decision.rationale: partial
- Decision.constitutional_basis: partial
- Problem.id: partial
- Problem.statement: absent
- Problem.scope: partial
- Problem.evidence: partial
- Option.id: partial
- Option.description: partial
- Option.status: partial
- Option.evidence: partial
- Constraint.id: partial
- Constraint.statement: extractable
- Constraint.source: extractable
- Constraint.evidence: partial
- Objective.id: partial
- Objective.statement: partial
- Objective.metric: partial
- TradeOff.id: partial
- TradeOff.axis: absent
- TradeOff.alternatives: partial
- TradeOff.resolution: partial
- TradeOff.evidence: partial
- Mechanism.id: partial
- Mechanism.description: partial
- Mechanism.evidence: partial
- Pattern.id: partial
- Pattern.name: partial
- Pattern.recurrence: partial
- Pattern.evidence: partial
- Component.id: partial
- Component.name: partial
- Component.interface: partial
- Component.evidence: partial
- Outcome.id: partial
- Outcome.status: extractable
- Outcome.window: partial
- Outcome.measurement: partial
- Outcome.evidence: partial
- Scar.id: partial
- Scar.root_cause: partial
- Scar.detection_signature: partial
- Scar.guard_action: partial
- Scar.severity: partial
- EvidenceRef.hash: absent
- EvidenceRef.uri: absent
- EvidenceRef.kind: extractable
- EvidenceRef.reverification: partial

field_counts: extractable=7, partial=40, absent=4

## disposition
The probe is intentionally feasibility-only. A NO-GO means the sealed disposition records do not carry enough structured SAEOS-1 §4.3 material to justify building a lossless extractor from these records alone; it does not invalidate the underlying Gate seals.
