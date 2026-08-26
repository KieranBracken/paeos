# PAEOS TaskPackage Worker Confinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox syntax for tracking.

**Goal:** Turn a frozen L11 implementation contract into the only production authority Cline can
exercise, using existing `TaskPackage`/`CapabilityToken` contracts, typed broker operations,
provenance-tagged context, exact egress manifests, and fail-closed OS confinement.

**Architecture:** The deterministic compiler reads committed lifecycle artifacts and emits a
frozen execution binding inside the existing `TaskPackage`. The kernel `CapabilityBroker` mints
the only authority token. A production broker exposes typed operations and constructs shell-free
commands itself; raw worker shell is denied. Route admission is a prerequisite fact, never a
permission. Baseline, candidate, and verifier views are immutable and separated. Sandbox support
is capability-detected and fails closed when a required network/process/disk boundary cannot be
enforced.

**Tech Stack:** Python 3.12, frozen dataclasses, Ed25519 capabilities, CAS, pathlib-safe path
resolution, OS resource limits/process groups, provider-independent tool broker, pytest,
Hypothesis, Ruff, Pyright.

**Spec:** `docs/superpowers/specs/2026-08-26-paeos-ai-supervised-autonomy-design.md` sections 7-8

## Global Constraints

- Depends on admitted worker route, fenced transactions, and admitted supervisor.
- Do not create a second Worker Contract or permission authority. Contract and recovery metadata
  compile into `TaskPackage`; only `CapabilityToken` grants operations.
- A model cannot mint, relabel, extend, refresh, or interpret its own token.
- Raw shell, unrestricted repository search, skills, subagents, model selection, lifecycle
  mutation, verdict submission, and promotion are denied by default.
- Builder-visible text is provenance-tagged data. Embedded instructions never grant authority.
- Data classification fails conservative. SECRET bytes never leave the local host. Secret
  scanning is additive and never the primary boundary.
- Scope expansion returns a structured request; the worker cannot edit the frozen contract.
- If required OS confinement is unavailable, the task does not run with weaker silent fallback.

---

## Task 1: Define the Frozen Implementation Contract and Execution Binding

**Files:**

- Create: `runtime/implementation_contract.py`
- Modify: `runtime/task_package.py`
- Test: `tests/runtime/test_implementation_contract.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class AcceptanceCommand:
    command_id: str
    argv: tuple[str, ...]
    cwd: str
    timeout_seconds: int
    expected_exit_codes: tuple[int, ...]

@dataclass(frozen=True, slots=True)
class FrozenImplementationContract:
    contract_id: str
    contract_hash: str
    goal_id: str
    run_id: str
    ceremony_trace: str
    base_commit: str
    allowed_paths: tuple[str, ...]
    required_artifacts: tuple[str, ...]
    acceptance_commands: tuple[AcceptanceCommand, ...]
    rollback_argv: tuple[str, ...]
    data_class: str
    context_manifest_hash: str
    derivation_register_hash: str

@dataclass(frozen=True, slots=True)
class ExecutionBinding:
    transaction_key: str
    contract_id: str
    contract_hash: str
    base_commit: str
    worktree: str
    worker_profile_hash: str
    supervisor_profile_hash: str
    policy_hash: str
    sandbox_profile_hash: str
    binary_hashes: tuple[tuple[str, str], ...]
    egress_manifest_hash: str
```

Add `execution_binding: ExecutionBinding | None = None` to `TaskPackage` for compatibility, but
the new production dispatch path must reject `None`.

- [ ] **Step 1.1: Write RED contract-validation tests**

Cover canonical hash mismatch, goal/run mismatch, uncommitted ceremony trace, non-commit base,
absolute/traversal paths, empty acceptance set, shell metacharacters represented as a single argv
string, missing rollback, missing CER-6 register, and a binding whose worker profile was admitted
for another task class.

- [ ] **Step 1.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_implementation_contract.py
```

Expected: collection fails because the contract and binding types do not exist.

- [ ] **Step 1.3: Implement immutable validation and canonical hashing**

Do not accept worker or supervisor assertions that the contract is frozen. The compiler's caller
must supply the committed ledger/CAS references; hash bytes canonically and compare them before
construction.

- [ ] **Step 1.4: Run GREEN with TaskPackage tests**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_implementation_contract.py tests/runtime/test_dispatcher.py
```

Expected: all pass; legacy test packages remain constructible, while production validation
requires a binding.

- [ ] **Step 1.5: Commit**

