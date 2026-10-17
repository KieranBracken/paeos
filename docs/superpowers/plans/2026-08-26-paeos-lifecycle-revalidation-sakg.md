# PAEOS Lifecycle Revalidation and SAKG Resumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. This is an
> audit and disposition plan; missing evidence must be remanded, not implemented by the auditor.

**Goal:** Establish the truth about operational PAEOS L01-L19 execution from canonical evidence,
identify any gap between implemented components and proven end-to-end use, and authorize SAKG
resumption only inside the empirically verified envelope.

**Architecture:** A deterministic lifecycle auditor folds verified ledger rows, CAS artifacts,
Court evidence, physical model receipts, Git commits, and review records into a per-run evidence
matrix. Each layer is `EXECUTED`, `DISCHARGED_TRACE_A`, `NOT_APPLICABLE`, `REMANDED`, or
`UNPROVEN`. SoftLoop activity and historical AI prose are observations only. The audit tool is
read-only and produces a report; it cannot repair missing layers, seal a run, or promote SAKG.

**Tech Stack:** Python 3.12, existing `runtime.ceremony`, `kernel.lifecycle`, ledger/CAS/seal/review
records, Git read-only plumbing, pytest, Ruff, Pyright.

**Spec:** `operations/ENGINEERING_LIFECYCLE.md`, `operations/IMPLEMENTATION_REVIEW_PROTOCOL.md`,
and `docs/superpowers/specs/2026-08-26-paeos-ai-supervised-autonomy-design.md` section 14

## Global Constraints

- Depends on the separately Founder-integrated control plane and applicable post-bootstrap
  canaries. It does not retroactively authorize bootstrap.
- Never infer completion from commit messages, worker prose, notebook claims, a sequence of chat
  messages, test filenames, or the fact that SoftLoop reached `SEAL`.
- Trace-A discharges only the canonical permitted layers and requires one valid discharge stub per
  layer. It never discharges L12-L16.
- Trace-B must execute its full obligation graph. An absent artifact/event is not an implicit pass.
- Builder evidence, auditor evidence, and Founder/constitutional disposition remain distinct.
- A correct remand is evidence that safety worked. Report exact correlated counts.
- Audit findings may create remediation plans/debt, but this auditor must not patch the defect it
  is adjudicating.

---

## Task 1: Define the Canonical Per-Layer Evidence Matrix

**Files:**

- Create: `runtime/lifecycle_audit.py`
- Test: `tests/runtime/test_lifecycle_audit.py`
- Reuse: `runtime/ceremony.py`
- Reuse: `kernel/lifecycle.py`

**Interfaces:**

```python
class LayerDisposition(StrEnum):
    EXECUTED = "EXECUTED"
    DISCHARGED_TRACE_A = "DISCHARGED_TRACE_A"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    REMANDED = "REMANDED"
    UNPROVEN = "UNPROVEN"

@dataclass(frozen=True, slots=True)
class LayerEvidence:
    layer: Layer
    disposition: LayerDisposition
    ledger_sequences: tuple[int, ...]
    artifact_hashes: tuple[str, ...]
    evidence_hashes: tuple[str, ...]
    model_receipt_hashes: tuple[str, ...]
    reason_code: str

@dataclass(frozen=True, slots=True)
class LifecycleAuditReport:
    run_id: str
    trace: str
    layers: tuple[LayerEvidence, ...]
    sealed: int
    remanded: int
    remediated: int
    blocking_reason_codes: tuple[str, ...]
    verified_ledger_head: str

def audit_run(
    run_id: str,
    *,
    rows: Sequence[LedgerRow],
    cas: CAS,
    repository: Path,
) -> LifecycleAuditReport: ...
```

Canonical minimum evidence mapping:

- L01: root objective artifact, author/authority binding, `goal_id`/`run_id` correlation.
- L02: committed ceremony contract and classification derivation/read-set.
- L03-L11: matching `STAGE_COMPLETED` artifacts for EXECUTE obligations or exact
  `LAYER_DISCHARGED` stubs for lawful Trace-A obligations.
- L12: implementation task/result, frozen contract binding, worker receipt, candidate commit.
- L13: independently reproduced, non-vacuous Court evidence and exact verdict.
- L14: sealed-bundle audit, physical receipt, and proven Builder/Auditor family inequality.
- L15: documentation/traceability artifact bound to the candidate.
- L16: exact disposition authority; seal/promotion/bootstrap records as applicable.
- L17: mandatory 10-point constitutional review artifact.
- L18: memory/scar/debt/proposal update or explicit discard-with-reason.
- L19: triggered amendment/ratification evidence, or machine-proven not-applicable reason.

