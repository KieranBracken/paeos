# PAEOS Two-Axis Conformance Map v1.0

> **Source-hierarchy note (2026-08-19):** the canonical L01–L19 obligation source is
> `operations/ENGINEERING_LIFECYCLE.md` (v1.3), not any "Freeze" document. The verbatim
> corpus used here is the archived derived extraction
> `operations/archive/PAEOS_19_LAYER_LIFECYCLE_EXTRACTION_v1.md` (a byte-faithful copy of the
> EL + its WSM form). Where the EL prose and the derived WSM YAML differ, the **EL prose wins**.
> See `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` Entry 146. (Revision of this map's reliance on the
> invalid "Freeze"-as-authority framing.)

Date: 2026-08-19 (Baseline Analysis) · Ratified Update: 2026-09-05 (Formal R4 Conformance Closure) · Canonical obligations from `ENGINEERING_LIFECYCLE.md` v1.3.

Method: canonical obligations from the Engineering Lifecycle (per the verbatim extraction in
`operations/archive/PAEOS_19_LAYER_LIFECYCLE_EXTRACTION_v1.md`) are compared against
implementation facts verified 2026-08-19 and formally closed 2026-09-05 (file:line citations below). Two ORTHOGONAL axes per the
founder's directive: (1) lifecycle conformance per layer; (2) autonomy-rung (R1–R5) readiness.
Status as of 2026-09-05: **R4-CONFORMANT** (L02 ceremony-depth assignment,
lawful Trace-A discharge evidence stubs, L06->L07 mitigation ordering, A-08 fail-closed multi-family decorrelation,
durable L17/L18 persistence, and end-to-end self-hosted Trace-A/Trace-B execution verified).

Status vocabulary: CONFORMANT_EXECUTED · CONFORMANT_DISCHARGED · DISCHARGEABLE_BUT_EVIDENCE_MISSING
· WRONG_DEPTH_CLASSIFICATION · PARTIAL · BYPASSED · MISPLACED · MISSING · IMPLEMENTATION_EXTENSION
· CANONICAL_CONFLICT · UNKNOWN

## Axis 1 — Lifecycle conformance (L01–L19)

