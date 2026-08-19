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
| `operations/PAEOS_CANONICAL_19_LAYER_FREEZE_v1.md` | Frozen canonical L01–L19 corpus (verbatim, sha256-hashed). THE architecture authority. |
| `operations/PAEOS_TWO_AXIS_CONFORMANCE_MAP_v1.md` | Lifecycle conformance × autonomy rung. Verdict: **R4-ALIGNED, NOT R4-CONFORMANT**. |
| `operations/PAEOS_CONFORMANCE_MAP_2_1_ADDENDUM.md` | Capability/transition split, atomic conflicts, seal-terminology question. |
| `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` | Entries 139–145 = this program's audit trail. |
| `MessyChangesNeedsReview.md` | All code changes logged for human review. |

## 3. Approved next sequence (DO NOT REORDER)

1. **Founder (Bob) Step 3 decisions** — adjudicate atomic C-01 conflicts (L13 authority
   prose-vs-YAML, L15 role, artifact diffs), C-02 (secondary sources = stale, not
   constitutional), seal terminology (G-Seal vs L16 disposition).
2. **RB-CEREMONY-DEPTH-001** (research only) — does the constitution already define exact
   `(verifiability × reversibility)` mechanics, or does it need a founder design decision?
3. Implement canonical **L02 ceremony contract** + **Trace-A discharge evidence stubs** (K1).
4. Runtime executes the **ceremony-resolved obligation graph** — NOT more hard-coded
   SoftLoop stages.
5. **A-08 fail-closed** enforcement: `BuilderFamily ≠ AuditorFamily`, generic
   (never vendor-locked to GPT-5.6). Same-family audit must HALT/REMAND, never degrade.
6. Prove canonical Trace-A → warranted Trace-B → **R4 conformance decision**.

**Forbidden until Step 3 is done:** coding L02 ceremony assignment (inventing a scoring
algorithm = legislating); deleting ADE/MISSION_CONTROL (freeze authority, re-evaluate);
pre-decided disposition of the 24 vacuous seals.

## 4. Open items

- Run 7 remand reason not yet diagnosed (see `.paeos_state/court/r-7*.jsonl`, verdict in CAS).
- A-08 unmet during single-model GLM window (GPT quota reset ~2026-08-22).
- **Uncommitted work — commit to git immediately** (two docs were nearly lost to
  compaction this session; don't repeat that).

## 5. Ground rules that emerged this session

- Authority order: frozen doctrine (`operations/`) > ratified amendments > kernel invariants
  > implementation > audit reports > AI opinions. Implementation NEVER redefines architecture.
- New requirement ≠ new architectural state (CER v1.1: "governs every state; add no state").
- TDD belongs in L11 contract + L13 court obligation, not a new StageId.
- Any doc produced by an agent must be verified on disk before reporting it done.
