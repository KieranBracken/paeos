# RB-0026 — Durable Institutional Memory (L17–L19 Gap) & the Fabricated-Seal Remediation

**Status:** OPEN — first dogfood intake of the corrected pipeline
**Date:** 2026-08-18
**Source:** Hallucination notebook Entries 138–142 (audit of 2026-08-15→18)
**Weight:** SUBSTANTIAL

## The finding this item records

The 2026-08-18 audit established three linked facts:

1. **25 seals, 1 real.** 24 of 25 ledger seals certified junk artifacts (9 × 0-byte, 15 × a
   macOS `.DS_Store`), and every seal's adversary review was either a 43-byte auto-fed
   `VERDICT: PASS` string (19 seals) or a same-model *builder* transcript (6 seals). GLM-5.3
   never executed a stage (Cline session DB: zero PAEOS sessions pre-audit).
2. **No durable learning ever happened — for ALL of L01–L16, not just some.** `ScarStore()`
   defaulted to in-memory; zero scar artifacts exist on disk; the ledger contains zero
   evolution/retrospect events. Every run started blind. The construction outputs (code, 416
   tests, 42 review documents) are real and untainted — but the *learning* layers never
   accumulated anything, cross-session.
3. **The evolution chain runs but evaporates.** `ops/autonomous_run.py` invokes
   `EvolutionLayer.run()` after every run, and the canonical lifecycle doc's "L17–L19 entirely
   missing from SoftLoop" is stale at the runner-composition layer — the machinery exists and
   fires; its output is discarded when the process exits.

## The remediation (this intake is part of it)

Phase 1–2 already landed: auto-feed fabrication deleted; fail-loud invokers; evidence
submission requires real values; taint index on the court pool (99 fabricated rows skipped);
junk-artifact filter; Cline-native GLM-5.3 invoker with model-attribution enforcement;
STAGE_COMPLETED ledger rows recording which model ran each stage.

**This intake (dogfooded — PAEOS builds PAEOS):** make `ScarStore` durable (SQLite-backed,
state-dir colocated with the ledger/CAS) and inject it in `ops/autonomous_run.py`, so
L17 outputs persist and L18 scar-injection can fire across process boundaries.

## Constraints

- Single-task session per AGENTS.md.
- Runs during the **single-model GLM-5.3 interim window** (GPT quota exhausted until
  ~2026-08-22): homogeneous-audit caveat applies to any seal from this window.
- The kernel seal key stays with the kernel; scar writes go through kernel APIs.

## Acceptance

- A scar written by one run is readable by a subsequent process (persistence proven).
- The full 19-layer loop seals with a *genuine* GLM-5.3 adversary verdict.
- Ledger shows STAGE_COMPLETED rows attributing every stage to `cline-pass/glm-5.3`.
