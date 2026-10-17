# PAEOS Cline SDK Admission Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this
> plan one task at a time, stopping at every named review checkpoint. Production changes follow
> RED → GREEN. The worker is an `UNADMITTED_BOOTSTRAP_CANDIDATE`; it may implement only under the
> Founder-approved isolated recovery exception and may never audit or ratify its own work.

**Goal:** Replace the inadmissible ordinary Cline CLI probe path with a provider-neutral,
fail-closed admission-probe interface and a pinned public Cline SDK adapter that can prove one
exact local-backend/provider/model/profile tuple without exposing credentials or duplicating later
PAEOS gates.

**Architecture:** Python owns admission policy, profile locking, probe-side effects, evidence
staging, secret scanning, and the final `RawWorkerRun`. A small pinned Node ESM host loads only the
prequalified public `@cline/sdk` and `@cline/core` entry points, starts one explicitly configured
local-backend session, exposes provider-boundary attempt telemetry through an injected `fetch`,
and forwards every requested probe tool over a length-prefixed protocol to Python. The host owns
no approval policy and receives no production task authority. Evidence is scanned before the
existing `kernel.cas.CAS` stores it; Gate B remains the owner of canonical transaction fencing,
Gate C of registries, Gate D of production capability admission, and Gate E of watchdog recovery.

**Tech Stack:** Python 3.12, frozen dataclasses and protocols, `fcntl.flock`, `subprocess`, canonical
JSON, Node.js ESM, installed public Cline SDK/Core 0.0.81, Cline 3.0.60, pytest, Ruff, Pyright.

**Frozen design:**
`docs/superpowers/specs/2026-08-29-paeos-provider-neutral-worker-session-adapter-design.md`

**Architectural baseline:** `d2c984b7a6d96b2e3e8ea0598bf779568de2116b`

## 1. Execution Binding and Non-Negotiable Boundaries

- Execute only in `/private/tmp/paeos-control-plane-recovery-s1-clean-recovered` on a clean
  descendant of `d2c984b`. At L12 dispatch, record the exact plan commit and starting HEAD; do not
  encode a self-referential commit hash in this plan.
- Never modify, merge, rebase, push, or promote `main`/`trunk`. Never operate on the quarantined
  damaged worktree.
- Ingest `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`,
  `docs/PAEOS_MODEL_ROUTER_INFERENCE_MESH_SPEC.md`, and
  `operations/ENGINEERING_LIFECYCLE.md` before each execution or remand-recovery turn.
- The canonical lifecycle is L01–L19. This plan is L11. L12 implementation, L13 independent
  reproduction, L14 different-family audit, L15 remediation, and L17 constitutional review remain
  distinct. SoftLoop is not the lifecycle.
- The legacy `ClineWorkerTransport` is diagnostic-only. It must not emit an admitted result.
  Browser automation, clipboard/AppleScript input, terminal keystroke injection, Cline `auto`
  backend selection, dynamic package install, dynamic version resolution, and private Cline APIs
  are forbidden.
- Qualification and admission are separate. Qualification proves the installed public SDK surface
  can be constrained; admission proves a disposable route tuple. Neither grants production task
  authority.
- No credential value, credential file, Keychain result, cookie, authorization header, provider
  settings blob, environment dump, or matched secret text may enter argv, logs, test fixtures,
  receipts, hashes, CAS, commits, or model context.
- A missing or opaque provider-attempt boundary, unknown frame, duplicate terminal frame, hidden
  retry, capability drift, lock ambiguity, secret finding, or side-effect uncertainty fails closed.
- One failed live probe is preserved and never repeated under the same probe ID. The adapter has no
  retry loop. The existing `qwen3-8-admission-01` rejection remains immutable evidence.
- Admission accounting and Court accounting are separate. Current worker counts are exactly
  `Admitted: 0 | Rejected: 1 | Remediated: 0`; the current Gate A Court counts are
  `Sealed: 0 | Remanded: 0 | Remediated: 0`.
- Remands are healthy back-pressure. Zero remands is never an acceptance criterion.

## 2. Dependency Order and Stop Rules

Tasks are sequential because each consumes the previous task's contract. Stop the implementation
at the first failed checkpoint. Do not replace a failed public-SDK approach with the legacy CLI,
GUI automation, Zen mode, browser control, or an undocumented internal API.

```text
Task 1 SDK qualification
    ↓
Task 2 provider-neutral contracts
    ↓
Task 3 profile handle + lock
    ↓
Task 4 framed Node host protocol
    ↓
Task 5 Python SDK adapter
    ↓
Task 6 evidence staging + CAS publication seam
    ↓
Task 7 operator probe integration + legacy quarantine
    ↓
Task 8 adversarial and mutation verification
    ↓
Task 9 independent L13/L14 review
    ↓
Task 10 three fresh live probes + L15/L17 disposition
```

Tasks 1–8 may be implemented without a provider call. Task 9 is independently performed. Task 10
is operational and remains blocked until qualification, L13, L14, and the non-secret authenticated
profile prerequisite all pass.

---

## Task 1: Qualify the Installed Public Cline SDK Surface

**Files:**

- Create: `runtime/integrations/cline_sdk_qualification.py`
- Create: `ops/cline_sdk_inspect.py`
- Test: `tests/runtime/test_cline_sdk_qualification.py`
- Create after test evidence: `reviews/tasks/PAEOS_CLINE_SDK_ADAPTER_FEASIBILITY.md`

**Produces:** a create-only, content-hashed `AdapterQualificationRecord`; no provider session.

### Step 1.1: Write failing fixture-tree tests

Create a fake installed tree under `tmp_path` containing `cline/package.json`,
`@cline/sdk/package.json`, `@cline/core/package.json`, public ESM entry points, and declaration
files. Test all of these cases:

Write these named tests with the stated assertions:

- `test_qualification_hashes_exact_public_sdk_closure`: assert every expected closure-relative
  path, byte count, and independently recomputed SHA-256 is present in sorted order.
