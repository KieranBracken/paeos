# PAEOS Two-Axis Conformance Map v1.0

Date: 2026-08-19 · Read-only analysis (Step 2) · Companion to `PAEOS_CANONICAL_19_LAYER_FREEZE_v1.md`

Method: canonical obligations extracted in the Freeze (Part A/B verbatim) are compared against
implementation facts verified 2026-08-19 (file:line citations below). Two ORTHOGONAL axes per the
founder's directive: (1) lifecycle conformance per layer; (2) autonomy-rung (R1–R5) readiness.
Current dogfooding is labeled **R4-ALIGNED, NOT R4-CONFORMANT** until L02 ceremony assignment,
lawful Trace-A discharge evidence, required L12–L16 execution, and applicable gates are
demonstrated. A-08 is treated generically (model-family decorrelation — never vendor-locked).
No code was modified; no conflicts resolved; nothing preserved merely by existing.

Status vocabulary: CONFORMANT_EXECUTED · CONFORMANT_DISCHARGED · DISCHARGEABLE_BUT_EVIDENCE_MISSING
· WRONG_DEPTH_CLASSIFICATION · PARTIAL · BYPASSED · MISPLACED · MISSING · IMPLEMENTATION_EXTENSION
· CANONICAL_CONFLICT · UNKNOWN

## Axis 1 — Lifecycle conformance (L01–L19)

| Layer | Canonical obligation (Freeze) | Implemented component | Reachable? | Status | Rung | Remediation class |
|---|---|---|---|---|---|---|
| L01 Intake | Record objective, classify provenance | `ops/autonomous_run.py` backlog.json intake; ledger GOAL_CREATED rows | yes (runner) | PARTIAL — intake is external/manual; objective recorded but no intake artifact bundle | R3 | Implementation remediation |
| L02 Triage | Weight class + **ceremony depth (v×r)** → Run Ceremony Contract | `runtime/triage.py` (ROUTINE/SUBSTANTIAL/KERNEL_TOUCHING + budget only); **zero ceremony/discharge code repo-wide** (grep: 0 hits) | yes | PARTIAL — depth assignment and ceremony contract absent | R4 | **R4 readiness gap** |
| L03 Re-Derivation | First-principles re-derivation after L02 disposition | no orchestrator path | no | DISCHARGEABLE_BUT_EVIDENCE_MISSING (Trace-A) / MISSING (Trace-B) — no stubs emitted | R4 | R4 readiness gap (stub emission) |
| L04 Ideation | Candidate generation | none anywhere | no | DISCHARGEABLE_BUT_EVIDENCE_MISSING / MISSING — no stubs | R4 | R4 readiness gap |
| L05 Frontier Research | Research, prior art | `runtime/ade.py` (unwired); research-backlog prompt allowance | no | DISCHARGEABLE_BUT_EVIDENCE_MISSING / MISSING; ADE is IMPLEMENTATION_EXTENSION pending re-evaluation | R4 | R4 readiness gap + ADE re-evaluation |
| L06 Trade-off Analysis | Explicit trade-off matrix | `runtime/ade.py` TRADEOFF (unwired) | no | DISCHARGEABLE_BUT_EVIDENCE_MISSING / MISSING | R4 | R4 readiness gap |
| L07 Mitigation | Mitigate analyzed trade-offs | `StageId.MITIGATION` runs FIRST in planner loop (`runtime/orchestrator/__init__.py` §planner) | yes | MISPLACED — executes with no TRADEOFF artifact (orphan input); Trace-A stub would satisfy | R3/R4 | Implementation remediation |
| L08 System Design | Design artifact | `StageId.DESIGN` | yes | CONFORMANT_EXECUTED (substantive; run 7 evidence) | R3 met | — |
| L09 Multi-Perspective Critique | Critique of design | `StageId.CRITIQUE` | yes | CONFORMANT_EXECUTED | R3 met | — |
| L10 Adversarial Design Review | Attack the DESIGN pre-implementation | no design-phase adversary | no | DISCHARGEABLE_BUT_EVIDENCE_MISSING (Trace-A) / MISSING (Trace-B) | R4 | R4 readiness gap |
| L11 Formal Planning | Implementation contract incl. test strategy/acceptance | `StageId.PLAN` | yes | CONFORMANT_EXECUTED, but contract lacks mandated baseline-failing suite field | R4 | CANDIDATE IMPROVEMENT (L19 amendment) |
| L12 Branch Implementation | Scoped implementation | `StageId.IMPLEMENT` on plan write_scopes, sandboxed workspace, ScopeViolation enforcement | yes | CONFORMANT_EXECUTED | R3 met | — |
| L13 Verification | Verify claims vs artifact | Deterministic Court: re-executes commands, evidence binding, vacuity gate (`runtime/verification.py`, orchestrator §court) | yes | CONFORMANT_EXECUTED — run 7 genuinely REMANDED; deterministic semantics possibly stronger than canonical VERIFY text → recorded as CANONICAL_CONFLICT C-01 sub-item, not resolved here | R3/R4 | Candidate improvement (ratify via L19) |
| L14 Independent Audit | Post-build audit, **model-family decorrelation (A-08)** | post-build ADVERSARIAL_REVIEW over sealed bundle + evidence | yes | PARTIAL — machinery real (fail-closed BLOCK/REMAND), but single-family window (GLM-5.3 builder+auditor) violates A-08 decorrelation; `HybridRuntime` provides generic decorrelation when a second family is available | R4 | R4 readiness gap |
| L15 Documentation & Ledger | Immutable record, promotion docs | append-only hash-chained ledger + seal; model attribution rows (2026-08-18); sidecar stage scores | yes | PARTIAL — ledger strong; documentation/promotion notes not automated | R4 | R4 readiness gap |
| L16 Promotion Decision | Promote/supersede decision | `promote_to` field in seal payloads (null in all 25 seals) | partial | PARTIAL — field exists, decision machinery absent | R4 | R4 readiness gap |
| L17 Retrospective | Post-run retrospective | `EvolutionLayer.run()` invoked by `ops/autonomous_run.py` post-run | yes | PARTIAL / DISCHARGEABLE_BUT_EVIDENCE_MISSING — zero evolution ledger events ever recorded; no stubs | R4 | R4 readiness gap |
| L18 Knowledge Extraction | Scars written & re-injected | ScarStore **in-memory default**; durable SQLite store = RB intake 1 (runs 5–7 REMANDED/HALTED — not yet delivered); zero durable scars on disk | partial | DISCHARGEABLE_BUT_EVIDENCE_MISSING / MISSING persistence | R4 | R4 readiness gap (RB intake 1) |
| L19 Constitutional Evolution | Amendment only through hard loop | `runtime/amendment.py`: kernel classifies blast radius, isolated adversary attacks diff, HALTS at founder signature (A-2/A-5); RB-0008 friction detection | yes | CONFORMANT_EXECUTED (machinery, tested); never yet triggered autonomously | R4 | R4 readiness gap (prove one autonomous trigger) |

