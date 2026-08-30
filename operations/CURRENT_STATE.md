# PAEOS — CURRENT STATE (persistent agent handoff)

> **Purpose:** single durable handoff for any agent/session resuming work on PAEOS.
> **Rule:** update this file at every significant state change. If your context was
> compacted, THIS FILE is your ground truth — do not reconstruct state from memory.
> **Last updated:** 2026-08-30 (isolated recovery debt-hardening checkpoint)

## 1. What just happened (session arc, condensed)

- Hallucination audit escalated into full architectural archaeology.
- **Contamination census:** 99/125 court evidence rows fabricated; 24/25 ledger seals vacuous
  (0-byte files + a `.DS_Store`); 1 legitimate seal (`r-5bf1dea3`, passed real GLM-5.3 review).
- **Root causes fixed + tested:** `ops/submit_evidence.py` fabrication defaults removed;
  codex invoker fail-loud (no silent provider fallback); court taint index
  (`.paeos_state/court/.tainted.json`, keyed by line-hash, skips tainted rows in
  `evidence_for`); ledger model attribution (`model_ver` per stage); Cline-native GLM-5.3
  invoker with per-stage thinking effort (DESIGN/PLAN/CRITIQUE/adversary=high,
  IMPLEMENT/MITIGATION=medium).
- **Dogfooding runs 5–7:** PAEOS worked its own backlog (durable ScarStore intake).
  Run 7 = first fully legitimate full-chain run: model-attributed, real adversary,
  **court REMAND** (fail-closed gates working as designed).
- **Archaeology correction (the big one):** three vocabularies were conflated —
  canonical lifecycle phases (L01–L19), autonomy rungs (R1–R5), construction milestones
  (B0/B1/B2). SoftLoop = B1 proof vehicle for R2/R3. "Bolt all 19 layers into SoftLoop"
  was a later AI reconstruction, **never an original plan**.
- **Repo cleanup (2026-08-19):** clutter consolidated into `misc/` (nothing deleted).
  Superseded/duplicate docs renamed with `SUPERSEDED__` / `ARCHIVED_DERIVED__` prefixes.
  Auto-filed boilerplate RBs (RB-0011..0025, RB-0027..0030) moved to `misc/_autofiled_rbs/`.
- **Test suite (2026-08-19):** `test_selfhost.py` and `test_memory_lifetime_boundary.py`
  indentation bugs repaired. Suite now has exactly **1 pre-existing failure**
  (`test_root_submit_evidence_script` — wrong path, unrelated to ceremony work).

## 2. Key documents (read these first, in order)

| File | What it is |
|---|---|
| `operations/ENGINEERING_LIFECYCLE.md` | **THE CANONICAL L01–L19 BASELINE (v1.3).** Authoritative lifecycle doctrine; CER-1..6; amendment authority = L19 + founder. Read first. |
| `operations/WORKFLOW_STATE_MACHINE.yaml` | Machine-executable **form** of the Engineering Lifecycle (derived, subordinate). Prose EL wins on conflict. |
| `operations/archive/ARCHIVED_DERIVED__PAEOS_19_LAYER_LIFECYCLE_EXTRACTION_v1.md` | Archived derived verbatim extraction. No independent authority; see its status header. |
| `operations/archive/SUPERSEDED_DRAFT__PAEOS_19_LAYER_FREEZE_v1.md` | Archived superseded draft with invalid source hashes. Historical only. |
| `operations/PAEOS_TWO_AXIS_CONFORMANCE_MAP_v1.md` | Lifecycle conformance × autonomy rung. Verdict: **R4-ALIGNED, NOT R4-CONFORMANT**. |
| `operations/PAEOS_CONFORMANCE_MAP_2_1_ADDENDUM.md` | Capability/transition split, C-01/C-02 resolution, seal-terminology. |
| `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` | Entries 139–150 = full audit trail. Entry 147 = ceremony contract. Entries 148–150 = watchdog check-ins. |
| `MessyChangesNeedsReview.md` | All code changes logged for human review. |

## 3. Approved next sequence (DO NOT REORDER)

> **2026-08-19 reconciliation:** C-01a/b/c, C-02, and seal terminology are now **mechanically
> resolved by the corrected source hierarchy** (Engineering Lifecycle v1.3 is the canonical
> baseline; the WSM is its derived form; prose wins; ratified amendments win where they apply).
> No founder adjudication is required for them — see Entry 146 and `proposals/PAEOS-IP-0014`.
> The sequence is therefore re-expressed from RB-CEREMONY-DEPTH-001 onward:

