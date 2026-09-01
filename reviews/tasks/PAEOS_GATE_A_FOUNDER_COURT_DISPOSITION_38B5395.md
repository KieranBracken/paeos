# Gate A Founder/Court Disposition — Candidate `38b5395`

**Date:** 2026-09-01  
**Candidate:** `38b53955c83126f2bed231640555d86ed1f3159a`  
**Recovery branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Disposition authority:** Founder (external L16 decision surface)  
**Disposition:** `COURT_SEALED`

## Evidence base

- Three independent live GLM worker probes (`...21`, `...22`, `...23`) were admitted.
- Candidate-bound L13 reproduction passed **1,107/1,107**, exit `0`.
- Independent heterogeneous Gemini 3.6 Flash L14/L17 audit passed with A-08
  `Builder (GLM) != Auditor (Gemini)`.
- Non-secret provenance, workspace confinement, seeded mutation/restoration, and lease lifecycle
  were verified.
- L14/L17 evidence bundle: `8594658ae9767f489093dd0473c75b8931b95c98b8b9554c7b914e581121fd1a`.
- L14 report SHA-256: `b15289ab911abbe7400dd14b871868a73e363b4bbbc8b76205fb3b136a53c48a`.
- L14 receipt-file SHA-256: `391130b37115ddf7278821182507af9c0c76ca47e4bf98b8c38fcbd6b7cf8f7b`.

## Founder resolution

The Founder authorizes **Gate A sealing** for Worker Admission & Transport Baseline and
progression to Gate B under the approved control-plane recovery plan. This authorization does not
permit merge, promotion, main/trunk mutation, credential access, fallback, retry, or unrelated
architectural changes.

## Authority boundary

This file is the candidate-bound one-off external L16 disposition record. It is not a replacement
for the append-only runtime ledger and does not claim that a historical SQLite ledger was mutated.
The decision is recorded for reconciliation; subsequent Gate B work must still obtain its own
candidate-bound evidence and applicable L16/L17 disposition.