- `test_qualification_rejects_missing_create_start_subscribe_abort_stop`: delete each public
  declaration in a parametrized fixture and assert `MISSING_PUBLIC_SYMBOL` plus a nonzero result.
- `test_qualification_rejects_missing_local_backend_mode`: remove `local` and assert
  `MISSING_LOCAL_BACKEND`.
- `test_qualification_rejects_missing_tool_policy_or_approval_callback`: remove each control seam
  and assert `MISSING_TOOL_CONTROL`.
- `test_qualification_rejects_missing_injected_fetch_boundary`: remove `fetch` injection and assert
  `OPAQUE_PROVIDER_BOUNDARY`.
- `test_qualification_rejects_symlink_escape_from_package_root`: point one closure file outside the
  root and assert `PACKAGE_ESCAPE` before content is read.
- `test_qualification_output_is_canonical_and_contains_no_file_contents`: assert byte-identical
  repeated serialization, sorted fields, and absence of fixture source text.

Run once and preserve the RED output:

```bash
.venv/bin/python -m pytest -q tests/runtime/test_cline_sdk_qualification.py
```

Expected: collection fails because `cline_sdk_qualification` does not exist.

### Step 1.2: Implement immutable qualification types

Implement in `runtime/integrations/cline_sdk_qualification.py`:

```python
SDK_QUALIFICATION_SCHEMA = "paeos.cline-sdk-qualification/1"

@dataclass(frozen=True, slots=True)
class QualifiedFile:
    role: str
    relative_path: str
    sha256: str
    byte_count: int

@dataclass(frozen=True, slots=True)
class AdapterQualificationRecord:
    schema: str
    cline_version: str
    sdk_version: str
    core_version: str
    node_version: str
    node_sha256: str
    package_root: str
    sdk_entrypoint: str
    core_entrypoint: str
    files: tuple[QualifiedFile, ...]
    required_symbols: tuple[str, ...]
    record_sha256: str

class QualificationGap(str, Enum):
    MISSING_PUBLIC_SYMBOL = "MISSING_PUBLIC_SYMBOL"
    MISSING_LOCAL_BACKEND = "MISSING_LOCAL_BACKEND"
    MISSING_TOOL_CONTROL = "MISSING_TOOL_CONTROL"
    OPAQUE_PROVIDER_BOUNDARY = "OPAQUE_PROVIDER_BOUNDARY"
    PACKAGE_ESCAPE = "PACKAGE_ESCAPE"
    VERSION_MISMATCH = "VERSION_MISMATCH"
```

The inspector must require public declarations for `ClineCore.create`, `start`, `subscribe`,
`abort`, `stop`, `backendMode: local`, explicit provider/model/session configuration,
`enableTools`, `enableSpawnAgent`, `enableAgentTeams`, `disableMcpSettingsTools`, `toolPolicies`,
`requestToolApproval`, `toolExecutors`, injected `fetch`, and the returned session manifest and
message paths. Hash the exact Node executable and the deterministic SDK/Core dependency closure.
Never execute package lifecycle scripts and never access credentials.

### Step 1.3: Add the read-only inspector CLI

`ops/cline_sdk_inspect.py` accepts only explicit absolute paths:

```text
--cline-package-root PATH
--node-executable PATH
--output PATH
```

It creates `--output` with `O_CREAT|O_EXCL`, mode `0600`, canonical JSON, `fsync`, and an atomic
parent-directory sync. Existing output, relative paths, symlink escapes, missing symbols, or
version mismatch exit nonzero with a sorted list of `QualificationGap` values. It does not invoke
`cline`, start ClineCore, call a provider, or read the Cline profile.

### Step 1.4: Run focused verification and inspect the real installation

```bash
.venv/bin/python -m pytest -q tests/runtime/test_cline_sdk_qualification.py
.venv/bin/ruff check runtime/integrations/cline_sdk_qualification.py \
  ops/cline_sdk_inspect.py tests/runtime/test_cline_sdk_qualification.py
.venv/bin/pyright runtime/integrations/cline_sdk_qualification.py ops/cline_sdk_inspect.py
```

Then run the inspector once against the installed public package tree, writing outside the repo to
a new path beneath `/Users/bob/.local/share/paeos/runtime-v2/adapter-qualification/`. This read-only
inspection needs no credential and is not a worker admission probe. Record hashes and gaps, never
file contents, in `reviews/tasks/PAEOS_CLINE_SDK_ADAPTER_FEASIBILITY.md`.

**Checkpoint 1 — hard stop:** Tasks 2–10 are blocked unless the real record proves the exact public
surface. A gap produces `ADAPTER_VERSION_UNQUALIFIED`; do not improvise a fallback.

Commit only after GREEN:

```bash
git add runtime/integrations/cline_sdk_qualification.py ops/cline_sdk_inspect.py \
  tests/runtime/test_cline_sdk_qualification.py \
  reviews/tasks/PAEOS_CLINE_SDK_ADAPTER_FEASIBILITY.md
git commit -m "feat(admission): qualify public cline sdk surface"
```

---

## Task 2: Add the Provider-Neutral Admission-Adapter Contract

**Files:**

- Create: `runtime/worker_adapter.py`
- Modify: `runtime/worker_admission.py`
- Test: `tests/runtime/test_worker_adapter.py`
- Test: `tests/runtime/test_worker_admission.py`

**Consumes:** the Task 1 qualification record. **Preserves:** existing `ProbeContract`,
`RawWorkerRun`, `AdmissionResult`, `ToolDecisionRecord`, and Task 5 worker binding behavior.

### Step 2.1: Write contract and precedence tests

Write these named tests and exact outcomes:

- immutable, transport-neutral observation construction and canonical hashing;
- failure receipt serialization contains hashes and enums but neither synthetic secret nor raw
  provider error text;
