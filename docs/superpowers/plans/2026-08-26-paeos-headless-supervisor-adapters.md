# PAEOS Headless Supervisor Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox syntax for tracking.

**Goal:** Admit and rotate Codex, Antigravity, or another suitable architect-grade model through a
provider-neutral headless protocol, preserving durable PAEOS state across quota loss without
granting a model direct ledger, worker, audit, or promotion authority.

**Architecture:** A supervisor adapter is stateless compute behind a strict request/response
envelope. A local trusted transport records what provider/model/version it actually observed. A
versioned admission profile separately proves protocol compliance and task-class reasoning
capability. The deterministic coordinator owns checkpoints and transactions. Only committed
checkpoints can transfer a claim; ambiguous work remains isolated. Browser automation remains a
non-authoritative compatibility adapter unless it satisfies the same correlation and identity
contract.

**Tech Stack:** Python 3.12, protocols and frozen dataclasses, canonical JSON, CAS, existing model
router/A-08 enforcement, subprocess injection seams, pytest, Ruff, Pyright.

**Spec:** `docs/superpowers/specs/2026-08-26-paeos-ai-supervised-autonomy-design.md` section 6

## Global Constraints

- Depends on the committed transaction-fencing/projection gate.
- A product name, catalog alias, prompt claim, UI label, or model prose is not physical identity.
- `UNVERIFIED_PHYSICAL_IDENTITY` cannot act as architect, L10 adversary, or L14 auditor.
- Admission is bound to task class and the full adapter/policy/model tuple, expires after 30 days
  at most, and expires immediately on any material tuple change.
- A degraded supervisor may process only an already-committed Trace-A classification. It may not
  create, lower, reinterpret, or self-ratify ceremony depth.
- Supervisor output is data until complete schema validation and coordinator commitment.
- Providers and LiteLLM do not hide retry or sub-routing. PAEOS chooses one explicit attempt.
- No credential value, settings file, environment dump, or raw authentication record enters an
  envelope, receipt, trace, fixture, or commit.

---

## Task 1: Define the Provider-Neutral Supervisor Protocol

**Files:**

- Create: `runtime/supervisors/__init__.py`
- Create: `runtime/supervisors/protocol.py`
- Test: `tests/runtime/supervisors/test_protocol.py`
- Reuse: `runtime/integrations/bridge_protocol.py`

**Interfaces:**

```python
class SupervisorTier(StrEnum):
    ARCHITECT = "ARCHITECT"
    DEGRADED_TRACE_A = "DEGRADED_TRACE_A"
    WORKER_ONLY = "WORKER_ONLY"
    QUARANTINED = "QUARANTINED"

@dataclass(frozen=True, slots=True)
class SupervisorRequest:
    request_id: str
    transaction_key: str
    nonce: str
    checkpoint_hash: str
    policy_hash: str
    task_class: str
    prompt_hash: str
    context_manifest_hash: str
    allowed_dispositions: tuple[Disposition, ...]

@dataclass(frozen=True, slots=True)
class TransportObservation:
    provider: str
    actual_model_id: str
    model_family: ModelFamily
    adapter_id: str
    adapter_version: str
    provider_request_id: str
    observed_at: str
    usage: Mapping[str, int]

@dataclass(frozen=True, slots=True)
class SupervisorResponse:
    request_id: str
    transaction_key: str
    nonce: str
    checkpoint_hash: str
    disposition: Disposition
    artifact_refs: tuple[ArtifactRef, ...]
    rationale_ref: Hash

@dataclass(frozen=True, slots=True)
class AdapterResult:
    response_bytes: bytes
    observation: TransportObservation

class SupervisorAdapter(Protocol):
    def invoke(self, request: SupervisorRequest, context: bytes) -> AdapterResult: ...
```

- [ ] **Step 1.1: Write RED canonical-envelope tests**

Test strict UTF-8, exact schema, request/transaction/nonce/checkpoint correlation, allowed
disposition, artifact hash shape, complete response only, unknown fields, conflicting identity,
partial JSON, prose prefixes/suffixes, and payload size limits. Prompt injection inside context
must not become an operation or policy field. The model response cannot supply or override the
separate locally observed `TransportObservation`.

- [ ] **Step 1.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_protocol.py
```

Expected: collection fails because `runtime.supervisors.protocol` does not exist.

- [ ] **Step 1.3: Implement strict codecs and validators**

Reuse bridge identifiers, hashes, `Disposition`, and canonical JSON rules. Parse into immutable
types before any coordinator call. Quarantine raw invalid bytes by content hash; never repair or
infer missing fields from prose. Keep locally trusted transport observation outside model-authored
response bytes and cross-check it against admission/profile data.

- [ ] **Step 1.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_protocol.py
```

Expected: all protocol and injection cases pass.

- [ ] **Step 1.5: Commit**

```bash
git add runtime/supervisors tests/runtime/supervisors/test_protocol.py
git commit -m "feat(supervision): define strict supervisor protocol"
```