- [ ] **Step 1.1: Write RED evidence-matrix tests**

Create synthetic ledgers for complete Trace-A, complete Trace-B, missing L02, illegal Trace-B
discharge, missing L13 reproduction, vacuous evidence, homogeneous L14, missing L15, seal without
L17, triggered L19 without Founder disposition, duplicate/conflicting events, wrong run/goal, and
tampered CAS references.

- [ ] **Step 1.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_lifecycle_audit.py
```

Expected: collection fails because `runtime.lifecycle_audit` does not exist.

- [ ] **Step 1.3: Implement the read-only fold**

Verify the supplied rows with the pure hash-chain algebra first; the read-only auditor must not
construct `Ledger` and acquire its writer token. Resolve exact CAS hashes; do not search for
conveniently named files as proof. A layer with contradictory evidence is REMANDED. A missing
required record is UNPROVEN. `SEALED` is a run outcome only when the complete applicable evidence
chain supports it.

- [ ] **Step 1.4: Run GREEN with ceremony/lifecycle tests**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_lifecycle_audit.py \
  tests/runtime/test_ceremony_contract.py tests/kernel/test_lifecycle.py
```

- [ ] **Step 1.5: Commit**

```bash
git add runtime/lifecycle_audit.py tests/runtime/test_lifecycle_audit.py
git commit -m "feat(audit): derive lifecycle evidence per layer"
```

---

## Task 2: Add Exact Court Disposition and Model-Provenance Reconciliation

**Files:**

- Create: `runtime/court_reconciliation.py`
- Test: `tests/runtime/test_court_reconciliation.py`
- Modify: `runtime/lifecycle_audit.py`
- Reuse: `paeos/model_router/a08_enforcer.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class CourtCounts:
    sealed: int
    remanded: int
    remediated: int

def reconcile_court_counts(rows: Sequence[LedgerRow]) -> CourtCounts: ...
def verify_builder_auditor_receipts(run_id: str, rows: Sequence[LedgerRow], cas: CAS) -> tuple[str, str]: ...
```

- [ ] **Step 2.1: Write RED count/provenance tests**

Test remand followed by remediation/seal, repeated report of one remand, orphan remediation,
uncorrelated seal, worker-prose counts, unknown physical family, alias-only identity, builder and
auditor same family, receipt changed after dispatch, and pre/post-dispatch A-08 mismatch.

- [ ] **Step 2.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_court_reconciliation.py
```

- [ ] **Step 2.3: Implement correlated counting and decorrelation checks**

Count unique Court transaction dispositions. `Remediated` means a prior correlated remand whose
specific root cause was resolved and re-adjudicated; it is not synonymous with a later unrelated
seal. Verify physical receipts both before and after L14 dispatch.

- [ ] **Step 2.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_court_reconciliation.py \
  tests/model_router/test_a08_integration.py
```

- [ ] **Step 2.5: Commit**

```bash
git add runtime/court_reconciliation.py runtime/lifecycle_audit.py \
  tests/runtime/test_court_reconciliation.py
git commit -m "feat(audit): reconcile Court and model provenance"
```

---

## Task 3: Implement a Read-Only Revalidation CLI

**Files:**

- Create: `ops/revalidate_paeos_lifecycle.py`
- Test: `tests/ops/test_revalidate_paeos_lifecycle.py`

**Interfaces:**

```text
python ops/revalidate_paeos_lifecycle.py \
  --ledger <path> --state-root <path> --repository <path> --run-id <id> --json
```

- [ ] **Step 3.1: Write RED CLI tests**

Assert explicit state/repository binding, read-only file behavior, stable JSON, all 19 layers in
order, exact Court counts, nonzero exit for REMANDED/UNPROVEN, corrupt ledger refusal, and no
`seal`, `promote`, `git checkout`, `git merge`, write, retry, browser, clipboard, or terminal path.

- [ ] **Step 3.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/ops/test_revalidate_paeos_lifecycle.py
```

- [ ] **Step 3.3: Implement deterministic report output**

Print one row per L01-L19 with evidence hashes/reason. Include spec/governance hashes and the
verified ledger head. A summary cannot overwrite or omit failed layers.

- [ ] **Step 3.4: Run GREEN and source checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/ops/test_revalidate_paeos_lifecycle.py
```