```bash
git add runtime/implementation_contract.py runtime/task_package.py \
  tests/runtime/test_implementation_contract.py
git commit -m "feat(runtime): bind frozen contracts to task packages"
```

---

## Task 2: Compile Provenance-Tagged Context and Exact Egress Policy

**Files:**

- Modify: `runtime/context_compiler.py`
- Create: `runtime/data_policy.py`
- Modify: `paeos/model_router/types.py`
- Modify: `paeos/model_router/privacy.py`
- Test: `tests/runtime/test_context_provenance.py`
- Test: `tests/runtime/test_data_policy.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class ContextEntry:
    ref: ArtifactRef
    source: str
    source_hash: str
    data_class: DataClass
    trust: str
    purpose: str

@dataclass(frozen=True, slots=True)
class PrivacyPolicySnapshot:
    provider: str
    policy_version: str
    policy_hash: str
    observed_at: str
    expires_at: str
    allows_internal: bool
    allows_confidential: bool
    trains_on_inputs: bool
    retains_prompts: bool

@dataclass(frozen=True, slots=True)
class EgressManifest:
    provider: str
    policy_hash: str
    entries: tuple[tuple[str, int, str], ...]  # content hash, byte length, data class
    total_bytes: int

def compile_egress_manifest(
    entries: Sequence[ContextEntry], policy: PrivacyPolicySnapshot
) -> EgressManifest: ...
```