- `SideEffectCertainty.UNKNOWN` always rejects;
- zero or two attempts within one declared turn rejects;
- `CAPABILITY_DRIFT` is primary when artifact mismatch is also present;
- HTTP 401 or structured Unauthorized remains `NormalizedErrorType.AUTH_FAILED`;
- the existing valid `RawWorkerRun` fixture produces its unchanged assessment and binding.

Run RED once:

```bash
.venv/bin/python -m pytest -q \
  tests/runtime/test_worker_adapter.py tests/runtime/test_worker_admission.py
```

### Step 2.2: Implement the narrow waist

```python
ADAPTER_PROTOCOL_VERSION = "paeos-worker-admission/1"

class SideEffectCertainty(str, Enum):
    NOT_DISPATCHED = "NOT_DISPATCHED"
    PROVIDER_ACCEPTED = "PROVIDER_ACCEPTED"
    TOOL_EFFECT_POSSIBLE = "TOOL_EFFECT_POSSIBLE"
    UNKNOWN = "UNKNOWN"

class AdapterFailureKind(str, Enum):
    ADAPTER_VERSION_UNQUALIFIED = "ADAPTER_VERSION_UNQUALIFIED"
    CAPABILITY_DRIFT = "CAPABILITY_DRIFT"
    PROFILE_LOCK_FAILED = "PROFILE_LOCK_FAILED"
    SESSION_AMBIGUOUS = "SESSION_AMBIGUOUS"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    UNKNOWN_MODEL_FAMILY = "UNKNOWN_MODEL_FAMILY"
    TOOL_DENIED = "TOOL_DENIED"
    COMMAND_EXPANSION = "COMMAND_EXPANSION"
    TIMEOUT_SAFE = "TIMEOUT_SAFE"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    VERIFICATION_NONDISCRIMINATIVE = "VERIFICATION_NONDISCRIMINATIVE"
    TRANSPORT_FAILED = "TRANSPORT_FAILED"

@dataclass(frozen=True, slots=True)
class AdapterObservation:
    invocation_id: str
    session_id: str
    provider_id: str
    model_id: str
    backend_mode: str
    declared_model_turn_count: int
    provider_attempts_by_turn: tuple[int, ...]
    side_effect_certainty: SideEffectCertainty
    capability_snapshot_sha256: str
    transcript_sha256: str

@dataclass(frozen=True, slots=True)
class AdapterFailureReceipt:
    invocation_id: str
    failure: AdapterFailureKind
    normalized_error: NormalizedErrorType | None
    side_effect_certainty: SideEffectCertainty
    raw_stdout_sha256: str
    raw_stderr_sha256: str
    observation_sha256: str

@runtime_checkable
class AdmissionProbeTransport(Protocol):
    def run_probe(
        self, contract: ProbeContract
    ) -> RawWorkerRun | AdapterFailureReceipt:
        raise NotImplementedError
```

Map provider errors through existing `paeos.model_router.errors.normalize_error`; `AUTH_FAILED`,
`QUOTA_EXHAUSTED`, `PROVIDER_UNAVAILABLE`, `TIMEOUT`, `BAD_REQUEST`, and `MODEL_UNAVAILABLE` remain
canonical `NormalizedErrorType` values and are not duplicated in `AdapterFailureKind`. Do not
replace them with generic `ADMISSION_REJECTED`. Define and test one deterministic precedence:

```text
secret/evidence incompleteness > protocol or transport failure > qualification/profile failure >
capability drift > session/model ambiguity > side-effect uncertainty > repeated or opaque attempt
telemetry > normalized provider error > safe timeout > tool/command denial >
artifact/verification mismatch
```

Preserve all additional findings even though only the first applicable reason is primary. Any
`UNKNOWN` side-effect certainty or absent observation is rejection-only. Add adapters around
the existing assessment seam rather than rewriting Task 5 binding semantics.

### Step 2.3: Verify compatibility and commit

```bash
.venv/bin/python -m pytest -q \
  tests/runtime/test_worker_adapter.py tests/runtime/test_worker_admission.py \
  tests/chatgpt_bridge/test_semantic_identity.py
.venv/bin/ruff check runtime/worker_adapter.py runtime/worker_admission.py \
  tests/runtime/test_worker_adapter.py tests/runtime/test_worker_admission.py
.venv/bin/pyright runtime/worker_adapter.py runtime/worker_admission.py
git add runtime/worker_adapter.py runtime/worker_admission.py \
  tests/runtime/test_worker_adapter.py tests/runtime/test_worker_admission.py
git commit -m "feat(admission): define provider-neutral probe transport"
```

---

## Task 3: Bind an Authenticated Profile Handle Without Reading Secrets

**Files:**

- Create: `runtime/worker_profile.py`
- Test: `tests/runtime/test_worker_profile.py`

### Step 3.1: Write fail-closed profile and lock tests

Write named tests proving:

- the public handle serializes only root, UUID, and positive authentication epoch;
- relative, repository-contained, sandbox-contained, evidence-contained, and qualification-root
  paths reject;
- every symlink component rejects before traversal;
- wrong uid or any group/world permission rejects;
- a child process cannot acquire the held lock;
- an active record with no corresponding held lock still requires manual recovery;
- ambiguous release retains the active record and prevents another invocation;
- normal release preserves an immutable released record and permits a later fresh invocation;
- credential-like files planted below the profile root are never listed, read, or hashed.

Use a child Python process for the cross-process `flock` test. Run RED once.

### Step 3.2: Implement a create-only public handle and nonblocking lock

```python
@dataclass(frozen=True, slots=True)
class AuthenticatedProfileHandle:
    root: Path
    profile_uuid: UUID
    auth_epoch: int

@dataclass(frozen=True, slots=True)
class ProfileLeaseRecord:
    invocation_id: str
    profile_uuid: str
    auth_epoch: int
    pid: int
    process_start_token: str
    boot_id: str
    acquired_monotonic_ns: int
```

Requirements:

- `root` is an explicit absolute directory outside the repository, sandbox, evidence root, and
  qualification root; it is owned by the current uid and mode `0700`.
