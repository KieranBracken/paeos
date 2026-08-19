# PAEOS — CURRENT STATE (persistent agent handoff)

> **Purpose:** single durable handoff for any agent/session resuming work on PAEOS.
> **Rule:** update this file at every significant state change. If your context was
> compacted, THIS FILE is your ground truth — do not reconstruct state from memory.
> **Last updated:** 2026-08-19 (late)

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

## 2. Key documents (read these first, in order)

| File | What it is |
|---|---|
| `operations/ENGINEERING_LIFECYCLE.md` | **THE CANONICAL L01–L19 BASELINE (v1.3).** Authoritative lifecycle doctrine; CER-1..6; amendment authority = L19 + founder. Read first. |
| `operations/WORKFLOW_STATE_MACHINE.yaml` | Machine-executable **form** of the Engineering Lifecycle (derived, subordinate). Prose EL wins on conflict. |
| `operations/archive/PAEOS_19_LAYER_LIFECYCLE_EXTRACTION_v1.md` | Archived **derived verbatim extraction** (former "Canonical Freeze"). No independent authority; see its status header. |
| `operations/archive/PAEOS_19_LAYER_FREEZE_DRAFT_v1.md` | Archived **superseded draft** with invalid source hashes. Historical only. |
| `operations/PAEOS_TWO_AXIS_CONFORMANCE_MAP_v1.md` | Lifecycle conformance × autonomy rung. Verdict: **R4-ALIGNED, NOT R4-CONFORMANT**. |
| `operations/PAEOS_CONFORMANCE_MAP_2_1_ADDENDUM.md` | Capability/transition split, C-01/C-02 resolution, seal-terminology. |
| `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` | Entries 139–146 = this program's audit trail (146 = source-hierarchy reconciliation). |
| `MessyChangesNeedsReview.md` | All code changes logged for human review. |

## 3. Approved next sequence (DO NOT REORDER)

> **2026-08-19 reconciliation:** C-01a/b/c, C-02, and seal terminology are now **mechanically
> resolved by the corrected source hierarchy** (Engineering Lifecycle v1.3 is the canonical
> baseline; the WSM is its derived form; prose wins; ratified amendments win where they apply).
> No founder adjudication is required for them — see Entry 146 and `proposals/PAEOS-IP-0014`.
> The sequence is therefore re-expressed from RB-CEREMONY-DEPTH-001 onward:

1. **RB-CEREMONY-DEPTH-001** (research) — extract the exact ceremony-depth contract from the
   Engineering Lifecycle (`(verifiability × reversibility)`, Trace-A/B, auto-discharge rule):
   D1 doctrine extraction is produced first (no founder design decision needed — the doctrine exists).
2. Implement canonical **L02 ceremony contract** + **Trace-A discharge evidence stubs** (K1).
3. Runtime executes the **ceremony-resolved obligation graph** — NOT more hard-coded
   SoftLoop stages.
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