---

## Task 2: Add Versioned, Task-Class-Scoped Supervisor Admission

**Files:**

- Create: `runtime/supervisors/admission.py`
- Modify: `paeos/model_router/types.py`
- Modify: `paeos/model_router/a08_enforcer.py`
- Test: `tests/runtime/supervisors/test_admission.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class SupervisorAdmissionProfile:
    profile_id: str
    tier: SupervisorTier
    task_classes: tuple[str, ...]
    provider: str
    actual_model_id: str
    model_family: ModelFamily
    adapter_hash: str
    binary_hash: str
    prompt_hash: str
    policy_hash: str
    sandbox_profile_hash: str
    canary_set_version: str
    admitted_at: str
    expires_at: str

@dataclass(frozen=True, slots=True)
class SupervisorAdmissionDecision:
    admitted: bool
    reason_code: str
    profile_hash: str | None

def decide_supervisor_admission(
    profile: SupervisorAdmissionProfile,
    observation: TransportObservation,
    *,
    task_class: str,
    committed_trace: str,
    now: str,
) -> SupervisorAdmissionDecision: ...
```

- [ ] **Step 2.1: Write RED admission matrix tests**

Cover architect, degraded, worker-only, quarantined, task-class mismatch, expired policy, 30-day
maximum TTL, binary/adapter/prompt/model drift, missing binary hash, opaque alias, family conflict,
and a degraded model presented an uncommitted or Trace-B classification. Serious failures yield a
categorical quarantine reason rather than a lower score.

- [ ] **Step 2.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_admission.py
```

Expected: fails because supervisor admission types and policy do not exist.

- [ ] **Step 2.3: Implement fail-closed admission**

Decision order is: schema -> tuple equality -> physical lineage -> TTL -> quarantine -> task class
-> tier -> precommitted ceremony depth -> rotating-canary status. Return stable reason codes and
hash the complete admitted profile.

- [ ] **Step 2.4: Run GREEN with A-08 tests**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_admission.py \
  tests/model_router/test_generic_decorrelation.py \
  tests/model_router/test_a08_integration.py
```

Expected: all pass; no unknown family becomes eligible.

- [ ] **Step 2.5: Commit**

```bash
git add runtime/supervisors/admission.py paeos/model_router/types.py \
  paeos/model_router/a08_enforcer.py tests/runtime/supervisors/test_admission.py
git commit -m "feat(supervision): gate supervisor profiles by task class"
```

---

## Task 3: Persist Durable Checkpoints and Enforce Clean Rotation

**Files:**

- Create: `runtime/supervisors/checkpoint.py`
- Create: `runtime/supervisors/coordinator.py`
- Test: `tests/runtime/supervisors/test_checkpoint_rotation.py`
- Reuse: `runtime/control_plane/coordinator.py`
- Reuse: `kernel/cas.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class SupervisorCheckpoint:
    schema_version: str
    checkpoint_id: str
    ledger_seq: int
    ledger_head: str
    repository_head: str
    repository_digest: str
    policy_hash: str
    governance_hashes: tuple[tuple[str, str], ...]
    transaction_digests: tuple[tuple[str, str, int], ...]
    open_reconciliation_ids: tuple[str, ...]
    open_debt_ids: tuple[str, ...]
    previous_checkpoint_hash: str | None

def verify_checkpoint(checkpoint: SupervisorCheckpoint, *, ledger: Ledger, repo: Path) -> None: ...

class SupervisorCoordinator:
    def checkpoint(self, *, expected_ledger_head: str) -> ArtifactRef: ...
    def rotate(self, *, from_profile: str, to_profile: str, checkpoint_ref: ArtifactRef) -> None: ...
```

- [ ] **Step 3.1: Write RED handoff tests**

Test clean no-claim rotation, active transferable claim refusal, ambiguous claim isolation,
unrelated-goal continuation, ledger/repository/policy/governance mismatch, broken checkpoint chain,
stale checkpoint, and old adapter responding after rotation. The stale adapter must be fenced.

- [ ] **Step 3.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_checkpoint_rotation.py
```

Expected: fails because durable checkpoint and rotation enforcement are absent.

- [ ] **Step 3.3: Implement CAS checkpoints and coordinator events**

Checkpoint bytes are canonical and content-addressed. Rotation commits `CHECKPOINT_CREATED`,
`SUPERVISOR_RELEASED`, and `SUPERVISOR_ADMITTED` facts through the canonical coordinator. Never
transfer an active claim by copying a PID/session/browser identifier.

- [ ] **Step 3.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_checkpoint_rotation.py \
  tests/runtime/control_plane/test_coordinator.py
```

Expected: all pass; stale post-rotation commits are rejected.

- [ ] **Step 3.5: Commit**

```bash
git add runtime/supervisors/checkpoint.py runtime/supervisors/coordinator.py \
  tests/runtime/supervisors/test_checkpoint_rotation.py
git commit -m "feat(supervision): add durable checkpoint rotation"
```