- Validate path components with `lstat`; reject symlinks. Do not traverse or list profile content.
- Acquire an external sibling lock with `fcntl.flock(fd, LOCK_EX | LOCK_NB)` and keep its fd open
  through evidence staging.
- Write an active public lease record with `O_CREAT|O_EXCL`, mode `0600`, and `fsync`. On a clean
  terminal path, first persist terminal local evidence, then atomically rename that active record
  to a create-only invocation-specific released record, sync its parent, and finally release the OS
  lock. The historical released record is never deleted or overwritten.
- Never infer staleness from PID alone. Never automatically break, unlink, or replace a lock/record.
  Any pre-existing active record, lock loss, failed terminal record, or ambiguous release emits
  `PROFILE_LOCK_FAILED` or `SIDE_EFFECT_UNCERTAIN`, retains the active record, and requires manual
  recovery. A normal released history record does not block a new invocation.
- The environment may contain only the profile root path (`CLINE_DATA_DIR`), not secret material.

### Step 3.3: Verify and commit

```bash
.venv/bin/python -m pytest -q tests/runtime/test_worker_profile.py
.venv/bin/ruff check runtime/worker_profile.py tests/runtime/test_worker_profile.py
.venv/bin/pyright runtime/worker_profile.py
git add runtime/worker_profile.py tests/runtime/test_worker_profile.py
git commit -m "feat(admission): bind exclusive cline profile leases"
```

---

## Task 4: Implement the Length-Prefixed Python/Node SDK Protocol

**Files:**

- Create: `runtime/integrations/cline_sdk_protocol.py`
- Create: `runtime/integrations/cline_sdk_host.mjs`
- Test: `tests/runtime/test_cline_sdk_protocol.py`
- Test fixture: `tests/fixtures/cline_sdk/fake_sdk.mjs`

### Step 4.1: Write codec, state-machine, and fake-host tests

Use a four-byte unsigned big-endian payload length followed by canonical UTF-8 JSON. Set
`MAX_FRAME_BYTES = 1_048_576`. Test:

Write named tests asserting:

- frame round trips produce byte-identical canonical JSON;
- zero-length, over-1-MiB, truncated, invalid UTF-8, and non-object payloads terminate;
- unknown message types terminate;
- sequence gaps, duplicates, and cross-invocation IDs terminate;
- duplicate terminal and post-terminal frames terminate;
- a second request and stdin EOF before terminal both terminate;
- the fake SDK's tool request reaches Python and cannot complete until Python returns a decision;
- injected fetch emits one matched start/finish pair per declared turn without emitting request or
  response contents.

Run RED once, including Node syntax checking:

```bash
.venv/bin/python -m pytest -q tests/runtime/test_cline_sdk_protocol.py
node --check runtime/integrations/cline_sdk_host.mjs
```

### Step 4.2: Implement the protocol state machine

Allowed host messages, each with schema version, invocation ID, monotonically increasing sequence,
and session ID after creation:

```text
hello
session_created
capability_snapshot
provider_attempt_started
provider_attempt_finished
tool_request
session_snapshot
terminal
failure
cancelled
```

Allowed Python messages are exactly `start`, `tool_response`, and `cancel`. The Python side sends
one `start`; the host accepts no second start. A `terminal`, `failure`, or `cancelled` message closes
the state machine. Unknown fields are rejected except within explicitly versioned SDK observation
objects; no forward-compatible silent ignore is allowed at this trust boundary.

### Step 4.3: Implement the policy-free Node host

The host must:

- dynamically import only the absolute, prequalified SDK/Core public entry points supplied in the
  start request and verify their hashes before import;
- call `ClineCore.create`, `start`, `subscribe`, `abort`, and `stop` only through public exports;
- set `backendMode: "local"`; `auto`, `hub`, and `remote` are rejected;
- set explicit invocation/session/provider/model IDs;
- set `enableSpawnAgent: false`, `enableAgentTeams: false`,
  `disableMcpSettingsTools: true`, and constrain tools to `editor` and `run_commands`;
- override both relevant tool executors and `requestToolApproval` so requests are forwarded to
  Python and cannot execute locally before a Python response;
- inject a wrapping `fetch` that emits one `provider_attempt_started` immediately before an
  outbound provider request and one matching finished event afterward;
- restrict each attempt event to invocation ID, declared turn ID, attempt ordinal, a locally
  generated correlation ID, monotonic timestamps, and terminal status class. The wrapper passes
  the original request through but never serializes or logs its URL query, headers, authorization,
  cookies, body, prompt, response body, or credential-derived identifier;
- never retry a failed request, make a routing choice, approve a tool, access the filesystem probe
  artifact directly, or read credentials;
- return SDK manifest/message paths and the terminal result for Python validation.

If the SDK performs an outbound provider call outside the injected boundary, or if a default tool
executor can run before Python authorizes it, qualification fails permanently for this tuple.

### Step 4.4: Verify and commit

```bash
.venv/bin/python -m pytest -q tests/runtime/test_cline_sdk_protocol.py
node --check runtime/integrations/cline_sdk_host.mjs
.venv/bin/ruff check runtime/integrations/cline_sdk_protocol.py \
  tests/runtime/test_cline_sdk_protocol.py
.venv/bin/pyright runtime/integrations/cline_sdk_protocol.py
git add runtime/integrations/cline_sdk_protocol.py \
  runtime/integrations/cline_sdk_host.mjs tests/runtime/test_cline_sdk_protocol.py \
  tests/fixtures/cline_sdk/fake_sdk.mjs
git commit -m "feat(admission): add framed cline sdk host protocol"
```

---

## Task 5: Implement `ClineSdkAdmissionAdapter`

**Files:**

- Create: `runtime/integrations/cline_sdk.py`
- Modify: `runtime/integrations/cline_worker.py`
- Test: `tests/runtime/test_cline_sdk_adapter.py`
- Test: `tests/runtime/test_cline_worker_transport.py`

