# PAEOS L16 Court Reconciliation — Candidate `38b5395`

**Date:** 2026-09-01  
**Candidate evidence commit:** `38b53955c83126f2bed231640555d86ed1f3159a`  
**Recovery branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Current review lineage:** documentation-only descendants; no runtime or test changes after the candidate

## Scope and authority boundary

This began as a read-only L16/Court reconciliation. The Founder has now supplied a separate,
candidate-bound constitutional disposition record. This review does not rewrite historical
ledgers, consume promotion authority, merge or promote a ref, or resume SAKG.

## Candidate-bound evidence

- L13 non-gateway reproduction: **1,107/1,107 passed**, exit `0`; gateway-server fixture excluded
  under restricted-loopback policy. Raw log SHA-256:
  `371cb17145492dddd1d3ba59eecb48a525667f070f0509ddd1f28e4288a66ede`; exit-record SHA-256:
  `9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa`.
- Focused SDK protocol/adapter/adversarial/admission and bound-transport checks: **130/130
  passed**, exit `0`.
- L14/L17 physical audit: `L14_STATUS: PASS`, Google `gemini-3.6-flash` / family `gemini`, one
  attempt, no fallback; builder `cline-pass` / `z-ai/glm-5.3-flash` / family `glm`; A-08
  **PASS**. Report SHA-256:
  `b15289ab911abbe7400dd14b871868a73e363b4bbbc8b76205fb3b136a53c48a`; receipt-file SHA-256:
  `391130b37115ddf7278821182507af9c0c76ca47e4bf98b8c38fcbd6b7cf8f7b`.

These establish candidate-bound L13 and L14/L17 evidence. They do not establish an L16
disposition by themselves.

## Read-only ledger revalidation

`ops.revalidate_paeos_lifecycle` was run once per available state ledger against immutable
SQLite copies, with no writes to the source ledgers. Each run verified its hash chain, emitted all
19 layer records, returned exit `2` with `UNPROVEN_LAYERS_PRESENT`, and reconciled Court counts
to zero:

| Ledger source | Verified head | Layers | Disposition fold | Court counts | Raw JSON SHA-256 |
|---|---|---:|---|---|---|
| `.paeos_state_investigation/ledger.db` | `4c1e569293e643f8db7177cecc98be5afe899cd07604d39c3c757e5909ffb8e9` | 19 | 19 `UNPROVEN` | 0/0/0 | `74d789fe92e4aa23d087911176bd7a2b43d173a6b98b1a0a4f457272283cecf2` |
| `misc/.state_rb0026/ledger.db` | `85bf57b6e194d5584bac8a6d28957a5bbb06239adee6f95a086be1e6491862c9` | 19 | 19 `UNPROVEN` | 0/0/0 | `98088506301652bb2b9a1d9effbb0b957ed69aa03c789c94328d0825ba7bfbae` |
| `misc/_state_sakg/state_sakg/ledger.db` | `40355131a0e9aa5b70156aa0a1f0e972a270c38d08fbfe03ba7485b817abdb4c` | 19 | 19 `UNPROVEN` | 0/0/0 | `5f2cab531900b8d8b2db2bb693364f33f012adb1fcebdf7d8cee8f3601e67c20` |
| `/Users/bob/.local/share/paeos/runtime-v2/ledger.db` | empty-ledger head `407590d349641e2acaa71e4ebd02c48e788d46d6d144ecb21f9a0e79dda58c29` | 19 | 19 `UNPROVEN` | 0/0/0 | `310254385e4d9abc209b9f21ccf00f0a43aa7441737e6d793c85b8f84b4742e2` |

The fold found no correlated `COURT_SEALED`, `COURT_REMANDED`, `COURT_REMEDIATED`, promotion,
or Founder-disposition row in the available ledgers. The lifecycle auditor therefore correctly
refuses to infer a Court result from report prose or test output.

## Historical ledger disposition

```text
L16_STATUS: BLOCKED_UNQUALIFIABLE
REASON: no candidate-correlated canonical Court/L16 disposition row exists
```

Aggregate Worker evidence remains **Admitted: 3 | Rejected: 3 | Remediated: 0**; Court remains
**Sealed: 0 | Remanded: 0 | Remediated: 0**. `DEBT-0058` and `DEBT-0060` remain **OPEN**.
Strict progress remains **12/48 complete | 36 remaining**. Gate A and all later gates remain
unsealed; SAKG remains held.

## Founder/Court disposition (superseding external resolution)

The Founder supplied the exact candidate-bound disposition
`COURT_SEALED` for Gate A (Worker Admission & Transport Baseline) and authorized progression to
Gate B. The resolution is recorded in
`reviews/tasks/PAEOS_GATE_A_FOUNDER_COURT_DISPOSITION_38B5395.md` with SHA-256
`2e42f4823c970b4e0379182b8c31c1e5eae0730d905d57ab04a127e6d9641bfe`.

```text
L16_STATUS: PASS
REASON: Founder/Court disposition explicitly seals candidate 38b5395 after passing L13 and L14/L17 evidence
```

This external resolution supersedes the historical no-row observation for Gate A without claiming
that a historical SQLite ledger was rewritten. Gate A is **SEALED**, `DEBT-0058` is **REPAID**, and
strict program progress is **13/48 complete | 35 remaining**. Gate B is authorized to proceed under
its approved plan; its own candidate-bound evidence and disposition remain required.
