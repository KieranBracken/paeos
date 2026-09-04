# PAEOS MILESTONE 45 — `[SAKG TASK 21]` / Taxonomy Node Hierarchy Subsumption
## FOUNDER / COURT DISPOSITION

**Disposition:** **COURT_SEALED**
**Sealed:** 2026-09-04
**Milestone:** 45 of 48
**Predecessor:** Milestone 44 `[I-L15-SIZING]` / L15 Dynamic Context Sizing
**Next intake:** Milestone 46 — CER Gate Transition Verification Suite

## Founder direction

The Founder directs that Milestone 45 be recorded as qualified and complete on the supplied
candidate-bound Layer 14/17 audit pair. This seal admits the milestone to the physical progress
counter and records the evidence boundary; it does not promote the detached implementation into
the host worktree, merge a branch, or mint authority for SAKG claim promotion.

The qualified physical pair is the NVIDIA `meta/llama-3.2-11b-vision-instruct` audit, not the
separate Founder-authorized Gemini one-shot whose report was truncated and rejected. The rejected
Gemini artifacts remain immutable historical evidence and do not contribute to this seal.

## Candidate and scope

- **Implementation candidate:** `afc06e911840c60b091161a5864ca514dd8c0bdd`
- **Canonical intake:** `reviews/tasks/PAEOS_SAKG_TASK_21_TAXONOMY_NODE_HIERARCHY_SUBSUMPTION_INTAKE.md`
- **Candidate clone:** `/private/tmp/paeos-m45-task21-candidate` (detached; host branch unchanged)
- **Candidate source artifact hash:** `17d7f4102057b8d962984f90ef8873cfb996a680c574977139ad521edd1cc0a0`
- **Candidate focused-test artifact hash:** `f7a2566c3f2062ab7c33e44ba2828e1ab2f4fbc8c044df1085ced9f7702157ca`
- **Contract:** typed SAKG node identifiers and exact `subsumes` relation; provenance- and
  evidence-hash requirements; deterministic, graduated scope transfer; constraint compatibility;
  cycle and ambiguity rejection; machine-readable explanations and failure reasons; idempotent
  append without node mutation.

The candidate remains a detached implementation artifact. This documentation commit contains no
SAKG source or test changes.

## Local Layer 13 / Court evidence

The final isolated SoftLoop state root was `/private/tmp/paeos-m45-task21-run`:

- **Final run:** `r-530205f1`
- **Goal:** `g-a8707365ba55`
- **Local seal:** `5e768d9926917aa42f937c71cafb3f4721cf74d4d73dbee5aebaf5d0fe8d5252`
- **Ledger head:** `66`
- **Ledger SHA-256:** `565e67464c0a3a0410a2c5d5130dc924c9953d6d4650bd2bc189cfb700a008a4`
- **Final artifact bundle:** `8279b70a20760600bbe77e567b2f924e4017b558c8f27fe58eb73a58dc854c17`
- **Final adversary report:** `PASS` (CAS `15f032698e1b0b1809f8d88ab486032215600e7a942200fbdee3b885d4279b11`)
- **Focused SAKG test result:** 7/7 pass; the isolated `tests/sakg` suite also passed.

The chronology records three remediated, fail-closed remands before the final seal: a bridge
timeout (`r-380e4bfc`), non-reproducing elapsed-time pytest output (`r-aa6bc788`), and an A-08
typed-identifier/hexadecimal-hash validation finding (`r-438efeb6`). Local accounting is
**Court: Sealed 1 | Remanded 3 | Remediated 3** and **Worker: Admitted 0 | Rejected 0 |
Remediated 0**. These remands remain visible back-pressure; they are not optimized away.

## Layer 14/17 physical audit

The supplied receipt/report pair is bound to the exact candidate and bundle:

- **Audit ID:** `m45-sakg-task21-afc06e9-nvidia-001`
- **Auditor:** NVIDIA `meta/llama-3.2-11b-vision-instruct` (family `llama`)
- **Builder recorded by receipt:** `cline-pass` / `z-ai/glm-5.3-flash` (family `glm`)
- **A-08:** **PASS** (`llama != glm`)
- **Provider attempts:** 1; fallback chain contains only the configured NVIDIA route; no retry
- **Candidate commit:** `afc06e911840c60b091161a5864ca514dd8c0bdd`
- **Evidence bundle SHA-256:** `0bd0a8e3e811026078bd1513719bbd2fb1e5007b7ceae41519ce25f22c14db31`
- **Candidate manifest:** `/private/tmp/paeos-sakg-task21-candidate-bundle.json`
- **Manifest file SHA-256:** `0bd0a8e3e811026078bd1513719bbd2fb1e5007b7ceae41519ce25f22c14db31`
- **Physical receipt:** `/private/tmp/paeos-sakg-task21-m45-receipt.json`
- **Receipt canonical/self SHA-256:** `215242a20dd8dceb76c0eaa342fcf0c11fe52dba62a3cbc3868ecc31ab63dd09`
- **Receipt file SHA-256:** `8dfbc97ac4b6d61c0099f76d057b85f2dd8e6c3b8de048badfec045c862690c7`
- **Substantive report:** `/private/tmp/paeos-sakg-task21-m45-report.md`
- **Report SHA-256:** `fbfd7fc75ef0585ef15c789209ffa053883c73ad2bcb7191d44e0e7f8f917bf5`
- **Review scope / transport request SHA-256:** `6dfaceefb2db6bbc5c78854a58b371e75ff64faa1fd5c43fba5b6ea7a646e3d8`
- **Report status:** **PASS**; exact terminator `AUDIT_COMPLETE: true` present
- **Physical window accounting:** **Sealed: 1 | Remanded: 0 | Remediated: 0**

The report verifies typed node identifiers, the exact `subsumes` relation, provenance, evidence
hashes, ambiguity checks, deterministic scope transfer, and fail-closed rejection behavior. The
receipt's canonical self-hash is recorded separately from the digest of the receipt file; neither
value is substituted for the other.

### Preserved physical finding

The substantive report observes that when a child scope is not a subset of the parent scope, a
`ScopeIncompatibilityError` may be raised without a sufficiently clear explanation of the
incompatible scope classes and domains. This is retained as an auditor finding and follow-up risk.
The report is nevertheless qualified `PASS` for the audited contract, and this disposition makes
no claim that the explanatory text has been fixed or that scope claims are widened automatically.

## Programme accounting and next work

The physical completion counter advances exactly once for this qualified audit window:

```text
32/48 complete | 16 remaining  →  33/48 complete | 15 remaining
```

Milestone 46 — **CER Gate Transition Verification Suite** — is now **OPEN / QUEUED** in
`reviews/tasks/PAEOS_MILESTONE_46_CER_GATE_TRANSITION_VERIFICATION_SUITE_INTAKE.md`. It is queued
for a new isolated execution and has no implementation, physical audit, or completion seal yet.

## Non-actions and integrity constraints

- No additional provider transmission was made by this disposition; the supplied NVIDIA pair is
  consumed as-is.
- The prior Gemini `gemini-3.6-flash` one-shot remains rejected for truncation and is not reused.
- No fallback, retry, source-code change, promotion, merge, or main/trunk/protected-ref mutation
  occurred.
- SAKG remains the authority for taxonomy and claim promotion; this seal does not promote any
  Concept OS candidate or widen any claim scope.
- Legacy `PAEOS_INTAKE_M46_*` records are preserved historical artifacts from an older sequence;
  the canonical next intake is the CER Gate Transition Verification Suite named above.

**COURT_SEALED**
