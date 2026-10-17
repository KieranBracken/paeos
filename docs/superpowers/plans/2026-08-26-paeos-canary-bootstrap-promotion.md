# PAEOS Canary, Bootstrap, and Promotion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. This plan
> contains a mandatory Founder stop; no agent may execute beyond it by inference.

**Goal:** Prove the repaired control plane under hidden fault injection, prepare a non-self-
authorizing Founder bootstrap bundle, and only after separate Founder L16 integration enable
single-use exact-ref promotion for later reversible, non-protected Trace-A work.

**Architecture:** An activation evaluator derives counters solely from correlated ledger/CAS
evidence. Hidden canaries prove seeded defects were installed, reached, and killed. Before
bootstrap, promotion code is present only on the recovery branch and cannot obtain a valid
bootstrap fact or capability. After a separate Founder integration, the kernel may mint a normal
`CapabilityToken` whose single exact operation encodes repository, target ref, expected head, and
reviewed commit. The controller can call `git update-ref <ref> <new> <old>` once; it cannot edit,
merge, rebase, resolve conflicts, or push.

**Tech Stack:** Python 3.12, existing ledger/CAS/capability/classifier/seal/review components,
isolated Git worktrees, Git plumbing, hidden Z0 fixtures, pytest, Ruff, Pyright.

**Spec:** `docs/superpowers/specs/2026-08-26-paeos-ai-supervised-autonomy-design.md` sections 11-13

## Global Constraints

- Depends on all earlier program gates and an exact static-debt disposition.
- Before live remote probes, rotate/refresh the exposed credential and revoke the old material.
  This is an operator bootstrap action; automation must not read or log the credential.
- Promotion code and tests cannot bootstrap their own authority. A Founder-authored L16 ledger fact
  committed after independent review is mandatory.
- Protected kernel, lifecycle, constitution, authority, credential, signing-domain, policy, and
  promotion-controller changes always stop for Founder ratification.
- Automatic scope is repository ref integration only. No deployment, migration, financial action,
  credential action, external message, or other side effect is authorized.
- A changed target head invalidates review. Do not autonomously rebase or resolve conflicts.
- Correct remands do not reset an activation window. Critical escapes do.

---

## Task 1: Derive Activation State from Correlated Evidence

**Files:**

- Create: `runtime/autonomy/__init__.py`
- Create: `runtime/autonomy/activation.py`
- Test: `tests/runtime/autonomy/test_activation.py`

**Interfaces:**

```python
class ActivationStage(StrEnum):
    SUPERVISED_RECOVERY_ONLY = "SUPERVISED_RECOVERY_ONLY"
    ISOLATED_CANARY = "ISOLATED_CANARY"
    AWAITING_FOUNDER_BOOTSTRAP = "AWAITING_FOUNDER_BOOTSTRAP"
    SINGLE_FLIGHT_PROMOTION = "SINGLE_FLIGHT_PROMOTION"
    BROADER_TRACE_A = "BROADER_TRACE_A"

@dataclass(frozen=True, slots=True)
class ActivationCounts:
    admitted_route_probes: int
    end_to_end_trace_a: int
    clean_rotations: int
    forced_quota_stops: int
    automatic_promotions: int
    sealed: int
    remanded: int
    remediated: int
    critical_failures: int

@dataclass(frozen=True, slots=True)
class ActivationDecision:
    stage: ActivationStage
    counts: ActivationCounts
    blocking_reason_codes: tuple[str, ...]
    evidence_head: str

def evaluate_activation(rows: Sequence[LedgerRow], cas: CAS) -> ActivationDecision: ...
```

- [ ] **Step 1.1: Write RED counter and correlation tests**

Test exact minimums, duplicate evidence, uncorrelated claims, worker prose, stale receipts,
healthy remands, remediated remands, critical escape, missed Z0 canary, unsafe replay, provenance
conflict, and wrong route/profile. Counts come from distinct transaction IDs and verified hashes.

- [ ] **Step 1.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/autonomy/test_activation.py
```

Expected: collection fails because activation evaluation does not exist.

- [ ] **Step 1.3: Implement pure evidence derivation**

Require three admitted route probes per route, three end-to-end Trace-A canaries, one clean
rotation, one forced quota-stop, then—only post-bootstrap—five automatic promotions at concurrency
one. Any critical failure returns to the safest stage and quarantines the exact tuple.

- [ ] **Step 1.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/autonomy/test_activation.py
```

- [ ] **Step 1.5: Commit**

```bash
git add runtime/autonomy tests/runtime/autonomy/test_activation.py
git commit -m "feat(autonomy): derive activation from correlated evidence"
```

---

## Task 2: Build the Hidden Mutation and Fault-Injection Harness