- [ ] **Step 3.5: Commit**

```bash
git add ops/revalidate_paeos_lifecycle.py \
  tests/ops/test_revalidate_paeos_lifecycle.py
git commit -m "feat(ops): add read-only lifecycle revalidation"
```

---

## Task 4: Audit Historical PAEOS Completion Claims

**Files:**

- Create: `reviews/tasks/PAEOS_L01_L19_OPERATIONAL_REVALIDATION_review.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `MessyChangesNeedsReview.md` only for verified gaps

- [ ] **Step 4.1: Establish immutable audit inputs**

Record target Git history window, exact commits, ledger path/head, state-root manifest, CAS head,
governance/spec hashes, test toolchain, and physical auditor receipt. Do not rely on the prior
worker's statements that all layers completed.

- [ ] **Step 4.2: Enumerate candidate historical runs**

Derive run IDs from verified ledger rows. For each, run the read-only auditor once. Preserve raw
JSON and hashes outside Git runtime state. If no historical run has the necessary event schema,
report that limitation rather than inventing evidence from commits.

- [ ] **Step 4.3: Reproduce tests and non-vacuity for claimed sealed runs**

Re-run only commands bound in evidence. Compare baseline/candidate/verifier results and confirm
that each relevant acceptance test fails against the defective baseline for the intended reason.

- [ ] **Step 4.4: Produce the truth statement**

Separate:

- components implemented in source;
- components covered by tests;
- layers observed in an end-to-end run;
- layers lawfully discharged for Trace-A;
- layers independently audited and sealed;
- gaps that make historical completion operationally unproven.

Record exact Sealed/Remanded/Remediated counts. Do not collapse these categories into “PAEOS is
complete” or “PAEOS is broken.”

- [ ] **Step 4.5: Obtain physically decorrelated audit of the audit**

The L14 reviewer for this disposition must not share the implementation-worker family and must
receive a sealed evidence bundle. A physical identity conflict remands this review.

- [ ] **Step 4.6: Commit only review/debt records**

```bash
git add reviews/tasks/PAEOS_L01_L19_OPERATIONAL_REVALIDATION_review.md \
  PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md MessyChangesNeedsReview.md
git commit -m "docs(review): record operational lifecycle truth"
```

---

## Task 5: Gate SAKG Resumption

**Files:**

- Create: `operations/SAKG_RESUMPTION_MANIFEST.json`
- Create: `reviews/tasks/SAKG_RESUMPTION_DISPOSITION_review.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`

- [ ] **Step 5.1: Compute the verified operating envelope**

List admitted supervisor/worker/auditor profiles, eligible task classes/data classes, lifecycle
layers and transitions proven live, static-debt policy, concurrency, promotion stage, open debt,
open incidents, and reconciliation items. Missing facts reduce the envelope.

- [ ] **Step 5.2: Select a bounded SAKG Trace-A canary**

The task must be reversible, non-protected, isolated, independently verifiable, and expressible in
one frozen implementation contract. It cannot be a constitutional, credential, schema migration,
deployment, external-message, or broad architectural task.

- [ ] **Step 5.3: Freeze the SAKG contract through the verified lifecycle**

Create a new goal/run; do not reuse a recovery authorization or historical task package. Compile
the exact context, base commit, scopes, acceptance commands, rollback, data policy, profiles, and
capability under the proven envelope.

- [ ] **Step 5.4: Obtain the applicable L16 disposition**

If the task or verified envelope requires Founder authority, stop. Otherwise use only the already
ratified standing automatic Trace-A envelope. No agent may broaden that envelope here.

- [ ] **Step 5.5: Run once, audit, and report honestly**

One Cline implementation, independent L13 reproduction, physically decorrelated L14, L15, L16,
mandatory L17, and exact Court counts. A remand goes through remediation; it is not evidence that
the workflow failed.

- [ ] **Step 5.6: Commit the resumption disposition**

```bash
git add operations/SAKG_RESUMPTION_MANIFEST.json \
  reviews/tasks/SAKG_RESUMPTION_DISPOSITION_review.md \
  PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md
git commit -m "docs(review): record SAKG resumption disposition"
```

Expected final outcome is one of: `RESUME_WITHIN_VERIFIED_ENVELOPE`, `REMANDED_FOR_SPECIFIC_GAPS`,
or `HALT_FOR_FOUNDER`. No generic success label is permitted.