| Layer | Canonical obligation (Engineering Lifecycle v1.3) | Implemented component | Reachable? | Status | Rung | Remediation class |
|---|---|---|---|---|---|---|
| L01 Intake | Record objective, classify provenance | `Intake` contract in `runtime/orchestrator/__init__.py`; ledger `GOAL_CREATED` rows | yes (runner) | CONFORMANT_EXECUTED — typed intake contract, write scopes, evidence binding, provenance | R3/R4 | Closed |
| L02 Triage | Weight class + **ceremony depth (v×r)** → Run Ceremony Contract | `runtime/triage.py` ($v \times r$ classification) + `runtime/ceremony.py` (`CeremonyContract`) | yes | CONFORMANT_EXECUTED — depth assignment and run ceremony contract operational | R4 | Closed |
| L03 Re-Derivation | First-principles re-derivation after L02 disposition | `FRONTEND_PLANNER_STAGES` (`StageId.RE_DERIVE`) | yes | CONFORMANT_DISCHARGED (Trace-A stub emitted) / CONFORMANT_EXECUTED (Trace-B) | R4 | Closed |
| L04 Ideation | Candidate generation | `FRONTEND_PLANNER_STAGES` (`StageId.IDEATE`) | yes | CONFORMANT_DISCHARGED (Trace-A stub emitted) / CONFORMANT_EXECUTED (Trace-B) | R4 | Closed |
| L05 Frontier Research | Research, prior art | `FRONTEND_PLANNER_STAGES` (`StageId.RESEARCH`) | yes | CONFORMANT_DISCHARGED (Trace-A stub emitted) / CONFORMANT_EXECUTED (Trace-B) | R4 | Closed |
| L06 Trade-off Analysis | Explicit trade-off matrix | `FRONTEND_PLANNER_STAGES` (`StageId.TRADEOFF`) | yes | CONFORMANT_DISCHARGED (Trace-A stub emitted) / CONFORMANT_EXECUTED (Trace-B: substantive execution preceding L07) | R4 | Closed |
| L07 Mitigation | Mitigate analyzed trade-offs | `FRONTEND_PLANNER_STAGES` (`StageId.MITIGATION`) chained after TRADEOFF | yes | CONFORMANT_DISCHARGED (Trace-A stub emitted) / CONFORMANT_EXECUTED (Trace-B: monotonic input context from L06) | R4 | Closed |
| L08 System Design | Design artifact | `FRONTEND_PLANNER_STAGES` (`StageId.DESIGN`) | yes | CONFORMANT_DISCHARGED (Trace-A) / CONFORMANT_EXECUTED (Trace-B substantive) | R3/R4 | Closed |
| L09 Multi-Perspective Critique | Critique of design | `FRONTEND_PLANNER_STAGES` (`StageId.CRITIQUE`) | yes | CONFORMANT_DISCHARGED (Trace-A) / CONFORMANT_EXECUTED (Trace-B) | R3/R4 | Closed |
| L10 Adversarial Design Review | Attack the DESIGN pre-implementation | `FRONTEND_PLANNER_STAGES` (`StageId.ADVERSARIAL_REVIEW`) | yes | CONFORMANT_DISCHARGED (Trace-A) / CONFORMANT_EXECUTED (Trace-B) | R4 | Closed |
| L11 Formal Planning | Implementation contract incl. test strategy/acceptance | `FRONTEND_PLANNER_STAGES` (`StageId.PLAN`) | yes | CONFORMANT_DISCHARGED (Trace-A) / CONFORMANT_EXECUTED (Trace-B) | R4 | Closed |
| L12 Branch Implementation | Scoped implementation | `StageId.IMPLEMENT` on plan write_scopes, sandboxed workspace, ScopeViolation enforcement | yes | CONFORMANT_EXECUTED | R3/R4 | Closed |
| L13 Verification | Verify claims vs artifact (EL: "Auditor/Runtime (mechanical) + Adversary"; "mechanical evidence is self-approving via EXEC signature"; A-09 independent evidence) | Deterministic Court: re-executes commands, evidence binding, CANARY-0002 vacuity gate (`runtime/verification.py`, orchestrator §court) | yes | **CONFORMANT_EXECUTED** — Court is a faithful implementation of EL L13 prose (mechanical, self-approving, independent). | R3/R4 | Closed |
| L14 Independent Audit | Post-build audit, **model-family decorrelation (A-08)** | `ReviewHarness` over sealed bundle + `A08Enforcer` fail-closed check (`runtime/worker_admission.py`, `paeos/model_router/`) | yes | CONFORMANT_EXECUTED — `HybridRuntime` decorrelation operational; fail-closed on same-family | R4 | Closed |
| L15 Documentation & Ledger | Immutable record, promotion docs | Append-only hash-chained ledger + `SealRecord` + model attribution | yes | CONFORMANT_EXECUTED | R4 | Closed |
| L16 Promotion Decision | Promote/supersede decision | `SealAuthority` with `promote_to` field, promotion controller | yes | CONFORMANT_EXECUTED | R4 | Closed |
| L17 Retrospective | Post-run retrospective | `RetrospectiveEngine` (CAS-bound report, gate-routed) + `EvolutionLayer` emitting ledger events | yes | CONFORMANT_DISCHARGED (Trace-A stub emitted) / CONFORMANT_EXECUTED (Trace-B: `EVOLUTION_EVENT` rows) | R4 | Closed |
| L18 Knowledge Extraction | Scars written & re-injected | `SqliteScarStore` durable SQLite store on disk (`runtime/scar_store.py`) + `EvolutionLayer` emitting ledger events | yes | CONFORMANT_DISCHARGED (Trace-A stub emitted) / CONFORMANT_EXECUTED (Trace-B: durable scars on disk) | R4 | Closed |
| L19 Constitutional Evolution | Amendment only through hard loop | `runtime/amendment.py`: kernel classifies blast radius, isolated adversary attacks diff, HALTS at founder signature; autonomous trigger on KERNEL_TOUCHING | yes | CONFORMANT_EXECUTED | R4 | Closed |

## Axis 2 — Autonomy rung assessment

- **R1 Recorded** — MET (ledger, CAS, transcripts).
- **R2 Assisted** — MET (B1 Soft-Loop milestone, historical).
- **R3 Supervised autonomy** — MET: supervised dogfooding runs exercised dispatch,
  evidence, court, adversary, seal, attribution under founder supervision; gates genuinely
  fail-closed.
- **R4 Self-hosting** — **R4-CONFORMANT ESTABLISHED (2026-09-05).** All 7 canonical blockers formally closed and verified:
  1. L02 ceremony-depth classification + Run Ceremony Contract: CLOSED (`runtime/ceremony.py`, `runtime/triage.py`);
  2. Trace-A discharge stub emission (K1: all 11 auto-discharge transitions carry evidence): CLOSED;
  3. L06/L07 orphan resolution (TRADEOFF L06 precedes MITIGATION L07 with forward artifact chaining): CLOSED;
  4. L14 A-08 decorrelation (A08Enforcer fails closed on same-family, HybridRuntime decorrelation): CLOSED;
  5. L18 durable scar store + L17 evolution ledger events (SqliteScarStore, EVOLUTION_EVENT rows): CLOSED;
  6. L15/L16 documentation + promotion machinery (SealAuthority, PromotionController): CLOSED;
  7. Live end-to-end Trace-A and Trace-B runs verified green across 722 runtime tests, 144 model router tests, and 224 kernel tests: CLOSED.
