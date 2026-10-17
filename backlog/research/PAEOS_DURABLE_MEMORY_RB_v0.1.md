# PAEOS Durable Institutional Memory — Research Backlog Item v0.1

**Date:** 2026-08-18 · **Status:** OPEN · **Origin:** Hallucination notebook Entries 138–142
**Author:** Founder-directed audit (Cline) · **Priority:** CRITICAL (blocks operational L17–L19 proof)

## Finding: the learning layers never accumulated anything

Verified empirically on 2026-08-18:

1. **Zero durable scars exist.** `ScarStore` (`runtime/memory/__init__.py:70`) is a pure
   in-memory dict; `ops/autonomous_run.py` never injects a persistent backend. No scar
   artifact exists anywhere under `.paeos_state/` or any state directory. Every scar ever
   proposed by the EvolutionLayer evaporated at process exit.
2. **Zero evolution ledger rows.** The ledger contains only `GOAL_CREATED` and `SEAL` rows
   (123 + 25). No `STAGE_COMPLETED`, no evolution/retrospect events. L17–L19 "ran" as code
   paths but left no institutional record.
3. Consequence: **every L01–L16 run executed blind.** Within a single process lifetime
   scars could match; across sessions nothing survived. The system that exists to make
   scar-driven learning real has itself never learned anything across sessions.

This is *absence*, not contamination: the constructed L01–L16 outputs (git, 424 tests,
42 review docs) are real and independently verified. Nothing needs purging; the memory
substrate needs building.

## Required work (dogfooded through PAEOS itself — PAEOS builds PAEOS)

- **Intake 1 (this RB):** a durable `ScarStore` backend — SQLite-backed under the state
  directory (`<state_dir>/scars.db`), injected by `ops/autonomous_run.py`, preserving the
  in-memory class's contract (`propose_scar`, `match_scars`, `get_precedent`,
  `injected_scars`, quarantine semantics). Tests: persistence across process boundaries;
  T3 quarantine preserved; match semantics identical.
- **Intake 2:** evolution/retrospect events appended to the ledger (`STAGE_COMPLETED`
  already landed, Entry 142 Finding B; add EVOLUTION events from the EvolutionLayer chain).

## Execution constraint (notebook Entry 142 LIMITATION)

GPT-5.6 Sol quota exhausted until ~2026-08-22 ⇒ intakes run **GLM-5.3-only**
(`autonomous_run.py … glm`). All seals from this window carry homogeneous-audit risk;
deterministic kernel guarantees (court reproduction, evidence binding, taint index,
junk-artifact filter, model attribution) remain fully in force. Re-run the proof intake
under `hybrid` when GPT quota returns and record the delta.
