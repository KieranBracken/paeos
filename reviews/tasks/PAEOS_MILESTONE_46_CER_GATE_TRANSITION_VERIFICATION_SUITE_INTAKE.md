# Milestone 46 — CER Gate Transition Verification Suite

**Milestone:** 46 of 48
**Status:** **OPEN / QUEUED**
**Opened:** 2026-09-04
**Predecessor:** Milestone 45 `[SAKG TASK 21]` / Taxonomy Node Hierarchy Subsumption
**Owner boundary:** PAEOS ceremony and Court transition verification (runtime boundary)

## Objective

Specify and verify the CER gate-transition contract at the PAEOS runtime boundary. The suite must
demonstrate that valid ceremony obligations transition through the authorized gate sequence, while
unknown, incomplete, contradictory, or out-of-order transitions fail closed. Verification must
cover the Trace-A to warranted Trace-B hand-off, obligation discharge state, Court decision
binding, and the absence of implicit promotion or claim-scope widening.

This is a verification-suite intake, not a new lifecycle state or a replacement for the canonical
L01–L19 Engineering Lifecycle. The implementation must remain subordinate to the lifecycle and
CER doctrine.

## Deliverables and acceptance

- A candidate-bound CER gate transition specification and implementation/test changes in an
  isolated SoftLoop state root; no host-source adoption is implied by this intake.
- Focused tests for: valid ordered transitions; duplicate/idempotent observations; missing or
  contradictory obligations; invalid transition ordering; unknown gate/depth values; fail-closed
  remand behavior; Trace-A → warranted Trace-B hand-off; and deterministic replay/digests.
- Evidence that gate transitions preserve state independence: PAEOS owns canonical task/history/
  tool/diff/debt state, while models remain stateless compute.
- Candidate commit, reproducible local Court evidence, and an independent Layer 14/17 physical
  audit with `BuilderFamily != AuditorFamily` (A-08) before any completion disposition.
- Documentation of any non-blocking auditor finding without silently normalizing, widening, or
  deleting it.

## Boundary and dependency rules

- CER gate verification is a PAEOS runtime responsibility. SAKG remains authoritative for
  engineering taxonomy and claim promotion; Concept OS candidates are inputs/references only.
- The suite may consume ceremony contracts and Court evidence, but may not mutate SAKG claims,
  copy raw corpus material, or cause provider/transport/promotion side effects.
- Permitted direction is Supervisor/Antigravity → PAEOS policy/router → gateway/provider for an
  explicitly authorized audit; models do not own canonical state or gate authority.
- Unknown or unverifiable evidence must halt/remand; zero-remand execution is not an acceptance
  criterion.

## Execution constraints

- Execute only in an isolated SoftLoop state root and preserve the host branch and protected refs.
- No provider transmission, retry, fallback, promotion, merge, or main/trunk mutation is
  authorized by this intake. A physical audit requires a separate explicit Founder authorization.
- The existing legacy `PAEOS_INTAKE_M46_*` records describe an older, unrelated sequence and are
  retained as historical artifacts. This file is the canonical current M46 intake.
- Milestone 46 remains **OPEN / QUEUED** until its candidate evidence, physical audit, and
  Founder/Court disposition are all present and mechanically qualified.