## Axis 2 — Autonomy rung assessment

- **R1 Recorded** — MET (ledger, CAS, transcripts).
- **R2 Assisted** — MET (B1 Soft-Loop milestone, historical).
- **R3 Supervised autonomy** — SUBSTANTIALLY MET: supervised dogfooding runs 5–7 exercised dispatch,
  evidence, court, adversary, seal, attribution under founder supervision; gates genuinely
  fail-closed (run 7 court REMAND is the positive proof).
- **R4 Self-hosting** — **R4-ALIGNED, NOT ESTABLISHED.** Self-hosting mechanism present (own backlog,
  own gates). Canonical ceremony conformance incomplete. Blockers, in dependency order:
  1. L02 ceremony-depth classification + Run Ceremony Contract (enables everything below);
  2. Trace-A discharge stub emission (K1: transitions without evidence are invalid);
  3. L06/L07 orphan resolution (MITIGATION input);
  4. L14 A-08 decorrelation (any genuinely distinct model family);
  5. L18 durable scar store + L17 evolution ledger events;
  6. L15/L16 documentation + promotion machinery;
  7. one complete Trace-A run whose every discharged state has a stub, and (when warranted)
     one Trace-B run.
- **R5 Autonomous** — NOT BEGUN (by design; requires R4-conformant operation over time).

## Remediation register (founder-decision input)

**IMPLEMENTATION REMEDIATIONS (no legislation):** wire L02 ceremony classification; emit Trace-A
stubs; fix MITIGATION input ordering; durable scar store (RB intake 1); evolution events to ledger.

**R4 READINESS GAPS:** items 1–7 above; L14 decorrelation via existing HybridRuntime routing
(generic family rule — Builder family ≠ Auditor family, no specific vendor).

**CANONICAL CONFLICTS (founder adjudication):** C-01 prose-vs-YAML semantics (incl. deterministic
Court vs canonical VERIFY wording); C-02 secondary-source numbering (excluded by precedence);
C-03 ceremony-depth legality edge cases. See Freeze Part C — deliberately unresolved.

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

- Planner chain executes `MITIGATION → DESIGN → CRITIQUE → PLAN` then `IMPLEMENT` —
  `runtime/orchestrator/__init__.py` (§ planner loop, § builder).
- `grep -rcE 'ceremony|trace_a|TraceA|discharge' runtime/ kernel/ ops/` → **0 hits** (no depth machinery).
- `runtime/triage.py`: ROUTINE/SUBSTANTIAL/KERNEL_TOUCHING weight classes + Budget; no depth field.
- `kernel/types.py` `StageId`: 21 constants = 19 canonical states + RAW + terminal/restart mechanics.
- `runtime/ade.py` exists; no import from orchestrator/ops (unwired).
- Ledger kinds observed: goal, seal (148+ rows; +model attribution 2026-08-18); zero evolution rows.
- Scar persistence: in-memory default; no scar artifacts on disk; durable store = RB intake 1 in flight.
- Runs 5–7 (GLM-5.3 single-family window, GPT quota exhausted 2026-08-18→~08-22):
  run 7 REMANDED by court with per-stage `model_ver` attribution — gates proven real.
- Freeze v1.0 (this repo, `operations/`) anchors all canonical rows; hashes recorded therein.

*End of conformance map v1.0. No code modified during production of this document.*
