# PAEOS MILESTONE 44 — `[I-L15-SIZING]` / L15 Dynamic Context Sizing
## FOUNDER / COURT DISPOSITION

**Disposition:** **COURT_SEALED**  
**Sealed:** 2026-09-04  
**Milestone:** 44 of 48  
**Predecessor:** Milestone 43 `[I-CER-BASELINE]` / L02-C1 Ceremony Enforcement Realization  
**Next intake:** Milestone 45 — SAKG Task 21 / Taxonomy Node Hierarchy Subsumption

## Founder direction

The Founder directs that the Milestone 44 L15 Dynamic Context Sizing implementation be entered as
qualified and complete on the strength of the supplied Layer 14/17 physical audit and the sealed
local execution record below. This disposition seals the governance record only. It does not
promote the implementation, merge a branch, transmit a new prompt, retry a provider, or mutate a
protected ref.

## Candidate and scope

- **Implementation candidate:** `2e6c900e86428abb0cb94c59f135dafb37b5507f`
- **Intake:** `[I-L15-SIZING]` / L15 Dynamic Context Sizing
- **Contract:** deterministic input-budget derivation from verified model capacity, mandatory
  non-eviction, typed fail-closed overflow, no silent truncation, and machine-readable sizing
  records while preserving the legacy compiler API.
- **Candidate source hash:** `bd74cff...251a6` (as recorded in the isolated bundle)
- **Candidate test hash:** `f2e3adca...72c3c9` (post-format isolated bundle)

The candidate commit is an implementation artifact and is kept distinct from this documentation
disposition commit. No source change is made by this record.

## Local Layer 13 / Court evidence

The final isolated SoftLoop was run under `/private/tmp/paeos-l15sizing-run`:

- **Run:** `r-086c73de`
- **Goal:** `g-7486b8e7a7d7`
- **Local seal:** `d867658b49da459c37cab6ee25f8ca7121f174723959d91d674f6570d133c472`
- **Ledger head:** `8adb14fd39721cdcad355a46a4cd14a5bdd2b2a349905d15fb2a3e15ecff7026`
- **Artifact bundle:** `45703c8ca932ea5f968fdf96fecf4f69a47c0036113b981bf40a3dbc2dbb6014`

Mechanical reproduction recorded in the bundle is:

| Check | Result |
|---|---|
| Focused L15 sizing tests | 14/14 pass |
| Existing compatibility tests | 21/21 pass |
| Full runtime suite | exit 0 |
| Model-router suite | 10/10 pass |
| Ruff | exit 0 |
| Pyright | exit 0 |
| AST anti-pattern scan | 2 files checked, no violation |
| Mutation evidence | 8 failures / kill condition satisfied |

The local state-root chronology preserves healthy back-pressure: **Court Sealed: 2 |
Remanded: 2 | Remediated: 2; Worker Admitted: 0 | Rejected: 0 | Remediated: 0**. Remands are
not defects to optimize away and the zero-remand state is not an acceptance criterion. The two
remands were resolved by narrowing the elapsed-time evidence and by isolating an adversarial
ledger-scope disagreement; the original records remain immutable.

## Layer 14/17 physical audit

The supplied physical receipt and substantive report qualify the exact candidate:

- **Audit ID:** `m44-l15sizing-2e6c900-nvidia-001`
- **Auditor:** NVIDIA `meta/llama-3.2-11b-vision-instruct` (family `llama`)
- **Builder recorded by receipt:** `cline-pass` / `z-ai/glm-5.3-flash` (family `glm`)
- **A-08:** **PASS** (`llama != glm`)
- **Provider attempts:** 1; no fallback or retry
- **Candidate:** `2e6c900e86428abb0cb94c59f135dafb37b5507f`
- **Evidence bundle:** `31696bc14435062b0a1854b98a2187ef91f84c6aa42c1a5f809102c6ee3550e4`
- **Bundle:** `/private/tmp/paeos-l15sizing-m44-bundle.json`
- **Physical receipt:** `/private/tmp/paeos-l15sizing-m44-receipt.json`
- **Receipt canonical/self hash:** `61d10b197a9bbde74ae11ef76d4a9e74261cc0faa945dbd71aa3c479a4f79e80`
- **Receipt file SHA-256:** `0432b4bc8cd8d299d405ddbf8f6a600f9920734c623d5358b286add9c69dc6a9`
- **Substantive report:** `/private/tmp/paeos-l15sizing-m44-report.md`
- **Report SHA-256:** `0f28779da98e7344e9be243956967bd1a1c7237872bd1760469793f9adcbdd22`
- **Review scope / transport request SHA-256:** `849809ea957e68e5c7b24b02105db45190ab010a444b6f2e0d63384ad5f322ea`
- **Report status:** `PASS`; **qualified:** `true`; report terminator: `AUDIT_COMPLETE: true`

The physical report verifies deterministic sizing, mandatory non-eviction, and fail-closed
budget behavior across 14/14 tests. Its separate physical-audit window accounting is
**`Sealed: 1 | Remanded: 0 | Remediated: 0`**.

### Preserved report finding

The report notes that the implementation does not explicitly check a negative input budget. That
statement is retained verbatim as an auditor observation, but it is inconsistent with the
candidate source evidence: the source contains an explicit `budget < 0` fail-closed branch with
the `sizing_reservations_exceed_context_limit` disposition. The inconsistency is non-blocking
because the report is PASS, the source branch is reproducible, and no claim is widened beyond the
tested contract. Future sizing changes must add an explicit negative-budget assertion to the
focused audit rather than silently normalizing the finding.

## Programme accounting and next work

The physical completion counter advances exactly once for this qualified window:

```text
31/48 complete | 17 remaining  →  32/48 complete | 16 remaining
```

Milestone 45 is now **OPEN/QUEUED** as **SAKG Task 21 — Taxonomy Node Hierarchy Subsumption**.
Its canonical intake is `reviews/tasks/PAEOS_SAKG_TASK_21_TAXONOMY_NODE_HIERARCHY_SUBSUMPTION_INTAKE.md`.
No implementation or physical seal is claimed for Task 21 by this disposition.

## Non-actions and integrity constraints

- No new provider transmission was made; the earlier one-shot authorization is not reused.
- No fallback, retry, code change, promotion, merge, or main/trunk/protected-ref mutation occurred.
- The receipt’s canonical self-hash and the physical receipt file digest are intentionally recorded
  separately; neither is substituted for the other.
- The local remand and remediation history remains visible for future oversight and is not
  collapsed into the physical window count.

**COURT_SEALED**
