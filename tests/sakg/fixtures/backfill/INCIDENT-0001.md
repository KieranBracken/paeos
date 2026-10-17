# INCIDENT-0001 — Historical timeout evidence

decision_id: sakg://paeos-recovery/Decision/01J00000000000000000000F01
Status: **observed**

## Observation

The historical bridge timeout record is retained as a candidate Outcome input.

## Resolution

The S3 automatic outcome loop must independently observe whether the Decision held; this record is
hand-attributed and is not proof of a current runtime state.

## Risk

The record may be incomplete; consumers must retain its source hash and candidate status.