**Files:**

- Create: `runtime/autonomy/canary.py`
- Create: `tests/runtime/autonomy/test_canary_harness.py`
- Create: `tests/fixtures/autonomy/public/`
- Create: `tests/fixtures/autonomy/z0/` with repository access restricted to the verifier

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class CanaryManifest:
    canary_id: str
    version: str
    target_hash: str
    mutation_hash: str
    expected_failure_code: str
    installer_hash: str

@dataclass(frozen=True, slots=True)
class CanaryResult:
    canary_id: str
    installed: bool
    reached: bool
    killed: bool
    observed_failure_code: str | None
    evidence_refs: tuple[str, ...]

def adjudicate_canary(manifest: CanaryManifest, observations: Sequence[Event]) -> CanaryResult: ...
```

- [ ] **Step 2.1: Write RED non-vacuity tests**

Test not installed, installed but not reached, reached but survived, wrong failure reason, builder
modified canary, builder learned hidden expected reason, stale canary version, replayed evidence,
and a true installed/reached/killed result. Every incomplete triple fails.

- [ ] **Step 2.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/autonomy/test_canary_harness.py
```

- [ ] **Step 2.3: Implement verifier-owned manifests**

Store hidden content in the verifier view/Z0, not the builder worktree or prompt. Public fixtures
may describe failure classes but not hidden instances or expected hashes. Record installed,
reached, and killed as separately reproduced facts.

- [ ] **Step 2.4: Add the required fault catalog**

Include stale/competing claims, symlink/scope escape, duplicate response, quota loss in every
state, hung model/tool, vacuous evidence, baseline contamination, homogeneous audit, misleading
completion, pre/post-side-effect crash, prompt injection, opaque alias, policy expiry, resource
exhaustion, stale target head, projection poisoning, partial supervisor response, and false
physical provenance.

- [ ] **Step 2.5: Run GREEN and commit**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/autonomy/test_canary_harness.py
git add runtime/autonomy/canary.py tests/runtime/autonomy/test_canary_harness.py \
  tests/fixtures/autonomy
git commit -m "test(autonomy): require installed reached killed canaries"
```

---

## Task 3: Run the No-Promotion Canary Ladder

**Files:**

- Create: `ops/run_autonomy_canary.py`
- Test: `tests/ops/test_run_autonomy_canary.py`
- Create at execution time: immutable evidence under the configured external state root, not Git
- Modify after execution: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`

- [ ] **Step 3.1: Verify prerequisites without reading secrets**

Record only that the credential rotation/revocation prerequisite is attested complete, the
admitted route/profile hashes, binary hashes, policy hashes, verified ledger head, and clean
isolated worktree. If the operator prerequisite is absent, stop before invocation.

- [ ] **Step 3.2: Write and run RED CLI contract tests**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/ops/test_run_autonomy_canary.py
```

Assert one canary per invocation, no retry loop, no promotion operation, unique transaction,
bounded sandbox, exact task package, raw evidence retention, and nonzero exit on remand/halt.

- [ ] **Step 3.3: Implement the one-shot CLI and run synthetic canaries**

Run three distinct end-to-end Trace-A canaries in fresh synthetic repositories, then one clean
Codex/Antigravity rotation and one forced quota-stop simulation. Stop on each result, reconcile
raw evidence, and require a distinct authorized invocation for the next.

- [ ] **Step 3.4: Run one isolated PAEOS canary and shadow task**

Only after synthetic evidence is independently green, run one low-risk isolated PAEOS task with
no promotion capability, then shadow a real task without applying its decision. A valid remand is
recorded as healthy behavior.

- [ ] **Step 3.5: Compute the activation decision**

Expected stage: `AWAITING_FOUNDER_BOOTSTRAP` only if every pre-bootstrap minimum is proven and
there are zero critical failures. Otherwise remain `SUPERVISED_RECOVERY_ONLY` or
`ISOLATED_CANARY` with exact blockers.

- [ ] **Step 3.6: Commit code and notebook records, never runtime evidence**

```bash
git add ops/run_autonomy_canary.py tests/ops/test_run_autonomy_canary.py \
  PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md
git commit -m "test(autonomy): record no-promotion canary ladder"
```

---

## Task 4: Resolve the Static-Gate Bootstrap Blocker

**Files:**

- Modify only the exact files implicated by new-code Ruff/Pyright findings
- Create if inherited debt remains: `operations/STATIC_DEBT_BASELINE.json`
- Create if inherited debt remains: `operations/STATIC_DEBT_BASELINE_POLICY.md`
- Create: `tests/ops/test_static_debt_baseline.py`

- [ ] **Step 4.1: Run the real gates once and preserve raw output**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check .
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright
```

