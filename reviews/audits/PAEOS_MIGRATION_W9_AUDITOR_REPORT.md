Candidate SHA: aa09fa76204ab7e8be8f83c1d014617fae19c4a7
Evidence Bundle SHA-256: b5390927896960537573851cc8df35ba6d1c61127b3e5d99ccca2aa6d1718d7f
L14_STATUS: PASS
INVARIANT: All 8 court claims evaluated in court-run-w9-20260906-011257 passed with zero unmet claims and complete evidence hash integrity under explicit Founder Ratification.
REPRODUCTION: Deterministic execution commands for all 8 claims returned exit code 0 and produced stdout matching expected results exactly.
Worker: Admitted: 0 | Rejected: 1 | Remediated: 0
Court: Sealed: 0 | Remanded: 0 | Remediated: 0

### Audit Findings

1. **Substantive Claim Verification (court-run-w9-20260906-011257)**:
   - **CLAIM-W9-01-RECURSIVE-LEARNING-SHADOW-TRACE**: Verified fully traceable 7-step recursive learning shadow proof and replay provenance via pytest contract execution. Expected and actual stdout matched (`RECURSIVE_LEARNING_SHADOW_TRACE_PASS`).
   - **CLAIM-W9-02-ZERO-CRITICAL-DATA-LOSS-ANOMALIES**: Confirmed duplicate mission/candidate quarantine isolation and fail-closed provider outage routing. Expected and actual stdout matched (`ZERO_CRITICAL_DATA_LOSS_ANOMALIES_PASS`).
   - **CLAIM-W9-03-FAILOVER-AND-STALE-PROJECTION-RECOVERY**: Validated break-glass direct PAEOS entry, stale projection rejection, and Orca outage recovery. Expected and actual stdout matched (`FAILOVER_AND_STALE_PROJECTION_RECOVERY_PASS`).
   - **CLAIM-W9-04-FOUNDER-GATE-ENFORCEMENT**: Verified hard Founder Gate strictly blocking unratified authority cutovers and rehearsing rollback. Expected and actual stdout matched (`FOUNDER_GATE_ENFORCEMENT_PASS`).
   - **CLAIM-W9-05-CANARY-DISCRIMINATION**: Demonstrated non-vacuous court evidence discrimination by verifying that invoking `activate_live_cutover('')` on `OrcaMissionControlAdapter` actively raises `FounderAuthorityGateLockedError`.
   - **CLAIM-W9-06-PAID-ROUTING-PROHIBITED**: Verified fail-closed prohibition on pay-per-token routing guaranteeing $0 marginal cost leakage (`PAID_ROUTING_PROHIBITED_PASS`).
   - **CLAIM-W9-07-SENTIUM-QUARANTINE-AND-NO-CAPITAL-PRESERVED**: Confirmed Sentium candidate admission strictly enforces quarantine-only boundary (`quarantine_only=True`) and strictly prohibits capital state and trade execution directives (`SENTIUM_QUARANTINE_AND_NO_CAPITAL_PRESERVED_PASS`).
   - **CLAIM-W9-08-FOUNDER-RATIFIED-CUTOVER-ACTIVE**: Verified Founder-ratified live authority cutover is active with token `FOUNDER-RATIFY-W9-AUTHORITY-CUTOVER-20260906T020813`, valid persistence to disk, and restored gate state (`FOUNDER_RATIFIED_CUTOVER_ACTIVE_PASS`).

2. **Verdict & Integrity**:
   - The court run artifact (`86ed3fbadbafb10b3726acf627bc34f1698263adc92858710ff0ab140f22076c`) has a verdict of `PASS` with 0 unmet claims across 8 total evaluated claims.
   - Physical A-08 heterogeneous auditor separation is satisfied: Builder family `gpt` (`gpt-5.6-sol` via Codex) != Auditor family `gemini` (`gemini-3.6-flash` via Google).

AUDIT_COMPLETE: true