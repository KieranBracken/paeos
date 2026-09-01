# PAEOS L14/L17 Physical Audit — Candidate `38b5395`

**Date:** 2026-09-01  
**Candidate:** `38b53955c83126f2bed231640555d86ed1f3159a`  
**Recovery branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Audit ID:** `l14-l17-38b5395-gemini-epoch4-contract-001`

## Bound artifacts

- Evidence bundle: `/private/tmp/paeos-l14-l17-bundle-epoch4-contract.md`
- Evidence bundle SHA-256: `8594658ae9767f489093dd0473c75b8931b95c98b8b9554c7b914e581121fd1a`
- Prompt SHA-256: `0edb5da3eb8a550432ed84d2705c7888e602043bede2809aa253745c59811a56`
- Report: `/private/tmp/paeos-l14-l17-report-38b5395.md`
- Report file SHA-256: `b15289ab911abbe7400dd14b871868a73e363b4bbbc8b76205fb3b136a53c48a`
- Receipt: `/private/tmp/paeos-l14-l17-receipt-38b5395.json`
- Receipt file SHA-256: `391130b37115ddf7278821182507af9c0c76ca47e4bf98b8c38fcbd6b7cf8f7b`
- Canonical receipt SHA-256: `f6da040bb9d7797df36783b586f6232082ab5393279c951e3650d03823ea1c77`
- Transcript SHA-256: `ca2f1109c768158d141458df7ff3ee1c000e0ff3b4c77194280d37db3f965339`

## Physical provenance

- Actual provider/model: Google / `gemini-3.6-flash`
- Auditor family: `gemini`
- Builder: `cline-pass` / `z-ai/glm-5.3-flash` / family `glm`
- A-08 Builder != Auditor: **PASS**
- Provider attempts: `1`; fallback chain: `google:gemini-3.6-flash`

## Substantive disposition

`L14_STATUS: PASS`. The report binds the exact candidate and evidence bundle, contains concrete
findings, uses the capture contract’s per-audit accounting lines, and ends with
`AUDIT_COMPLETE: true`. Findings cover the explicit legacy-identity compatibility boundary,
focused 130/130 verification, 1,107/1,107 non-gateway reproduction, epoch-4 admissions, and
prompt/receipt contract alignment.

Quality observation: the machine-readable fields are `INVARIANT: None` and `REPRODUCTION: N/A`;
the detailed findings contain the substantive invariant and reproduction evidence. This is
recorded for future prompt-quality hardening and is not silently upgraded to a stronger claim.

## Constitutional boundary

This is qualified candidate-bound L14/L17 evidence only. It does not create a Court/L16 ledger
row, seal Gate A, close `DEBT-0058` or `DEBT-0060`, promote a ref, or resume SAKG. Aggregate
worker evidence remains **Admitted: 3 | Rejected: 3 | Remediated: 0** and Court remains
**Sealed: 0 | Remanded: 0 | Remediated: 0**. The current strict program count is
**12/48 complete | 36 remaining**. A separate canonical Court/L16 reconciliation is required
before any gate advancement.