- **R5 Autonomous** — INITIATED / PRE-CONDITIONS MET (requires sustained multi-turn operation under R4-conformant governance).

## Remediation register

**IMPLEMENTATION REMEDIATIONS (no legislation):** All 5 items completed and verified (L02 ceremony classification, Trace-A K1 stubs, L06->L07 input ordering, durable SQLite scar store, evolution events to ledger).

**R4 READINESS GAPS:** All 7 items closed and verified. A-08 generic model family decorrelation enforced fail-closed.

**CANONICAL CONFLICTS — RESOLVED MECHANICALLY BY HIERARCHY (2026-08-19):** the former
C-01a/C-01b/C-01c prose-vs-YAML divergences, C-02 secondary-source numbering, and seal
terminology are now resolved by the corrected source hierarchy — `ENGINEERING_LIFECYCLE.md` (v1.3)
prose wins over the derived WSM YAML unless a ratified amendment states otherwise; secondary
sources (backlog/IP reconstructions) are excluded by precedence; SealRecord (attestation) ≠ L16
Seal disposition. No founder adjudication required. See Entry 146 and `proposals/PAEOS-IP-0014`
for the one optional L13 ratification candidate. The genuinely-open ceremony *edge cases*
(how v×r is evaluated, escalation, de-escalation, substantive-vs-discharge) remain in
RB-CEREMONY-DEPTH-001 (research), not in a freeze conflict register.

**CANDIDATE IMPROVEMENTS (L19 path):** TDD baseline-failing contract strengthening L11 + L13
court-verified FAIL→PASS delta (no new state — CER v1.1 "add no state"); ratify deterministic
Court semantics if adjudicated a material improvement.

**HISTORICAL EVIDENCE DEFECTS (separate queue, evidence-driven disposition):** 24 vacuous seals
(uphold/annotate/supersede/revalidate/quarantine per evidence, NOT pre-dispositioned); 99 tainted
court rows (taint index active); zero historical evolution events.

**ADE / MISSION_CONTROL re-evaluation:** founding justification rested on the withdrawn
"accrete all StageIds" narrative. Unwired today; re-evaluate whether any L05/L06 capability is
still needed once stub machinery + ceremony contract exist, before retaining or retiring.

## Verified fact base (citations)

- **Planner chain:** executes `FRONTEND_PLANNER_STAGES` ordered as `RE_DERIVE (L03) → IDEATE (L04) → RESEARCH (L05) → TRADEOFF (L06) → MITIGATION (L07) → DESIGN (L08) → CRITIQUE (L09) → ADVERSARIAL_REVIEW (L10) → PLAN (L11)` then `IMPLEMENT (L12)` — `runtime/orchestrator/__init__.py`. Chaining is forward and monotonic.
- **Ceremony contract & discharge stubs:** `runtime/ceremony.py` (`CeremonyContract`, `DischargeStub`, `ceremony_for()`); `runtime/triage.py` ($v \times r$ depth assignment, `Trace.A`/`Trace.B`); `runtime/orchestrator/__init__.py` (`_record_discharges` emits canonical `LAYER_DISCHARGED` rows `{layer, result: auto_pass, reason: trace_a, by: runtime}` for all 11 discharged layers L03–L11, L17, L18).
- **A-08 Decorrelation:** `paeos/model_router/a08_enforcer.py` (`A08Enforcer`), `runtime/worker_admission.py` (`enforce_receipt_decorrelation`), `runtime/integrations/hybrid.py` (`HybridRuntime`). Fails closed on same or unknown model families.
- **Durable evolution persistence:** `runtime/scar_store.py` (`SqliteScarStore` with state-dir SQLite WAL `scars.db`); `runtime/evolution.py` (`EvolutionLayer` writes retrospective reports to CAS, records scars to SQLite, emits `EVOLUTION_EVENT` rows to ledger).
- **Physical regression verification (2026-09-05):**
  - `tests/runtime/`: **722 / 722 passed in 27.78s**
  - `tests/model_router/`: **144 / 144 passed in 4.86s**
  - `tests/kernel/`: **224 / 224 passed in 19.32s**
  - `tests/concept/`: **173 / 173 passed in 1.36s**
  - Linters: Ruff clean (0 errors), Pyright clean (0 errors across runtime, kernel, paeos, concept), AST linter clean (0 violations).
- **Canonical obligation source:** `operations/ENGINEERING_LIFECYCLE.md` (v1.3); verbatim extraction archived at `operations/archive/PAEOS_19_LAYER_LIFECYCLE_EXTRACTION_v1.md`; EL prose wins over derived WSM.

*End of conformance map v1.0 (Ratified R4-CONFORMANT: 2026-09-05).*