1. **[DONE 2026-08-19] RB-CEREMONY-DEPTH-001** — canonical ceremony doctrine extracted to
   `backlog/research/PAEOS_RESEARCH_BACKLOGS_CEREMONY_TDD_v0.1/PAEOS_CEREMONY_DEPTH_DOCTRINE_EXTRACTION_v1.md`
   (D1). Doctrine exists in the EL; no founder design decision needed.
2. **[DONE 2026-08-19] L02 ceremony contract + Trace-A discharge evidence stubs (K1)** — implemented
   in `runtime/ceremony.py`, wired into `runtime/triage.py`, tested
   (`tests/runtime/test_ceremony_contract.py`). Implements EL/WSM law; no legislation. Unknown depth ⇒ Trace-B.
3. **Runtime executes the ceremony-resolved obligation graph** — walk `CeremonyContract.obligation_plan()`
   in the orchestrator and record each discharge stub (instead of hard-coding SoftLoop stages). **NEXT.**
4. **A-08 fail-closed** enforcement: `BuilderFamily ≠ AuditorFamily`, generic
   (never vendor-locked to GPT-5.6). Same-family audit must HALT/REMAND, never degrade.
5. Prove canonical Trace-A → warranted Trace-B → **R4 conformance decision**.
6. **(Candidate, awaiting founder)** ratify the deterministic Court as canonical L13 via
   `proposals/PAEOS-IP-0014` (implementation already exists; ratification is optional L19 blessing).

**Forbidden until L02 ceremony contract is done:** inventing a scoring algorithm for L02
ceremony assignment (legislating); deleting ADE/MISSION_CONTROL (frozen authority, re-evaluate); 
pre-decided disposition of the 24 vacuous seals; treating any Freeze file as primary L01–L19 authority.

## 4. Open items

- Run 7 remand reason not yet diagnosed (see `.paeos_state/court/r-7*.jsonl`, verdict in CAS).
- A-08 unmet during single-model GLM window (GPT quota reset ~2026-08-22).
- **Uncommitted work — commit to git immediately** (two docs were nearly lost to
  compaction this session; don't repeat that).

## 5. Ground rules that emerged this session

- Authority order: `ENGINEERING_LIFECYCLE.md` (v1.3, canonical L01–L19) > valid ratified amendments
  (IPs/A-series/ratified specs) > derived machine-executable form (WSM) > kernel invariants
  > implementation conformance > audit reports > AI opinions. Implementation NEVER redefines architecture.
  Archived "Freeze" files carry no authority.
- New requirement ≠ new architectural state (CER v1.1: "governs every state; add no state").
- TDD belongs in L11 contract + L13 court obligation, not a new StageId.
- Any doc produced by an agent must be verified on disk before reporting it done.
- 2026-08-30 isolated recovery checkpoint: commit `87a33067bff8ed23c68bbbd7042aea1da5181257`
  binds new L14 reports to their physical receipts and enforces caller-supplied canonical
  accounting; it also adds a state-root-local transaction lock and required prior-digest CAS.
  Focused checks and the full non-gateway suite (**955 passed**) are green, but DEBT-0059 and
  DEBT-0061 remain open pending their external repayment conditions. DEBT-0060 is traced to the
  legacy GUI monitor writing outside the injected bridge response path; the event-watchdog plan
  remains the approved remediation. Strict sealed progress is **12/48 complete | 36 remaining**;
  no Gate C seal, Gate D–G advancement, production dispatch, or SAKG resumption is authorized.
- 2026-08-30 event-watchdog candidate: commits `55000cf`, `53a96a5`, `b29f6ec`, `3f865a3`,
  `873f8c2`, and `0857a13` add monotonic liveness, typed read-only recovery decisions, fenced
  recovery application, storage back-pressure, and a run-once state-root-bound CLI; the legacy
  GUI monitor is disabled. Fresh non-gateway verification collected **995** and passed. This is
  not a gate seal: DEBT-0060 remains open pending the liveness fault matrix and independent
  L14/L17 evidence; strict sealed progress remains **12/48 complete | 36 remaining**.
- 2026-08-30 liveness fault matrix commit `e354bd9` passes the deterministic timeout, side-effect,
  projection, storage, process-death, and repeated-observation cases. This satisfies the local
  implementation proof only; DEBT-0060 remains open pending independent L14/L17 audit and canary
  authorization.