### Step 5.1: Write integration tests with the fake SDK

Write named integration tests proving:

- exact editor then exact verification command produces a valid `RawWorkerRun`;
- read, search, MCP, spawn, team, skill, and every unknown request rejects before execution;
- command expansion by `cd`, pipe, separator, substitution, redirection, or extra argv rejects
  before `subprocess` is called;
- every declared model turn has exactly one observed provider attempt;
- a started but unfinished attempt returns `SideEffectCertainty.UNKNOWN`;
- manifest provider, model, session, and capabilities are all cross-checked;
- structured 401 remains `AUTH_FAILED`;
- timeout sends one cancel, stops once, and performs no retry;
- the child environment equals the explicit allowlist and contains no planted secret;
- legacy CLI diagnostic output is mechanically incapable of admission.

Patch all subprocess boundaries in tests. No test calls a live provider or real profile.

### Step 5.2: Implement the adapter orchestration

```python
@dataclass(frozen=True, slots=True)
class ClineSdkAdapterConfig:
    node_executable: Path
    host_module: Path
    qualification: AdapterQualificationRecord
    profile: AuthenticatedProfileHandle
    timeout_seconds: float

class ClineSdkAdmissionAdapter(AdmissionProbeTransport):
    def run_probe(
        self, contract: ProbeContract
    ) -> RawWorkerRun | AdapterFailureReceipt:
        raise NotImplementedError
```

The Python adapter owns all side effects:

1. Validate the qualification record and acquire the profile lease.
2. Validate a fresh, empty, absolute sandbox and exact initial artifact bytes.
3. Launch the exact hashed Node executable with shell disabled and argv
   `[node, absolute_host_module]`.
4. Build a minimal explicit environment containing only locale, a fixed safe `PATH` if required,
   `CLINE_DATA_DIR`, and platform variables proven necessary by tests. Do not inherit the full
   environment.
5. Send one start frame binding the invocation, local backend, provider, model, session, sandbox,
   qualification hash, and exact capability snapshot.
6. For each tool request call existing `evaluate_tool_request`. Execute only the exact allowed
   disposable edit or verification command after approval; record `ToolDecisionRecord` before
   returning the result. A denial trips the probe and sends one cancel.
7. Preserve raw stdout/stderr bytes separately. Validate sequence, attempt telemetry, SDK manifest,
   message model info, capability snapshot, artifact bytes, command exit status, and terminal state.
8. Run existing `run_discriminative_verification` under Python ownership.
9. Return `RawWorkerRun` only when every invariant holds; otherwise return a typed failure receipt.

Use no router fallback and no automatic retry. Each declared model turn must have exactly one
provider attempt, and continuation after an approved tool result must consume a new declared turn
within the contract maximum. More than one attempt in a turn is `TRANSPORT_FAILED`; zero or opaque
telemetry is `ADAPTER_VERSION_UNQUALIFIED`. Preserve the repeated-attempt finding explicitly.

Mark `ClineWorkerTransport` with an explicit diagnostic-only result type or property. Add a guard
in its admission call seam so it cannot produce `AdmissionVerdict.ADMITTED` even if its artifact
tests pass. Preserve its tests as historical diagnostic coverage.

### Step 5.3: Verify and commit

```bash
.venv/bin/python -m pytest -q \
  tests/runtime/test_cline_sdk_adapter.py \
  tests/runtime/test_cline_worker_transport.py \
  tests/runtime/test_cline_worker_approval.py
.venv/bin/ruff check runtime/integrations/cline_sdk.py \
  runtime/integrations/cline_worker.py tests/runtime/test_cline_sdk_adapter.py
.venv/bin/pyright runtime/integrations/cline_sdk.py runtime/integrations/cline_worker.py
git add runtime/integrations/cline_sdk.py runtime/integrations/cline_worker.py \
  tests/runtime/test_cline_sdk_adapter.py tests/runtime/test_cline_worker_transport.py
git commit -m "feat(admission): constrain cline through public sdk"
```

**Checkpoint 2 — hard stop:** continue only if the fake-SDK tests prove that no default tool,
hidden retry, backend fallback, or unobserved provider attempt is possible through the qualified
surface.

---

## Task 6: Stage, Scan, and Publish Admission Evidence Through Existing CAS

**Files:**

- Create: `runtime/worker_evidence.py`
- Test: `tests/runtime/test_worker_evidence.py`
- Test: `tests/kernel/test_worker_evidence_cas.py`

### Step 6.1: Write content-free secret and durability tests

Write named tests proving:

- PEM, bearer, JWT-shaped, cookie, token assignment, and known provider-prefix fixtures are found
  without echoing matched text;
- reports contain category, range, rule version, and redacted-context hash only;
- unallowlisted files and symlinks quarantine the bundle;
- exactly 64 MiB is accepted, one byte more rejects, exactly 512 MiB free is accepted, and one
  byte less halts before capture;
- staging uses create-only private files and all expected `fsync` calls;
- CAS receives only canonical bytes from a successful scan;
- any secret finding results in zero `CAS.put` calls;
- publication creates neither a Court disposition nor a lifecycle/ledger write.

Fixtures must use synthetic unmistakably fake tokens, never real provider formats copied from the
host. Assertions must ensure the fake secret bytes do not appear in exceptions, reprs, JSON, or
captured output.

### Step 6.2: Implement staging and scanning

```python
MAX_EVIDENCE_BUNDLE_BYTES = 67_108_864
MIN_FREE_BYTES_BEFORE_CAPTURE = 536_870_912

class SecretCategory(str, Enum):
    PRIVATE_KEY = "PRIVATE_KEY"
    AUTHORIZATION_HEADER = "AUTHORIZATION_HEADER"
    TOKEN_ASSIGNMENT = "TOKEN_ASSIGNMENT"
    COOKIE = "COOKIE"
    JWT_SHAPE = "JWT_SHAPE"
    PROVIDER_KEY_PREFIX = "PROVIDER_KEY_PREFIX"

@dataclass(frozen=True, slots=True)
class SecretFinding:
    category: SecretCategory
    artifact_name: str
    byte_offset: int
    byte_length: int
    scanner_rule_version: str
    redacted_artifact_sha256: str
```