---

## Task 4: Implement Codex and Antigravity Headless Adapter Seams

**Files:**

- Create: `runtime/supervisors/headless.py`
- Create: `runtime/supervisors/codex.py`
- Create: `runtime/supervisors/antigravity.py`
- Test: `tests/runtime/supervisors/test_headless_adapters.py`
- Modify: `runtime/integrations/__init__.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class HeadlessInvocation:
    argv: tuple[str, ...]
    cwd: Path
    stdin: bytes
    timeout_seconds: float
    environment_keys: tuple[str, ...]

class HeadlessRunner(Protocol):
    def run(self, invocation: HeadlessInvocation) -> HeadlessResult: ...

class CodexSupervisorAdapter(SupervisorAdapter): ...
class AntigravitySupervisorAdapter(SupervisorAdapter): ...
```

- [ ] **Step 4.1: Write RED invocation tests with a fake runner**

Assert shell-free argv, exact bound worktree, minimal environment key allowlist, pinned executable
path/hash, one request/one response, timeout termination, stdout/stderr preservation, provider
observation capture, and no fallback to another executable/model. Missing headless support fails
closed; it never triggers browser/clipboard automation.

- [ ] **Step 4.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_headless_adapters.py
```

Expected: collection fails because adapter implementations do not exist.

- [ ] **Step 4.3: Implement transport-specific encoding only**

Adapters may translate the provider's documented request/response format into the common protocol
and collect local observations. They may not choose task class, retry, commit, dispatch Cline,
select an auditor, or interpret prose as a capability.

- [ ] **Step 4.4: Run GREEN and static checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_headless_adapters.py
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check runtime/supervisors \
  tests/runtime/supervisors
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright runtime/supervisors
```

Expected: all selected checks pass. Do not run a live provider yet.

- [ ] **Step 4.5: Commit**

```bash
git add runtime/supervisors runtime/integrations/__init__.py \
  tests/runtime/supervisors/test_headless_adapters.py
git commit -m "feat(supervision): add headless adapter seams"
```

---

## Task 5: Simulate Quota Loss, Drift, Injection, and Recovery

**Files:**

- Create: `tests/runtime/supervisors/test_failure_matrix.py`
- Create: `tests/fixtures/supervisors/` fixtures containing no secrets
- Modify: `runtime/supervisors/coordinator.py`

- [ ] **Step 5.1: Add the RED failure matrix**

Inject quota loss in NEW, PREPARED, CLAIMED, RESPONDED, and post-response/pre-consume boundaries;
partial streams; hung response; malformed output; conflicting physical receipts; policy expiry;
provider sub-routing; stale checkpoint; prompt injection; fake Founder approval; self-ratification;
and old-adapter late response.

- [ ] **Step 5.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_failure_matrix.py
```

Expected: the first missing fail-closed behavior fails. Preserve its exact output before fixing.

- [ ] **Step 5.3: Implement only the failing policy paths**

Pre-acceptance quota failure may be eligible for one coordinator-authorized new attempt. Any
accepted or ambiguous attempt enters reconciliation. Invalid bytes are quarantined. No adapter
contains a sleep-and-retry loop.

- [ ] **Step 5.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/supervisors
```

Expected: all supervisor tests pass; every failure has a stable reason and durable raw evidence.

- [ ] **Step 5.5: Commit**

```bash
git add runtime/supervisors tests/runtime/supervisors tests/fixtures/supervisors
git commit -m "test(supervision): prove quota-safe adapter recovery"
```

---

## Task 6: L13, L14, and L17 Gate

**Files:**

- Create: `reviews/tasks/PAEOS_HEADLESS_SUPERVISOR_ADAPTERS_review.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `MessyChangesNeedsReview.md` only for unresolved debt

- [ ] **Step 6.1: Run the full applicable suite fresh**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors tests/runtime/control_plane tests/model_router
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q
git diff --check
```

- [ ] **Step 6.2: Prove rotating canaries are hidden and killed**

Use Z0-held variants for instruction fidelity, seeded architecture defect, raw-evidence
separation, restart, privacy, self-ratification, and prompt injection. Record installed/reached/
killed evidence. A miss quarantines the exact profile.

- [ ] **Step 6.3: Obtain physically decorrelated L14 audit**

The auditor receives a sealed evidence bundle and a receipt proving a different physical family
from the adapter builder. An adapter cannot audit its own implementation or admission profile.

- [ ] **Step 6.4: Record L17 and stop before production dispatch**

Report exact Court counts and outstanding debt. This plan qualifies supervision; it does not
authorize Cline production work, live SAKG work, or promotion.

- [ ] **Step 6.5: Commit review records**

```bash
git add PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md MessyChangesNeedsReview.md \
  reviews/tasks/PAEOS_HEADLESS_SUPERVISOR_ADAPTERS_review.md
git commit -m "docs(review): record supervisor adapter disposition"
```