Do not rerun an identical failing command until a code change or separately authorized baseline
policy gives a new rationale.

- [ ] **Step 4.2: Make all new/changed code green**

No baseline may excuse a finding introduced or moved by this program.

- [ ] **Step 4.3: Choose one honest repository-wide disposition**

Either repair all inherited findings, or prepare an exact baseline containing tool versions,
configuration hashes, finding fingerprints, file/content hashes, and counts. The policy permits
only unchanged fingerprints and fails if a finding changes location/content or the count grows.

- [ ] **Step 4.4: Obtain Founder ratification if a baseline is used**

The baseline is invalid until the Founder explicitly ratifies its exact hash. This cannot be
delegated to a supervisor, worker, auditor, or this plan.

- [ ] **Step 4.5: Test and commit the disposition**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/ops/test_static_debt_baseline.py
git add operations/STATIC_DEBT_BASELINE.json \
  operations/STATIC_DEBT_BASELINE_POLICY.md tests/ops/test_static_debt_baseline.py
git commit -m "chore(quality): bind inherited static debt baseline"
```

Omit nonexistent baseline files from `git add` when the repository-wide gates are fully repaired.

---

## Task 5: Implement a Dormant Single-Use Exact-Ref Promotion Controller

**Files:**

- Create: `kernel/promotion.py`
- Create: `runtime/autonomy/promotion.py`
- Test: `tests/kernel/test_promotion_policy.py`
- Test: `tests/runtime/autonomy/test_promotion_controller.py`
- Reuse: `kernel/capability.py`
- Reuse: `kernel/classifier.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class PromotionIntent:
    repository_id: str
    target_ref: str
    expected_target_head: str
    reviewed_commit: str
    disposition_hash: str
    rollback_commit: str
    health_command_id: str
    expires_seq: int

def promotion_operation(intent: PromotionIntent) -> str: ...
def evaluate_promotion(intent: PromotionIntent, evidence: PromotionEvidence) -> tuple[str, ...]: ...

class PromotionController:
    def promote(self, intent: PromotionIntent, token: CapabilityToken) -> PromotionReceipt: ...
```

The token contains exactly one operation string derived from the complete canonical intent. The
kernel cannot mint that operation unless a later Founder bootstrap fact is present, so the
controller is mechanically dormant throughout this task.

- [ ] **Step 5.1: Write RED policy and dormant-bootstrap tests**

Test missing Founder bootstrap fact, Trace-B, HARD/protected paths, stale L11/L13/L14/L15, same
builder/auditor family, debt/incident/reconciliation, missing rollback, wrong repository/ref/head/
commit/disposition, expired/used token, competing promotion, and concurrency greater than one.
Prove the controller cannot create or ratify the missing bootstrap fact.

- [ ] **Step 5.2: Write RED Git-plumbing tests in disposable repositories**

Test exact `git update-ref ref reviewed expected`, explicit fast-forward ancestry, target-head
race, non-fast-forward, conflict, attempted rebase, unrelated ref, edit attempt, second use, crash
before update, crash after update, health pass, and health failure. The precomputed
`rollback_commit` must have `reviewed_commit` as its sole parent and the exact tree of
`expected_target_head`; health failure advances the ref to that rollback commit only when the ref
still equals `reviewed_commit`. A later integration forces HALT.

- [ ] **Step 5.3: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/kernel/test_promotion_policy.py \
  tests/runtime/autonomy/test_promotion_controller.py
```

- [ ] **Step 5.4: Implement deny-by-default dormant policy and exact update-ref**

Use existing conservative `classify_paths()` for protected classification. Verify the token via
`CapabilityBroker.verify()`. Invoke Git shell-free with an absolute pinned binary. Prove
`expected_target_head` is an ancestor of `reviewed_commit`, and validate the rollback commit's
parent/tree before any update. Persist the prepared promotion transaction before `update-ref`.
After the ref side effect, commit token consumption and the promotion receipt; a crash in between
is reconciled from the exact ref state and is never replayed as a second update.

- [ ] **Step 5.5: Run GREEN and mutations**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/kernel/test_promotion_policy.py \
  tests/runtime/autonomy/test_promotion_controller.py
```

Kill mutations that remove bootstrap proof, ancestry, expected-head comparison, token
consumption, protected-path check, auditor decorrelation, health check, crash reconciliation, or
rollback parent/tree validation.

- [ ] **Step 5.6: Commit the still-dormant controller**

```bash
git add kernel/promotion.py runtime/autonomy/promotion.py \
  tests/kernel/test_promotion_policy.py \
  tests/runtime/autonomy/test_promotion_controller.py