The finding never contains matched bytes or any digest influenced by matched bytes.
`redacted_artifact_sha256` is computed only after replacing every matched range with fixed zero
bytes of the same length, so it fingerprints non-secret context without hashing a credential.
Scan the allowlisted raw artifacts before building the
canonical bundle: contract, qualification record, public profile handle, provider-attempt events,
tool decisions, SDK manifest, SDK messages, raw stdout, raw stderr, artifact snapshots,
verification receipt, adapter observation, and terminal/failure receipt. Resolve and validate SDK
paths beneath the leased profile root without following symlinks. Reject unexpected files.

Create staging directories with `0700`, files with `0600`, `O_EXCL`, file `fsync`, atomic rename,
and parent-directory `fsync`. On secret finding, oversize, low disk, or incomplete capture, write
only a content-free quarantine receipt to a distinct private quarantine root and do not call CAS.

Provide a narrow publication function accepting an injected existing `kernel.cas.CAS`:

The exact publication interface is
`publish_scanned_bundle(bundle: ScannedEvidenceBundle, cas: CAS) -> EvidenceCasReceipt`.

It calls `CAS.put` for canonical scanned bytes and returns hashes. It creates no ledger, registry,
Court seal, transaction fence, or lifecycle advancement.

### Step 6.3: Verify and commit

```bash
.venv/bin/python -m pytest -q \
  tests/runtime/test_worker_evidence.py tests/kernel/test_worker_evidence_cas.py \
  tests/kernel/test_cas.py tests/kernel/test_cas_properties.py
.venv/bin/ruff check runtime/worker_evidence.py \
  tests/runtime/test_worker_evidence.py tests/kernel/test_worker_evidence_cas.py
.venv/bin/pyright runtime/worker_evidence.py
git add runtime/worker_evidence.py tests/runtime/test_worker_evidence.py \
  tests/kernel/test_worker_evidence_cas.py
git commit -m "feat(admission): scan and stage worker evidence"
```

---

## Task 7: Integrate the SDK Adapter Into the One-Shot Operator Probe

**Files:**

- Modify: `ops/worker_admission_probe.py`
- Modify: `tests/ops/test_worker_admission_probe.py`
- Create: `tests/ops/test_worker_admission_probe_sdk.py`
- Modify: `ledger/debt/DEBT-0058.md` only to record implementation status, not repayment

### Step 7.1: Write CLI boundary tests

Write named CLI tests proving:

- qualification record, profile root, UUID, positive auth epoch, and Node executable are required;
- one CLI invocation calls the adapter once and no retry option exists;
- `auto`, `hub`, and `remote` reject before process launch;
- typed authentication failure remains `AUTH_FAILED` in canonical output;
- diagnostic CLI transport can never admit;
- existing probe ID or evidence directory rejects without mutation;
- worker and Court counts are separate exact fields.

### Step 7.2: Replace the admission default, not the diagnostic implementation

Make `cline-sdk` the only admission-capable transport. If `cline-cli-diagnostic` remains selectable,
its result is forcibly classified `DIAGNOSTIC_ONLY_REJECTED` and cannot reach
`admitted_worker_binding`.

Add required arguments:

```text
--transport cline-sdk
--qualification-record ABSOLUTE_PATH
--profile-root ABSOLUTE_PATH
--profile-uuid UUID
--auth-epoch POSITIVE_INTEGER
--node-executable ABSOLUTE_PATH
```

Keep the existing exact provider/model/sandbox/artifact/verification arguments. Reject unknown
arguments. Do not add `--retry`, `--fallback`, `--auto`, or a credential argument. Print one
canonical content-free summary containing the verdict, ordered reason codes, evidence hashes,
worker counts, and Court counts. The process exits nonzero on every rejection.

Catch typed adapter failures and retain their exact normalized reason, including `AUTH_FAILED`,
rather than appending only `ADMISSION_REJECTED`. Record in DEBT-0058 that the adapter implementation
exists but live repayment and independent lifecycle stages remain open.

### Step 7.3: Verify and commit

```bash
.venv/bin/python -m pytest -q \
  tests/ops/test_worker_admission_probe.py \
  tests/ops/test_worker_admission_probe_sdk.py
.venv/bin/ruff check ops/worker_admission_probe.py \
  tests/ops/test_worker_admission_probe.py tests/ops/test_worker_admission_probe_sdk.py
.venv/bin/pyright ops/worker_admission_probe.py
git add ops/worker_admission_probe.py tests/ops/test_worker_admission_probe.py \
  tests/ops/test_worker_admission_probe_sdk.py ledger/debt/DEBT-0058.md
git commit -m "feat(admission): route one-shot probes through cline sdk"
```

---

## Task 8: Prove Fail-Closed Behavior With Adversarial and Mutation Tests

**Files:**

- Create: `tests/runtime/test_cline_sdk_adversarial.py`
- Create: `tests/runtime/test_cline_sdk_mutations.py`
- Create: `reviews/tasks/PAEOS_CLINE_SDK_ADAPTER_L13_EVIDENCE.md` during independent reproduction,
  not by the builder

### Step 8.1: Add the adversarial matrix

Each case must prove the forbidden side effect did not occur and that raw evidence was preserved:

1. SDK declaration says spawn disabled but manifest says enabled.
2. SDK asks for `read_files`, MCP settings, skills, subagent, or team use.
3. SDK expands the exact verification command with `cd`, a pipe, separator, or extra argument.
4. Two provider attempt starts occur for one turn.
5. Provider call occurs with no injected-fetch event.
6. A tool executes before Python returns approval.
7. Host emits duplicate, out-of-order, unknown, oversize, truncated, or post-terminal frame.
8. Manifest path escapes the leased profile root or is a symlink.
9. Profile lock record exists but OS lock is free.
10. Host times out after an attempt starts and before it finishes.
11. stdout, stderr, manifest, message, or artifact contains a synthetic secret.
12. Evidence disk watermark or 64 MiB cap is crossed.
13. Qualification file hash changes between inspection and launch.
14. Legacy CLI diagnostic path otherwise appears to satisfy the probe.

