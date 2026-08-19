# PAEOS Ecosystem Discovery Pack Master Guide — v0.1

**Status:** Handoff Guide for Autonomous PAEOS Ingestion  
**Domain:** Discovery Pack Structure & Adjudication Protocol  

---

## 1. Discovery Pack Architecture

Each candidate system in `ecosystem_prep/<system>/` now contains a complete PAEOS-ready Discovery Pack:
- `01_ORIGINAL_VISION.md`: Forensic specification & primary mission.
- `02_CURRENT_REPOSITORY_STATE.md`: File manifest, code reality, debt, and drift.
- `03_FIRST_PRINCIPLES_DESIGN_A.md`: Blind Architect (Model A) clean-slate design.
- `04_FIRST_PRINCIPLES_DESIGN_B.md`: Existing-System Architect (Model B) current design evaluation.
- `05_ADVERSARIAL_REVIEW.md`: Adversarial Architect (Model C) flaw & assumption audit.

---

## 2. Ingestion Protocol for PAEOS

When PAEOS initiates ecosystem ingestion:
1. Ingest `SENTIUM_ECOSYSTEM_CANONICAL_INVENTORY_v0.1.md` and `00_ECOSYSTEM_BOUNDARY_ANALYSIS.md`.
2. Load Discovery Packs (`ecosystem_prep/<system>/01..05`) into context during `StageId.DESIGN` (L03 Re-Derivation).
3. Evaluate Blind vs Existing vs Adversarial designs during `StageId.CRITIQUE` (L09 Multi-Perspective Critique).
4. Derive final canonical architecture and mint build intakes in `ops/backlogs/`.