git commit -m "feat(autonomy): gate dormant exact-ref promotion"
```

Expected: all tests pass, but every real promotion attempt remains blocked because no Founder
bootstrap fact or promotion token exists.

---

## Task 6: Prepare the Founder Bootstrap Evidence Bundle

**Files:**

- Create: `reviews/tasks/PAEOS_AUTONOMY_BOOTSTRAP_review.md`
- Create: `operations/PAEOS_AUTONOMY_BOOTSTRAP_MANIFEST.json`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`

- [ ] **Step 6.1: Independently reproduce all pre-bootstrap evidence**

Verify ledger/projection head, route probes, supervisor rotation, quota stop, three Trace-A
canaries, sandbox boundaries, physical receipts, L14 family inequality, static-gate disposition,
repository diff, commits, and the dormant controller's inability to mint authority.

- [ ] **Step 6.2: Build a hash-bound manifest**

Bind exact candidate commit, expected target head, governance/spec hashes, toolchain hashes,
test/static results, review bundle, rollback procedure, open debt/incidents/reconciliation, and
exact Sealed/Remanded/Remediated counts.

- [ ] **Step 6.3: Obtain a physically decorrelated L14 bootstrap audit**

The auditor cannot be a builder or supervisor family and sees only sealed evidence. A missing,
opaque, or conflicting receipt remands bootstrap.

- [ ] **Step 6.4: Commit the evidence manifest on the recovery branch**

```bash
git add operations/PAEOS_AUTONOMY_BOOTSTRAP_MANIFEST.json \
  reviews/tasks/PAEOS_AUTONOMY_BOOTSTRAP_review.md \
  PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md
git commit -m "docs(review): prepare autonomy bootstrap disposition"
```

- [ ] **Step 6.5: MANDATORY STOP FOR FOUNDER L16 DISPOSITION**

Do not merge, update main/trunk, mint promotion authority, or continue to Task 7. Present the exact
manifest hash and candidate/target commits to the Founder. Only a new explicit Founder approval
of that exact bundle authorizes bootstrap integration.

---

## Task 7: Run the Post-Bootstrap Single-Flight Window

**Precondition:** A separate Founder L16 bootstrap integration is committed in the canonical
ledger, the installed target contains the reviewed dormant controller, and the kernel verifies
that exact bootstrap manifest before minting the first promotion capability.

**Files:**

- Create: `ops/run_trace_a_promotion_canary.py`
- Test: `tests/ops/test_trace_a_promotion_canary.py`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`

- [ ] **Step 7.1: Test the run-once canary CLI**

Require exact approved intent/token, one transaction, one ref, one promotion attempt, one health
check, no retry, no rebase, and raw evidence retention.

- [ ] **Step 7.2: Run one reversible Trace-A promotion**

Stop and independently reconcile it before authorizing another. A valid remand does not count as
a promotion and does not reset the window. Any critical failure quarantines the exact route.

- [ ] **Step 7.3: Repeat with four distinct authorized canaries**

Each uses a fresh transaction, contract, candidate commit, expected head, capability, and
physically decorrelated audit. Concurrency remains one.

- [ ] **Step 7.4: Derive activation state**

Expected `BROADER_TRACE_A` only when all five promotions and every earlier minimum are correlated
and no critical failure exists. The stage does not authorize protected or external side effects.

- [ ] **Step 7.5: Commit code and records**

```bash
git add ops/run_trace_a_promotion_canary.py \
  tests/ops/test_trace_a_promotion_canary.py \
  PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md
git commit -m "test(autonomy): record single-flight promotion window"
```

---

## Task 8: L17 Review and Program Handoff

**Files:**

- Create: `reviews/tasks/PAEOS_CANARY_BOOTSTRAP_PROMOTION_review.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `MessyChangesNeedsReview.md` only for unresolved debt

- [ ] **Step 8.1: Run all applicable tests and static gates fresh**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/autonomy \
  tests/kernel/test_promotion_policy.py tests/ops/test_run_autonomy_canary.py \
  tests/ops/test_trace_a_promotion_canary.py
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check .
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright
git diff --check
```

- [ ] **Step 8.2: Perform mandatory L17 10-point review**

Record authority, evidence non-vacuity, failure discrimination, replay safety, physical
decorrelation, protected-path policy, static debt, rollback, exact Court counts, and residual
risks. Route every lesson to L18/L19, Proposal, Debt, or discard-with-reason.

- [ ] **Step 8.3: Commit and hand off to lifecycle revalidation**

```bash
git add reviews/tasks/PAEOS_CANARY_BOOTSTRAP_PROMOTION_review.md \
  PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md MessyChangesNeedsReview.md
git commit -m "docs(review): record autonomy activation disposition"
```