### Step 8.2: Add discriminative mutations

For each mutation, first show the unmutated fixture passes, then mutate one invariant and show the
correct stable rejection:

```text
provider ID
model ID
session ID
profile UUID
auth epoch
qualification hash
capability snapshot
provider-attempt count within one declared model turn
tool decision ordering
verification receipt hash
```

The test must fail if the mutation is not detected. This is evidence against vacuous tests, not a
claim of independent audit.

### Step 8.3: Run the full pre-audit verification matrix

```bash
.venv/bin/python -m pytest -q \
  tests/runtime/test_cline_sdk_adversarial.py \
  tests/runtime/test_cline_sdk_mutations.py
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/pyright
node --check runtime/integrations/cline_sdk_host.mjs
git status --short
```

Record exact collected, passed, failed, skipped, xfailed, and xpassed counts. Do not paraphrase a
failure as success. Commit the builder-owned test additions only after all commands are GREEN:

```bash
git add tests/runtime/test_cline_sdk_adversarial.py \
  tests/runtime/test_cline_sdk_mutations.py
git commit -m "test(admission): challenge cline sdk trust boundaries"
```

**Checkpoint 3 — builder stop:** The builder now stops. It must not create the L13 evidence file,
declare Gate A complete, edit Court counts, or run a live admission probe.

---

## Task 9: Perform Independent L13 Reproduction and L14 Decorrelated Audit

**Owner:** not the L12 builder. The L14 auditor's proven physical family must differ from the
builder family. If either family is unknown, L14 is blocked.

**Files:**

- Create: `reviews/tasks/PAEOS_CLINE_SDK_ADAPTER_L13_EVIDENCE.md`
- Create: `reviews/tasks/PAEOS_CLINE_SDK_ADMISSION_ADAPTER_review.md`
- Modify only for findings: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`

### Step 9.1: Reproduce L13 from a clean checkout of the exact candidate

The independent verifier records candidate SHA, clean status, tool versions, commands, raw output
hashes, exact test counts, and mutation kill results. It reruns Task 8 commands without consuming
the builder's prose as evidence. It inspects the real qualification record and recomputes every
file hash from the installed public package closure without reading the profile or making a
provider call.

### Step 9.2: Conduct the different-family L14 audit

The auditor explicitly checks:

- no private/undocumented Cline API and no dynamic package/version resolution;
- local backend is explicit and no `auto`/hub/remote fallback exists;
- tool defaults cannot execute before Python authorization;
- injected fetch observes every provider attempt and hidden retry is rejected;
- profile code never enumerates or hashes secrets and ambiguous locks require manual recovery;
- secret findings are content-free and secret-bearing bundles never reach CAS;
- ordinary CLI transport is mechanically unable to admit;
- Gate A did not implement Gate B fencing, Gate C registries, Gate D task capabilities, Gate E
  watchdogs, another ledger, or self-ratification;
- existing Task 5 worker binding and semantic identity tests remain intact;
- negative and mutation evidence is non-vacuous.

Disposition is exactly `PASS`, `REMAND_WITH_AMENDMENTS`, or `BLOCKED_UNQUALIFIABLE`. Every remand
names the violated invariant and reproduction command. Do not optimize for zero remands.

### Step 9.3: Commit review evidence separately

Only after independent reproduction and audit:

```bash
git add reviews/tasks/PAEOS_CLINE_SDK_ADAPTER_L13_EVIDENCE.md \
  reviews/tasks/PAEOS_CLINE_SDK_ADMISSION_ADAPTER_review.md \
  PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md
git commit -m "docs(review): audit cline sdk admission adapter"
```

**Checkpoint 4 — hard stop:** Task 10 is blocked on any L13 failure, L14 remand, unknown family,
qualification drift, or unavailable non-secret authenticated profile.

## Approved Amendment — Task 9A: Capture a Physical Auditor Receipt

**Founder authorization:** On 2026-08-30 the Founder explicitly authorized a bounded recovery
exception to add candidate-bound physical auditor-receipt capture in the isolated recovery
worktree because the existing router could not produce an L14 receipt. The amendment is specified
in `docs/superpowers/specs/2026-08-30-paeos-auditor-physical-receipt-capture.md`.

Task 9A may add only the provider-neutral receipt contract, transport fingerprints, create-only
receipt/report persistence, focused tests, and a one-shot operational capture command. It may not
run a provider call during implementation, alter worker admission, repair unrelated static debt,
close Gate A, execute Task 10, or advance Gates B–G.

The amended Checkpoint 4 remains in force: Task 10 is blocked until a fresh L13 matrix is green or
formally dispositioned, a machine-captured receipt proves a non-GLM physical auditor against the
exact candidate/evidence bundle, the static/environment findings are reconciled, and the
non-secret authenticated Cline profile prerequisite is satisfied.

---

## Task 10: Run Three Fresh One-Shot Probes and Record L15/L17 Disposition

**This is operational, not a retry loop.** It requires explicit confirmation that the isolated
profile handle is authenticated without inspecting or copying credential values.

**Files after evidence exists:**

- Modify: `ledger/debt/DEBT-0058.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `MessyChangesNeedsReview.md`
- Modify: `docs/IMPLEMENTATION_ATLAS.md`
- Modify: `reviews/tasks/PAEOS_CLINE_SDK_ADMISSION_ADAPTER_review.md`

### Step 10.1: Freeze the exact route tuple

Before any provider call, record the exact hashes and public identifiers:

