# PAEOS-IP-0015 — Cryptographically Bind L14 Reports and Enforce Canonical Accounting

Status: **AWAITING FOUNDER RATIFICATION** · Filed: 2026-08-30 · Channel: CER-2
Level: **operational evidence schema / possible kernel-surface amendment**
Source: Gate C headless-supervisor L14 receipt review; Notebook Entry 175.

## 1. Observation

The candidate-bound physical receipt for `l14-headless-9fd72db-001` validates its transport
identity and A-08 decorrelation. The paired persisted report passes the current binding/status
validator but claims worker and Court successes that contradict the prompt and the durable
recovery ledger. The receipt has no digest of the report content, so it cannot prove that the
persisted report is the response whose transport digest it records.

## 2. Current behaviour

`PhysicalAuditorReceipt` stores request, response, and transcript digests but no report-content
digest. `validate_auditor_report()` checks non-empty content, candidate/evidence bindings, one
status, and remand detail; it does not require the exact accounting fields requested by the audit
contract or compare them with a bound canonical ledger snapshot.

## 3. Proposed improvement

1. Add a canonical `report_sha256` (and, where needed, a ledger-snapshot identity) to the receipt,
   computed from the exact persisted response bytes and written atomically with the report.
2. Make the L14 report schema machine-readable for worker/Court accounting and require the exact
   counts declared by the request's bound ledger snapshot.
3. Reject any missing, contradictory, or extra accounting claims before persistence; preserve the
   raw response and rejection reason as evidence.
4. Add discriminative tests proving the validator rejects the current `1/0/0` claims and fails
   when the report is swapped after receipt capture.

## 4. Justification

This prevents a physically genuine transport response from being paired with altered or
hallucinated operational counts. It reinforces A-09 probative evidence, CER-1 falsification,
and the Builder/Auditor separation without optimizing for zero remands.

## 5. Risks

- Receipt schema migration and ledger-snapshot plumbing add complexity.
- Providers may emit prose that requires a strict structured wrapper; malformed responses will
  remand rather than silently pass.
- Historical receipts lack `report_sha256` and need an explicit legacy status.

## 6. Backwards compatibility

Existing receipts remain readable as legacy-unbound artifacts but cannot satisfy the strengthened
L14 gate. New receipts use a versioned schema or an optional field with an explicit conformance
level; no historical evidence is rewritten.

## 7. Constitutional impact

This may amend the L14 evidence contract and receipt schema, potentially touching kernel-facing
evidence validation. It must complete L03–L11 design/court review and founder ratification before
any enforcement change; drafting this proposal changes no runtime behaviour (CER-5).

## 8. Recommendation

**Ratify after design and adversarial review**, with the smallest compatible schema extension and
an explicit legacy/unbound disposition. Until then, keep the current L14 report remanded.
