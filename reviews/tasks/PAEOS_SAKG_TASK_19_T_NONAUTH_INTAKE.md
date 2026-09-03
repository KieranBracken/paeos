# SAKG Task 19 — `[T-NONAUTH]` Canonical Intake

Source: item 18 of `ops/backlogs/sakg-1-intakes.json`.

**Objective:** Conformance tests for structural non-authority guarantees: no mutating method
reachable from consumer capabilities; every result carries `trust=untrusted` and a
`SUMMARY`/`INDEX` tier; SAKG can mint only `EvidenceRef`, never `Evidence`; and PAEOS core
does not import `sakg`.

## Deliverables and acceptance

- `tests/sakg/test_nonauthority.py`
- `tests/sakg/test_nonauthority_no_mutating_egress.py`
- `tests/sakg/test_nonauthority_no_evidence_minting.py`
- `tests/sakg/test_poisoned_corpus_cannot_gate.py`
- Focused tests and boundary checks:
  - `uv run pytest tests/sakg/test_nonauthority.py -q`
  - `uv run pytest tests/sakg/test_nonauthority_no_mutating_egress.py -q`
  - `uv run pytest tests/sakg/test_nonauthority_no_evidence_minting.py -q`
  - `uv run pytest tests/sakg/test_poisoned_corpus_cannot_gate.py -q`
  - `! rg -q 'import sakg|from sakg' kernel/ runtime/ cli/`
  - `uv run pyright sakg/`

Execution is queued for a fresh isolated SoftLoop state root. No Task 19 implementation or
seal is claimed by this intake.