```text
Cline version and binary/package hash
Node version and executable hash
@cline/sdk and @cline/core versions and closure hash
adapter and policy commit SHA
qualification record hash
backend mode = local
provider ID and model ID
physical model family expected
profile UUID and auth epoch (never credential data)
sandbox profile and exact capabilities
```

If the desired `cline-pass/qwen3.8-max` route is not present in the qualified local profile, stop
as `MODEL_UNAVAILABLE`. Do not silently choose GLM, auto, a free alias, or another provider.

### Step 10.2: Run three separate fresh probes

Use new invocation IDs `qwen3-8-sdk-admission-02`, `qwen3-8-sdk-admission-03`, and
`qwen3-8-sdk-admission-04`. Each command invokes `ops/worker_admission_probe.py` exactly once with
the frozen tuple and a fresh sandbox/evidence directory. After each invocation:

1. preserve raw output and hashes;
2. independently verify the evidence bundle and CAS receipt;
3. confirm each declared model turn has exactly one provider attempt and no failed turn repeats;
4. confirm spawn, teams, MCP settings tools, and all undeclared tools remained disabled;
5. confirm exact edit, exact command, seeded mutation detection, and physical receipt;
6. stop immediately on rejection or ambiguity.

Do not run probe 03 after probe 02 rejects, and do not run probe 04 after either prior probe
rejects. Never reuse a probe ID. A later operator may authorize a new ID only with a new written
rationale addressing the prior failure.

### Step 10.3: Reconcile evidence and exact counts

Three valid admissions for the identical tuple make the route eligible for Gate A closure review;
they do not automatically close Gate A. Any rejection keeps DEBT-0058 open. Report:

```text
Worker admission — Admitted: X | Rejected: Y | Remediated: Z
Gate A Court     — Sealed: X | Remanded: Y | Remediated: Z
```

Counts include the immutable rejected `qwen3-8-admission-01`. “Remediated” requires evidence that
a specifically rejected condition was corrected and re-adjudicated; a fresh successful probe is
not automatically counted as remediation.

### Step 10.4: Complete L15 remediation and L17 constitutional review

Update the five named records with exact SHAs, commands, evidence hashes, route tuple, failures,
open debt, and separation of qualification/admission/production authority. L17 verifies Founder
ratification remains external, Builder != Auditor, no main/trunk mutation, no secret disclosure,
and no lifecycle advancement beyond evidence.

Possible dispositions:

- `GATE_A_ROUTE_ELIGIBLE_FOR_SEALING`: all three probes admitted and L13/L14/L17 pass.
- `GATE_A_REMANDED`: evidence identifies a correctable implementation or policy defect.
- `GATE_A_BLOCKED_EXTERNAL`: SDK/profile/provider cannot be qualified without new external action.
- `GATE_A_REJECTED`: the route violates admission invariants.

Even `GATE_A_ROUTE_ELIGIBLE_FOR_SEALING` requires a separate constitutional ratification action.
Do not self-seal and do not mark DEBT-0058 repaid before that adjudication.

Commit only the reconciled records, never external raw evidence or credentials:

```bash
git add ledger/debt/DEBT-0058.md PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md \
  MessyChangesNeedsReview.md docs/IMPLEMENTATION_ATLAS.md \
  reviews/tasks/PAEOS_CLINE_SDK_ADMISSION_ADAPTER_review.md
git commit -m "docs(review): record sdk worker admission disposition"
```

Stop. No push, merge, rebase, main/trunk promotion, SAKG work, Gate B execution, or production
worker dispatch is authorized by this plan.

---

## 3. Final Acceptance Matrix

The candidate is ready for independent Gate A closure adjudication only when every item is true:

- The real installed public Cline SDK surface has a content-hashed qualification record and no
  required gap.
- The adapter uses explicit local backend, provider, model, session, profile UUID, and auth epoch.
- Node/package/SDK/Core/host/policy hashes are bound into every probe.
- Python is the sole probe-side policy and side-effect owner; the Node host cannot approve or run
  default tools independently.
- Every provider attempt is observed at the injected boundary; exactly one occurs per declared
  model turn and every continuation remains within the contract maximum.
- Spawn, teams, MCP settings tools, and every undeclared tool are disabled and manifest-verified.
- Profile locking is exclusive, nonblocking, secret-blind, and never auto-recovers ambiguity.
- Protocol framing rejects unknown, duplicate, out-of-order, oversize, truncated, and post-terminal
  messages.
- Typed failures preserve normalized provider errors and side-effect certainty.
- Evidence is allowlisted, size-bounded, content-free secret-scanned, durable, and published only
  through the existing CAS seam.
- The legacy ordinary CLI path is diagnostic-only and mechanically cannot admit.
- Full tests, Ruff, Pyright, Node syntax, adversarial tests, and all ten mutation kills pass with
  exact raw counts.
- L13 independently reproduces evidence and L14 uses a proven different model family.
- Three fresh one-shot probes for one identical tuple admit; the first failure stops the sequence.
- DEBT-0058, the notebook, review, messy-changes record, and implementation atlas agree exactly.
- No Gate B–G behavior, production authority, Court sealing, Founder ratification, or main/trunk
  promotion is smuggled into Gate A.

## 4. L12 Dispatch Packet

The Architect hands the implementation worker this plan plus:

1. the exact clean starting HEAD descending from the plan commit;
2. the frozen design at
   `docs/superpowers/specs/2026-08-29-paeos-provider-neutral-worker-session-adapter-design.md`;
3. the current notebook, inference-mesh spec, lifecycle, and DEBT-0058;
4. an allowlist limited to the files named by the active task;
5. one task at a time, with no teams/subagents unless separately authorized;
6. a stop condition after each checkpoint or any circuit-breaker event;
7. the classification `UNADMITTED_BOOTSTRAP_CANDIDATE` until external adjudication says otherwise.

The worker reports raw command output, exact changed files, exact test counts, and resulting commit
SHA. It does not claim admission, audit, Court disposition, Gate A completion, or debt repayment.
