# SAKG Task 13 — F-TRADEOFF-FIX Court Reconciliation (REMANDED)

**Date:** 2026-09-03
**Task:** `[F-TRADEOFF-FIX]` Golden tradeoff fixtures and precedent joins
**Recovery branch:** `codex/control-plane-recovery-s1-clean-recovered`
**Host HEAD:** `af601ffe1386735c5e0c76bc332dfa2ce0b81d0a`

## Local reproduction

The five existing Task 13 suites were run once against the recovery checkout with the repository
Python 3.13 environment:

```text
env PYTHONPATH=. /Users/bob/GitHub/paeos/.venv/bin/python -m pytest \
  tests/sakg/test_tradeoff_fixtures_wellformed.py \
  tests/sakg/test_tradeoff_fixtures_reference_real_goals.py \
  tests/sakg/test_tradeoff_golden.py \
  tests/sakg/test_tradeoff_joins_outcome.py \
  tests/sakg/test_tradeoff_precedents.py -qq
```

Result: `10 passed`, exit code `0`. Ruff and Pyright over `sakg/ tests/sakg/` were also clean.
This local reproduction is not a Court seal and does not establish Builder != Auditor.

## SoftLoop/Court evidence

Four distinct isolated windows were dispatched; all exited `2` with `REMANDED` outcomes:

| Window | Run | Court JSONL SHA-256 | Disposition |
|---|---|---|---|
| `/private/tmp/paeos-ftradeoff-run-001` | `r-5d109410` | `83f6194306337f65d2a88de12931adf796494c2625ee189bfe5e956e5869374e` | Court replay mismatch |
| `/private/tmp/paeos-ftradeoff-run-remediation-002` | `r-c265642d` | `3f5660ed1cf490fee585cb757deaf8923b7e9b2fe401fd0dd15e1b3dab174ae9` | Adversary blocked stale/non-discriminating evidence |
| `/private/tmp/paeos-ftradeoff-run-remediation-003` | `r-456aa82b` | `996a6efb27a2f0003e8baf252746ff615c91c32818d4f3a479e55ddb5da43747` | Adversary selected `.gitignore` junk artifact |
| `/private/tmp/paeos-ftradeoff-run-remediation-004` | `r-ab48d6e2` | `6173020693c1e52d38b1212736f4c0f97f1eab381866e75d39a4a3f92c4871e7` | Adversary found artifact/repository divergence and fail-open production code |

The latest state-root ledger verifies to head
`b640986594ba8e38a77556e0608e31e1cb244eec079b4867f634be3f07a6574f`.

## Blocking findings

The latest adversary report (CAS
`/private/tmp/paeos-ftradeoff-run-remediation-004/cas/9f/bd51416c6a2a64cebcac0aa840de82ba6dc10b64e315bbc9409886c68aad5b`)
is preserved as the authoritative raw dissent. It establishes:

1. The submitted strong artifact hash `551344f9deba9a67a8a9435b4412de7fdb542c9400189f8a98917f032bb37b75`
   exists only in the isolated CAS; the committed `sakg/methods/tradeoff_precedents.py` hashes to
   `6966e85136f322362d409fa2a0099c810f4f200d441ab5218944b50f70f24d2d`.
2. The committed method accepts negated resolving/realization links, ignores `namespace` and
   `min_confidence` in `execute()`, and admits untyped nodes (adversary probes P1–P5).
3. The `builds` claim passes only against the uncommitted CAS bytes; the `unit` claim is
   non-discriminating and passes against both weak and strong implementations.

## Canonical disposition

**Task 13: REMANDED / NOT SEALED.**  Exact Task 13 window accounting is
`Sealed: 0 | Remanded: 4 | Remediated: 0`. Strict physical program progress remains
`18/48 complete | 30 remaining`; Task 14 is held.

Required before a new attempt: integrate the strong implementation into the recovery candidate via
an authorized integration seam, add discriminating negative/namespace/confidence/type fixtures,
then rerun the Court and obtain a fresh heterogeneous L14/L17 receipt. No main/trunk promotion or
self-ratification occurred.
