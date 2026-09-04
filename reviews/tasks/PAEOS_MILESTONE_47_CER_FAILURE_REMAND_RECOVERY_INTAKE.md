# Milestone 47 — CER Failure & Remand Recovery

**Milestone:** 47 of 48
**Status:** **OPEN / QUEUED**
**Opened:** 2026-09-04
**Predecessor:** Milestone 46 `[I-CER-GATE-TRANSITION]` / L02-G1 CER Gate Transition Verification Suite
**Owner boundary:** PAEOS runtime failure handling, Court remand, and recovery state

## Objective

Specify and verify the fail-closed recovery contract for CER failures and Court remands. A
rejected or non-reproducible artifact must remain visible as immutable evidence, produce a typed
remand reason and debt/recovery record, and permit only an explicitly bounded corrective run. A
recovery must not erase prior observations, widen claims, bypass the Court, or silently retry or
fall back across providers.

## Required behavior

1. Preserve append-only observations, evidence, ledger heads, remand reasons, and debt records
   across a failed run and its corrective run.
2. Classify missing, stale, non-reproducible, vacuous, contradictory, and adversary-blocked
   artifacts with deterministic machine-readable reasons.
3. Permit a new isolated attempt only with an explicit intake and bounded write scope; reject
   unauthorized retry, fallback, promotion, merge, or protected-ref mutation.
4. Bind recovery decisions to the original candidate/evidence and the Court decision; ensure a
   corrected seal cannot mask or rewrite the remand chronology.
5. Demonstrate PAEOS-owned canonical recovery state and model statelessness, including restart
   and duplicate recovery observations.

## Deliverables and acceptance

- Runtime/Court implementation and focused tests produced through an isolated SoftLoop state root
  under `/private/tmp/paeos-m47-cer-recovery-run`.
- Tests for typed remand reasons, append-only debt/evidence preservation, deterministic recovery
  digests, duplicate recovery idempotence, fail-closed unauthorized retries/fallbacks, and
  successful bounded recovery after a valid corrective artifact.
- Candidate-bound deterministic Court evidence and an independent heterogeneous Layer 14/17 audit
  pair with `BuilderFamily != AuditorFamily` (A-08).
- Existing CER gate, ceremony, Court, and runtime regression suites remain compatible; any
  environment-sensitive failures are reported rather than hidden.
- Any auditor finding is recorded without deletion, claim widening, or zero-remand optimization.

## Boundary and dependency rules

- Recovery is a PAEOS runtime/Court responsibility. SAKG remains authoritative for taxonomy and
  claim promotion; Concept OS, corpus/KAE, provider, and transport layers are not modified.
- Models are stateless compute. Canonical task/history/tool/diff/evidence/debt state remains local
  to PAEOS and is persisted by the active state root.
- Unknown or unverifiable recovery evidence halts/remands; a remand is healthy back-pressure and
  not a failure of the safety machinery.

## Execution constraints

- Execute only in an isolated SoftLoop state root and candidate clone; do not mutate protected host
  branches directly.
- No provider transmission, retry, fallback, promotion, merge, or main/trunk mutation is
  authorized by this intake. Physical audit requires separate explicit Founder authorization.
- Milestone 47 remains **OPEN / QUEUED** until candidate evidence, physical audit, and a separate
  Founder/Court disposition are present and mechanically qualified.
