# Gate A — Cline Worker Admission / DEBT-0058 Review

**Date:** 2026-09-01  
**Evidence candidate:** `38b53955c83126f2bed231640555d86ed1f3159a`  
**Recovery branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Documentation descendants:** `fd9d6c2`, `b5a36be` (no runtime or test changes after the candidate)

## Scope and authority

This review adjudicates the Gate A admission evidence and, together with the separately recorded
Founder/Court disposition, its closure. Worker claims are not treated as constitutional authority;
physical receipts, correlated evidence, and the explicit Founder resolution are required.

## Worker admission evidence

Three distinct one-shot Cline SDK probes were admitted after authentication epoch 4:

| Probe | Provider / model / family | Verdict | Receipt |
|---|---|---|---|
| `...21-auth-epoch-4-readiness-001` | `cline-pass` / `z-ai/glm-5.3-flash` / `glm` | ADMITTED | `102fe131f694aabd840ea49cc024060db2258d4a93ce4ac04694ba6d355739c1` |
| `...22-auth-epoch-4-seeded-mutation-002` | `cline-pass` / `z-ai/glm-5.3-flash` / `glm` | ADMITTED | `8c870d09d0f533feedd3dae44825b4eb6a79191fe07a48c71ef8a5d80334a7f1` |
| `...23-auth-epoch-4-final-admission-003` | `cline-pass` / `z-ai/glm-5.3-flash` / `glm` | ADMITTED | `3bf1c1d3784aafedbc72210e4c4232ee474be6099874a43542a32e7ce015c737` |

All three completed with exit `0`, no fallback/retry, spawn/teams disabled, workspace confinement,
successful seeded mutation/restoration, and clean lease release. Aggregate worker accounting is
**Admitted: 3 | Rejected: 3 | Remediated: 0**. The later Court/L16 boundary is resolved by the
candidate-bound Founder disposition recorded in
`reviews/tasks/PAEOS_GATE_A_FOUNDER_COURT_DISPOSITION_38B5395.md`.

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
GATE_A_STATUS: COURT_SEALED
REASON: Founder supplied an exact candidate-bound L16 disposition after all admission and audit evidence passed
```

The Founder/Court disposition record is
`reviews/tasks/PAEOS_GATE_A_FOUNDER_COURT_DISPOSITION_38B5395.md` (SHA-256
`2e42f4823c970b4e0379182b8c31c1e5eae0730d905d57ab04a127e6d9641bfe`). Gate A is **SEALED** and
`DEBT-0058` is **REPAID**. The historical SQLite ledgers remain unchanged; this is an external
Founder ABI resolution, not a fabricated runtime event. Strict progress advances to
**13/48 complete | 35 remaining**. Gate B work is now authorized under the recovery plan, while
promotion, merge, main/trunk mutation, and SAKG resumption remain prohibited until their own
evidence and dispositions pass.
