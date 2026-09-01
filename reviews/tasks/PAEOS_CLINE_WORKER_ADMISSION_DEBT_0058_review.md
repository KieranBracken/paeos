# Gate A — Cline Worker Admission / DEBT-0058 Review

**Date:** 2026-09-01  
**Evidence candidate:** `38b53955c83126f2bed231640555d86ed1f3159a`  
**Recovery branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Documentation descendants:** `fd9d6c2`, `b5a36be` (no runtime or test changes after the candidate)

## Scope and authority

This review adjudicates the Gate A admission evidence and its remaining closure boundary. It is
not a Court seal, Founder ratification, promotion, merge, or SAKG authorization. Worker claims are
not treated as constitutional authority; physical receipts and correlated ledger facts are required.

## Worker admission evidence

Three distinct one-shot Cline SDK probes were admitted after authentication epoch 4:

| Probe | Provider / model / family | Verdict | Receipt |
|---|---|---|---|
| `...21-auth-epoch-4-readiness-001` | `cline-pass` / `z-ai/glm-5.3-flash` / `glm` | ADMITTED | `102fe131f694aabd840ea49cc024060db2258d4a93ce4ac04694ba6d355739c1` |
| `...22-auth-epoch-4-seeded-mutation-002` | `cline-pass` / `z-ai/glm-5.3-flash` / `glm` | ADMITTED | `8c870d09d0f533feedd3dae44825b4eb6a79191fe07a48c71ef8a5d80334a7f1` |
| `...23-auth-epoch-4-final-admission-003` | `cline-pass` / `z-ai/glm-5.3-flash` / `glm` | ADMITTED | `3bf1c1d3784aafedbc72210e4c4232ee474be6099874a43542a32e7ce015c737` |

All three completed with exit `0`, no fallback/retry, spawn/teams disabled, workspace confinement,
successful seeded mutation/restoration, and clean lease release. Aggregate worker accounting is
**Admitted: 3 | Rejected: 3 | Remediated: 0**. `DEBT-0058` is not closed until the later Court
and L16 boundary is reconciled.

## L13/L14/L17 evidence

- Current-candidate L13 non-gateway reproduction: **1,107/1,107 passed**, exit `0`, gateway-only
  fixture excluded; raw log SHA `371cb17145492dddd1d3ba59eecb48a525667f070f0509ddd1f28e4288a66ede`;
  exit-record SHA `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- Candidate-bound L14/L17 audit: candidate `38b5395`, evidence bundle
  `8594658ae9767f489093dd0473c75b8931b95c98b8b9554c7b914e581121fd1a`, report SHA
  `b15289ab911abbe7400dd14b871868a73e363b4bbbc8b76205fb3b136a53c48a`, receipt-file SHA
  `391130b37115ddf7278821182507af9c0c76ca47e4bf98b8c38fcbd6b7cf8f7b`, canonical receipt
  `f6da040bb9d7797df36783b586f6232082ab5393279c951e3650d03823ea1c77`.
- Physical provenance: Google `gemini-3.6-flash` / family `gemini` auditor versus
  `cline-pass` / `z-ai/glm-5.3-flash` / family `glm` builder; A-08 **PASS**, one attempt, no
  fallback. Report status: `L14_STATUS: PASS`, with concrete findings and terminal marker.
- Quality observation: report machine fields are `INVARIANT: None` and `REPRODUCTION: N/A`; the
  detailed findings contain the cited invariant and reproduction facts. This is retained as a
  prompt-quality debt, not upgraded into stronger evidence.

## L16 / Court reconciliation

The read-only lifecycle auditor verified the available state-ledger hash chains and emitted all
19 layer records. Every run returned exit `2` with `UNPROVEN_LAYERS_PRESENT`; no correlated
`COURT_SEALED`, `COURT_REMANDED`, `COURT_REMEDIATED`, promotion, or Founder-disposition row was
found. Court accounting is therefore **Sealed: 0 | Remanded: 0 | Remediated: 0**.

## Exact disposition

```text
GATE_A_STATUS: GATE_A_ROUTE_ELIGIBLE_FOR_SEALING
REASON: all three probes and candidate-bound L13/L14/L17 evidence pass; constitutional sealing remains external
```

Under the admission plan, this disposition makes the route eligible for Gate A sealing review; it
does not itself seal Gate A or repay `DEBT-0058`. The separate read-only L16/Court reconciliation
is `BLOCKED_UNQUALIFIABLE` because no candidate-correlated Court transaction exists. Strict
progress remains **12/48 complete | 36 remaining**. No Gate B+ implementation credit, promotion,
or SAKG resumption is claimed. A Founder/Court disposition must be produced through the canonical
PAEOS path; this review cannot create or ratify it.
