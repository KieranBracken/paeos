# PAEOS Headless Supervisor Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox syntax for tracking.

**Goal:** Admit and rotate Codex, Antigravity, or another suitable architect-grade model through a
provider-neutral headless protocol, preserving durable PAEOS state across quota loss without
granting a model direct ledger, worker, audit, or promotion authority.

**Architecture:** Preserve `AgentRuntime` as the existing worker/stage execution seam and add a
distinct supervisor protocol only for overseer semantics. Existing runtime integrations and model
router facilities are wrapped or extended through a descriptor-driven registry; they are not
duplicated. A local trusted transport records what provider/model/version it actually observed,
while a versioned admission profile separately proves protocol compliance and task-class reasoning
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
- `runtime.claude_code.AgentRuntime`, `runtime.agents.RoleSpec`, and the model-router catalog,
  health, privacy, and A-08 machinery remain the canonical existing seams for their current roles.
- Every task records one reuse disposition for each touched seam: `REUSE_UNCHANGED`, `EXTEND_WRAP`,
  or `REPLACE_WITH_MIGRATION_EVIDENCE`. No implementation starts from filenames alone.
- Provider-specific imports, endpoints, wire formats, and retry behavior may not enter the
  supervisor coordinator or transaction reducer.
- A conforming synthetic provider must register and execute contract tests without modifying the
  coordinator, lifecycle engine, transaction reducer, or audit-policy source.
- The existing closed `ProviderId` enum and hard-coded transport branches are compatibility debt;
  new supervisor code must not expand that pattern.

## Existing-Seam Baseline and Reuse Decisions

The following inventory is binding for this plan:

- `runtime.claude_code.AgentRuntime` / `RunOutput`: `REUSE_UNCHANGED` for scoped worker and
  lifecycle-stage execution. Supervisor adapters do not implement worker authority.
- `ClaudeCodeRuntime`, `AntigravityRuntime`, `ChatBridgeRuntime`, and `HybridRuntime`:
  `EXTEND_WRAP`. Reuse invocation and workspace helpers where their contracts are sound.
- `paeos.model_router.ModelRouter`, catalog, state, privacy, and A-08: `EXTEND_WRAP`. Preserve
  policy behavior behind provider descriptors through the separate provider-registry migration
  plan.
- `ProviderId` and `PROVIDER_API_BASES`: `REPLACE_WITH_MIGRATION_EVIDENCE`. Retain compatibility
  while removing new-core dependence through the separate provider-registry migration plan.
- `runtime.agents.RoleSpec`: `REUSE_UNCHANGED`. Supervisor admission references, but does not
  duplicate, role facts.
- `runtime.integrations.bridge_protocol`: `REUSE_UNCHANGED` where compatible. Stricter supervisor
  fields extend it compositionally.

Before changing any listed seam, the implementer must run:

```bash
rg -n "AgentRuntime|RoleSpec|ProviderId|PROVIDER_API_BASES|ModelRouter|Runtime" \
  runtime paeos tests --glob '*.py'
```

The resulting commit message or review record must state the applicable disposition and cite the
discriminative test that protects it.

---

## Task 1: Define the Provider-Neutral Supervisor Protocol

**Files:**

- Create: `runtime/supervisors/__init__.py`
- Create: `runtime/supervisors/protocol.py`
- Test: `tests/runtime/supervisors/test_protocol.py`
- Reuse: `runtime/integrations/bridge_protocol.py`
- Reuse unchanged: `runtime/claude_code.py` (`AgentRuntime`, `RunOutput`)

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

`SupervisorAdapter` is deliberately not a subtype of `AgentRuntime`: the former returns bounded
architectural data and observations; the latter executes scoped worker packages and may return
writes. Add a type-level test showing that the coordinator accepts only `SupervisorAdapter`, while
`AgentDispatcher` continues to accept the existing `AgentRuntime` implementations unchanged.

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

## Task 4: Add the Descriptor-Driven Supervisor Adapter Registry

**Files:**

- Create: `runtime/supervisors/registry.py`
- Test: `tests/runtime/supervisors/test_adapter_registry.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class SupervisorAdapterDescriptor:
    adapter_id: str
    adapter_version: str
    provider_key: str
    factory: Callable[[], SupervisorAdapter]

class SupervisorAdapterRegistry:
    def register(self, descriptor: SupervisorAdapterDescriptor) -> None: ...
    def resolve(self, adapter_id: str) -> SupervisorAdapterDescriptor: ...
```

- [ ] **Step 4.1: Write RED registry and compatibility tests**

Register a synthetic `future-supervisor` entirely from the test. Assert it is resolved and selected
without editing coordinator tables, duplicate IDs fail closed, unknown IDs fail closed, and invalid
adapter/provider keys are rejected. Add an AST assertion that supervisor coordinator and
transaction reducer modules contain no provider-name branches or provider-specific imports. Model
provider registration is proved independently by the provider-registry migration plan.

- [ ] **Step 4.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_adapter_registry.py
```

Expected: collection fails because registry modules do not exist.

- [ ] **Step 4.3: Implement immutable registries and legacy compatibility**

Validate descriptor keys and reject duplicate registration. Do not add dynamic filesystem
discovery, arbitrary import strings, or executable code in configuration. Registration occurs
through trusted Python composition at startup. Consume provider keys supplied by the provider
registry without reproducing provider catalogs or routing policy in this module.

- [ ] **Step 4.4: Run GREEN and static checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_adapter_registry.py
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check runtime/supervisors \
  tests/runtime/supervisors
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright runtime/supervisors
```