Reuse `paeos.model_router.types.DataClass` (`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `SECRET`) rather
than defining a second classification enum.

- [ ] **Step 2.1: Write RED provenance and egress tests**

Test transitive dependency closure, source hashes, PUBLIC/INTERNAL/SECRET, unknown classification,
stale provider policy, byte totals, manifest tampering, a PUBLIC wrapper containing SECRET CAS
content, prompt injection in source text, browser history treated as data, and forbidden external
provider egress. Unknown is SECRET-equivalent for egress decisions.

- [ ] **Step 2.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_context_provenance.py tests/runtime/test_data_policy.py
```

Expected: fails because structured provenance/data policy is absent.

- [ ] **Step 2.3: Implement conservative compilation**

The context compiler reads only approved CAS references and emits immutable entries. The egress
manifest hashes the exact bytes sent, not filenames or summaries. Apply path/capability/data-class
policy first, then run the secret scanner as an additional rejection detector.

- [ ] **Step 2.4: Run GREEN with router privacy tests**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_context_provenance.py tests/runtime/test_data_policy.py \
  tests/model_router/test_catalog_and_privacy.py
```

Expected: all pass; SECRET and unknown bytes never become eligible for remote egress.

- [ ] **Step 2.5: Commit**

```bash
git add runtime/context_compiler.py runtime/data_policy.py paeos/model_router/types.py \
  paeos/model_router/privacy.py \
  tests/runtime/test_context_provenance.py tests/runtime/test_data_policy.py
git commit -m "feat(runtime): compile provenance-bound egress manifests"
```

---

## Task 3: Compile Existing CapabilityToken Authority for Production

**Files:**

- Create: `runtime/task_compiler.py`
- Modify: `runtime/claude_code.py`
- Modify: `kernel/capability.py`
- Test: `tests/runtime/test_task_compiler.py`
- Modify: `tests/kernel/test_capability.py`

**Interfaces:**

```python
class TaskCompilationError(RuntimeError): ...

class ProductionTaskCompiler:
    def compile(
        self,
        *,
        contract: FrozenImplementationContract,
        binding: ExecutionBinding,
        context: tuple[ContextEntry, ...],
        budget: Budget,
        worker_session: str,
        current_seq: int,
    ) -> TaskPackage: ...
```

Capability operations use typed, hash-bound names such as:

```text
file:read:<path>
patch:apply:<path>
test:run:<command-id>
scope:request
artifact:submit:<required-path>
```

- [ ] **Step 3.1: Write RED compilation tests**

Prove route admission without a frozen contract cannot compile; every package field matches the
contract/binding; TTL is short and ledger-sequence-bound; operations are exact; worktree/base
commit and binary/profile hashes match; mismatches fail before runtime invocation.

- [ ] **Step 3.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_task_compiler.py tests/kernel/test_capability.py
```

Expected: task compiler tests fail because the production compiler is absent; capability tests
remain green.

- [ ] **Step 3.3: Implement compilation through CapabilityBroker**

The compiler may call `CapabilityBroker.mint()` but never receives the signing key. Do not add an
adapter-side token mint path. Preserve signature -> TTL -> binding -> allowlist verification order.

- [ ] **Step 3.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_task_compiler.py tests/kernel/test_capability.py \
  tests/runtime/test_dispatcher.py
```

Expected: all pass; existing dispatcher behavior remains compatible, new production dispatch is
strictly stronger.

- [ ] **Step 3.5: Commit**

```bash
git add runtime/task_compiler.py runtime/claude_code.py kernel/capability.py \
  tests/runtime/test_task_compiler.py tests/kernel/test_capability.py
git commit -m "feat(runtime): mint production task authority from L11"
```

---

## Task 4: Implement a Typed, Capability-Checked Worker Broker

**Files:**

- Create: `runtime/worker_broker.py`
- Test: `tests/runtime/test_worker_broker.py`
- Integrate: `runtime/worker_admission.py`

**Interfaces:**

```python
class OperationKind(StrEnum):
    READ_FILE = "READ_FILE"
    APPLY_PATCH = "APPLY_PATCH"
    RUN_ACCEPTANCE = "RUN_ACCEPTANCE"
    REQUEST_SCOPE = "REQUEST_SCOPE"
    SUBMIT_ARTIFACT = "SUBMIT_ARTIFACT"

@dataclass(frozen=True, slots=True)
class OperationRequest:
    request_id: str
    task_id: str
    kind: OperationKind
    arguments: Mapping[str, JsonValue]

@dataclass(frozen=True, slots=True)
class OperationReceipt:
    request_hash: str
    operation: str
    exit_code: int | None
    stdout_hash: str | None
    artifact_hash: str | None
    ledger_seq: int

class WorkerOperationBroker:
    def execute(self, package: TaskPackage, request: OperationRequest) -> OperationReceipt: ...
```

- [ ] **Step 4.1: Write RED policy-order and escape tests**

Test signature/TTL/binding/operation order, unrecognized tools, raw shell, command expansion,
additional command, skills, subagents, model change, audit verdict, lifecycle mutation, promotion,
path traversal, symlink/hardlink escape, absolute path, race between validation and open, duplicate
request, budget exhaustion, and worker-created evidence claims.

- [ ] **Step 4.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_worker_broker.py
```

Expected: collection fails because the production broker does not exist.

- [ ] **Step 4.3: Implement typed operations**

Resolve paths relative to an already-open worktree directory descriptor where supported; reject
links and re-check identity at mutation. Construct acceptance argv only from the frozen command
identified by `command_id`. Each successful mutation/command produces a coordinator event and
consumes budget; duplicate request hashes are idempotently returned only when the committed
receipt matches exactly.

- [ ] **Step 4.4: Run GREEN with disposable-probe policy tests**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_worker_broker.py tests/runtime/test_worker_admission.py
```

Expected: all pass. The disposable admission broker and production broker remain distinct policy
profiles over shared parsing primitives.

- [ ] **Step 4.5: Commit**

```bash
git add runtime/worker_broker.py runtime/worker_admission.py \
  tests/runtime/test_worker_broker.py
git commit -m "feat(runtime): broker typed worker operations"
```

---

## Task 5: Enforce OS Resource, Process, Disk, and Network Boundaries

**Files:**

- Modify: `kernel/sandbox.py`
- Create: `kernel/sandbox_backend.py`
- Modify: `tests/kernel/test_sandbox.py`
- Create: `tests/kernel/test_sandbox_confinement.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class SandboxProfile:
    profile_id: str
    cpu_seconds: int
    memory_bytes: int
    process_count: int
    open_files: int
    file_size_bytes: int
    disk_bytes: int
    wallclock_seconds: int
    network_mode: str
    allowed_exec_hashes: tuple[tuple[str, str], ...]

class SandboxBackend(Protocol):
    def supports(self, profile: SandboxProfile) -> bool: ...
    def run(self, invocation: SandboxedInvocation) -> SandboxResult: ...
```

- [ ] **Step 5.1: Write RED capability-detection and exhaustion tests**

Test executable hash mismatch, PATH substitution, child-process fanout, CPU/memory/open-file/file
size/disk/wallclock exhaustion, forbidden network connection, backend unavailable, timeout process
group cleanup, stdout/stderr size caps, and no weaker fallback. Use local loopback fixtures only;
do not access the internet.

- [ ] **Step 5.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/kernel/test_sandbox.py tests/kernel/test_sandbox_confinement.py
```

Expected: new tests fail because existing `run_sandboxed()` lacks process, disk, network, and
binary-hash guarantees.

- [ ] **Step 5.3: Implement explicit backend negotiation**

Keep the current portable resource limiter only for profiles it can fully satisfy. On macOS, add
a backend using the pinned and hash-verified `/usr/bin/sandbox-exec` with a generated deny-default
profile: network denied unless the task capability explicitly permits an enumerated endpoint,
writes restricted to the isolated workspace, and executable paths restricted to the profile.
Apply `RLIMIT_NPROC` where supported, launch a dedicated process group, and have the broker's quota
monitor kill that group if aggregate workspace bytes exceed `disk_bytes`. If `sandbox-exec`, a
required rlimit, or another requested boundary is unavailable, `supports(profile)` is false and
production stops with `SANDBOX_PROFILE_UNAVAILABLE`; never log and continue with a weaker backend.
Kill the complete process group on timeout.

- [ ] **Step 5.4: Run GREEN and mutation checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/kernel/test_sandbox.py tests/kernel/test_sandbox_confinement.py
```

Expected: all supported-boundary tests pass; unsupported host features cause explicit skips only
in platform-capability characterization tests and fail closed in production-policy tests.

- [ ] **Step 5.5: Commit**

```bash
git add kernel/sandbox.py kernel/sandbox_backend.py tests/kernel/test_sandbox.py \
  tests/kernel/test_sandbox_confinement.py
git commit -m "feat(kernel): enforce worker sandbox profiles"
```

---

## Task 6: Separate Baseline, Candidate, and Verifier Views

**Files:**

- Create: `runtime/verification_workspace.py`
- Test: `tests/runtime/test_verification_workspace.py`
- Modify: `runtime/orchestrator/__init__.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class VerificationViews:
    baseline: Path
    candidate: Path
    verifier: Path
    baseline_head: str
    candidate_head: str
    verifier_manifest_hash: str

def create_verification_views(contract: FrozenImplementationContract, verifier_bundle: ArtifactRef) -> VerificationViews: ...
```

- [ ] **Step 6.1: Write RED contamination tests**

Prove candidate cannot alter baseline, verifier tests, canaries, mutation manifest, dependency
lock, or expected failure reasons. A contract that authorizes test changes must set a separate
test-design-audit obligation before those tests can verify the change.

- [ ] **Step 6.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_verification_workspace.py
```

Expected: fails because immutable proof views are absent.

- [ ] **Step 6.3: Implement view creation and manifests**

Materialize from exact commits/CAS refs, make baseline/verifier read-only to the worker, and hash
their complete manifests. Independent verification reproduces commands in the verifier view with
the candidate applied; builder-authored stdout is not evidence.

- [ ] **Step 6.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_verification_workspace.py tests/runtime/test_dispatcher.py
```

- [ ] **Step 6.5: Commit**

```bash
git add runtime/verification_workspace.py runtime/orchestrator/__init__.py \
  tests/runtime/test_verification_workspace.py
git commit -m "feat(runtime): isolate verification proof views"
```

---

## Task 7: L13, L14, and L17 Gate

**Files:**

- Create: `reviews/tasks/PAEOS_TASKPACKAGE_WORKER_CONFINEMENT_review.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `MessyChangesNeedsReview.md` only for unresolved debt

- [ ] **Step 7.1: Run focused and full gates fresh**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/test_implementation_contract.py \
  tests/runtime/test_context_provenance.py tests/runtime/test_data_policy.py \
  tests/runtime/test_task_compiler.py tests/runtime/test_worker_broker.py \
  tests/runtime/test_verification_workspace.py \
  tests/kernel/test_capability.py tests/kernel/test_sandbox.py \
  tests/kernel/test_sandbox_confinement.py
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q
git diff --check
```

- [ ] **Step 7.2: Run hidden boundary mutations**

Prove the suite kills a removed token check, symlink race, executable substitution, data-class
downgrade, prompt-injected tool request, process fanout, network escape, budget bypass, and
baseline/verifier contamination.

- [ ] **Step 7.3: Obtain physically decorrelated L14 audit**

Audit sealed implementation/evidence only. Verify auditor family inequality against both
supervisor and worker receipts where applicable.

- [ ] **Step 7.4: Record L17 and stop before a real task**

Report exact Court counts and residual OS/platform limits. Do not dispatch a live PAEOS or SAKG
task under this plan.

- [ ] **Step 7.5: Commit review records**

```bash
git add PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md MessyChangesNeedsReview.md \
  reviews/tasks/PAEOS_TASKPACKAGE_WORKER_CONFINEMENT_review.md
git commit -m "docs(review): record worker confinement disposition"
```