Expected: all selected checks pass; the synthetic provider test proves extension without core
source modification.

- [ ] **Step 4.5: Commit**

```bash
git add runtime/supervisors/registry.py \
  tests/runtime/supervisors/test_adapter_registry.py
git commit -m "feat(supervision): register adapters without coordinator branches"
```

---

## Task 5: Wrap Existing Transports as Headless Supervisor Adapters

**Files:**

- Create: `runtime/supervisors/headless.py`
- Create: `runtime/supervisors/codex.py`
- Create: `runtime/supervisors/antigravity.py`
- Modify: `runtime/integrations/__init__.py`
- Reuse: `runtime/integrations/antigravity.py`
- Reuse: `runtime/integrations/chat_bridge.py`
- Test: `tests/runtime/supervisors/test_headless_adapters.py`

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

- [ ] **Step 5.1: Write RED invocation and reuse tests with a fake runner**

Assert shell-free argv, exact bound worktree, minimal environment key allowlist, pinned executable
path/hash, one request/one response, timeout termination, stdout/stderr preservation, provider
observation capture, and no fallback to another executable/model. Missing headless support fails
closed; it never triggers browser/clipboard automation. Characterize and reuse existing prompt,
workspace, and invocation helpers only when their output satisfies the stricter supervisor
contract; explicitly test that no worker write-collection or worker authority crosses the wrapper.

- [ ] **Step 5.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_headless_adapters.py
```

Expected: collection fails because headless supervisor implementations do not exist.

- [ ] **Step 5.3: Implement thin transport-specific wrappers**

Adapters translate documented request/response formats into the common protocol and collect local
observations. Factor shared invocation primitives from existing integrations only when their
behavior is already covered by characterization tests. Adapters may not choose task class, retry,
commit, dispatch Cline, select an auditor, collect worker writes, or interpret prose as a
capability. Register both adapters through `SupervisorAdapterRegistry`; do not add coordinator
branches for Codex or Antigravity.

- [ ] **Step 5.4: Run GREEN and static checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_headless_adapters.py \
  tests/runtime/test_live_adapter.py \
  tests/runtime/test_chat_bridge_fail_closed.py
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check runtime/supervisors \
  runtime/integrations tests/runtime/supervisors
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright runtime/supervisors runtime/integrations
```

Expected: supervisor and existing worker-adapter tests pass. Do not run a live provider yet.

- [ ] **Step 5.5: Commit**

```bash
git add runtime/supervisors runtime/integrations \
  tests/runtime/supervisors/test_headless_adapters.py
git commit -m "feat(supervision): wrap existing transports for headless oversight"
```

---

## Task 6: Simulate Quota Loss, Drift, Injection, and Recovery

**Files:**

- Create: `tests/runtime/supervisors/test_failure_matrix.py`
- Create: `tests/fixtures/supervisors/` fixtures containing no secrets
- Modify: `runtime/supervisors/coordinator.py`

- [ ] **Step 6.1: Add the RED failure matrix**

Inject quota loss in NEW, PREPARED, CLAIMED, RESPONDED, and post-response/pre-consume boundaries;
partial streams; hung response; malformed output; conflicting physical receipts; policy expiry;
provider sub-routing; stale checkpoint; prompt injection; fake Founder approval; self-ratification;
and old-adapter late response.

- [ ] **Step 6.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors/test_failure_matrix.py
```

Expected: the first missing fail-closed behavior fails. Preserve its exact output before fixing.

- [ ] **Step 6.3: Implement only the failing policy paths**

Pre-acceptance quota failure may be eligible for one coordinator-authorized new attempt. Any
accepted or ambiguous attempt enters reconciliation. Invalid bytes are quarantined. No adapter
contains a sleep-and-retry loop.

- [ ] **Step 6.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/supervisors
```

Expected: all supervisor tests pass; every failure has a stable reason and durable raw evidence.

- [ ] **Step 6.5: Commit**

```bash
git add runtime/supervisors tests/runtime/supervisors tests/fixtures/supervisors
git commit -m "test(supervision): prove quota-safe adapter recovery"
```

---

## Task 7: L13, L14, and L17 Gate

**Files:**

- Create: `reviews/tasks/PAEOS_HEADLESS_SUPERVISOR_ADAPTERS_review.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `MessyChangesNeedsReview.md` only for unresolved debt

- [ ] **Step 7.1: Run the full applicable suite fresh**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/supervisors tests/runtime/control_plane tests/model_router
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q
git diff --check
```

- [ ] **Step 7.2: Prove rotating canaries are hidden and killed**

Use Z0-held variants for instruction fidelity, seeded architecture defect, raw-evidence
separation, restart, privacy, self-ratification, and prompt injection. Record installed/reached/
killed evidence. A miss quarantines the exact profile.

- [ ] **Step 7.3: Obtain physically decorrelated L14 audit**

The auditor receives a sealed evidence bundle and a receipt proving a different physical family
from the adapter builder. An adapter cannot audit its own implementation or admission profile.

- [ ] **Step 7.4: Record L17 and stop before production dispatch**

Report exact Court counts and outstanding debt. This plan qualifies supervision; it does not
authorize Cline production work, live SAKG work, or promotion.

- [ ] **Step 7.5: Commit review records**

```bash
git add PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md MessyChangesNeedsReview.md \
  reviews/tasks/PAEOS_HEADLESS_SUPERVISOR_ADAPTERS_review.md
git commit -m "docs(review): record supervisor adapter disposition"
```
