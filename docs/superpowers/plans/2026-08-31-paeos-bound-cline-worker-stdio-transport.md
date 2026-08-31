# PAEOS Bound Cline Worker Stdio Transport Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Replace the unsafe manual GUI/clipboard handoff with a state-root-bound, one-shot Cline worker transport that produces exactly one hash-bound response or a durable fail-closed quarantine record.

**Architecture:** `BoundClineWorkerTransport` launches the existing framed `cline_sdk_host.mjs` in a fresh sandbox, validates every request/event/tool decision through existing PAEOS contracts, and persists only a correlated `ResponseEnvelope` or typed failure. `ChatBridgeRuntime` remains the transaction-facing compatibility seam; the new worker transport is explicit, supervised, and never creates Court/lifecycle authority.

**Tech Stack:** Python 3.12+, existing `bridge_protocol.py` envelopes and reducer, existing Cline SDK framed host, `subprocess.Popen(shell=False)`, frozen dataclasses/enums, pytest, Ruff, Pyright, canonical JSON/SHA-256 evidence.

**Spec:** `docs/superpowers/specs/2026-08-31-paeos-bound-cline-worker-stdio-transport-design.md`

## Global Constraints

- Work only in `/private/tmp/paeos-control-plane-recovery-s1-clean-recovered` on branch `codex/control-plane-recovery-s1-clean-recovered`.
- Preserve the eleven circuit breakers; no identical failed command is retried.
- Never launch the legacy GUI bridge, browser/CDP, clipboard, AppleScript, or an unbound terminal.
- No provider call, credential read, fallback, retry, Court mutation, lifecycle advancement, SAKG resumption, push, merge, rebase, or `main`/`trunk` mutation during implementation or tests.
- The worker is implementation-only. Worker prose cannot create a `WorkerBinding`, Court row, seal, promotion authority, or Founder disposition.
- Builder and auditor families remain physically distinct; the GLM worker cannot audit its own work.
- All state paths are absolute and external to the repository; symlinks and path escapes fail closed.
- Tests use a fake local host and synthetic receipts only. Real Cline admission remains a separately authorized operational action.
- Preserve current accounting (`12/48`, Worker `0/1/0`, Court `0/0/0`) and open debts `DEBT-0058`/`DEBT-0060`.

## File Map

- Create `runtime/integrations/bound_cline_transport.py`: typed configuration, request validation, one-shot framed process execution, response/quarantine persistence, and secret-blind handoff records.
- Create `tests/runtime/test_bound_cline_transport.py`: unit tests for contracts, path binding, process/event handling, and failure classification.
- Create `tests/runtime/test_bound_cline_transport_persistence.py`: atomic response, quarantine, and handoff persistence tests.
- Create `ops/bound_cline_worker.py`: explicit one-shot CLI boundary around the transport.
- Create `tests/ops/test_bound_cline_worker.py`: CLI validation and integration tests with a fake host.
- Modify `runtime/integrations/chat_bridge.py`: add an opt-in `BoundClineWorkerRuntime` adapter that delegates one package at a time to the transport; leave existing compatibility behavior unchanged.
- Modify `ops/autonomous_run.py`: accept explicit runtime type `bound-cline` only when the required public profile/qualification tuple is supplied; retain all existing defaults.
- Create `reviews/tasks/PAEOS_BOUND_CLINE_WORKER_STDIO_review.md`: implementation evidence and overseer handoff, with no seal or debt closure claim.

## Interfaces

The following interfaces are fixed before implementation:

```python
class TransportFailureKind(StrEnum):
    REQUEST_BINDING = "REQUEST_BINDING"
    PATH_ESCAPE = "PATH_ESCAPE"
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    LEASE_UNAVAILABLE = "LEASE_UNAVAILABLE"
    QUALIFICATION_DRIFT = "QUALIFICATION_DRIFT"
    MODEL_MISMATCH = "MODEL_MISMATCH"
    PROTOCOL_VIOLATION = "PROTOCOL_VIOLATION"
    TOOL_DENIED = "TOOL_DENIED"
    COMMAND_MISMATCH = "COMMAND_MISMATCH"
    PROVIDER_ATTEMPT_OVERFLOW = "PROVIDER_ATTEMPT_OVERFLOW"
    TIMEOUT = "TIMEOUT"
    PROCESS_FAILED = "PROCESS_FAILED"
    SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
    RESPONSE_BINDING = "RESPONSE_BINDING"

@dataclass(frozen=True, slots=True)
class BoundWorkerConfig:
    state_root: Path
    recovery_worktree: Path
    node_executable: Path
    host_module: Path
    sdk_entrypoint: Path
    core_entrypoint: Path
    qualification_record: Path
    provider_id: str
    model_id: str
    model_family: ModelFamily
    session_id: str
    timeout_seconds: float = 300.0
    max_declared_model_turns: int = 2

def dispatch_once(request_path: Path, prompt_path: Path, config: BoundWorkerConfig) -> WorkerDispatchResult: ...
```

`dispatch_once` is the only production entry point. It accepts immutable JSON request and prompt
files, starts at most one worker process, and returns without creating Court or lifecycle records.
The response writer is private to the module. Success and failure results both carry the immutable
request ID and transaction key; only success may create the correlated response file.

**Normative execution order:** implement and verify Task 1, then Task 2, then return to the
downstream Task 3, Task 4, and Task 5 sections below. The downstream sections are grouped before
the foundational sections in this document only to keep their persistence, CLI, and review details
together; their numeric order is authoritative.

---

### Task 3: Persist Correlated Responses, Quarantine Failures, and Write Handoffs

**Files:**
- Modify: `runtime/integrations/bound_cline_transport.py`
- Create: `tests/runtime/test_bound_cline_transport_persistence.py`

**Interfaces:**
- Consumes: successful terminal data or `TransportFailure`, `BridgePaths`, `write_once_json`, `canonical_json`, and the candidate HEAD from the explicit recovery worktree.
- Produces: `_persist_response_once(...)`, `_quarantine_failure_once(...)`, and `_persist_handoff_once(...)`.

- [ ] **Step 1: Write failing persistence and quarantine tests**

```python
def test_response_is_create_only_and_hash_bound(tmp_path):
    result = dispatch_with_fake_success(tmp_path)
    response_path = BridgePaths(tmp_path / "state").responses / f"{result.response.request_id}.json"
    assert json.loads(response_path.read_text()) == canonical_response_dict(result.response)
    assert response_path.stat().st_mode & 0o777 == 0o600

def test_preexisting_response_is_quarantined_without_overwrite(tmp_path):
    result = dispatch_with_preexisting_response(tmp_path)
    assert_failure(result, TransportFailureKind.DUPLICATE_TRANSACTION)
    assert quarantine_files(tmp_path)

def test_timeout_writes_only_content_free_failure_and_handoff(tmp_path):
    result = dispatch_with_fake_timeout(tmp_path)
    assert isinstance(result, WorkerDispatchFailure)
    assert result.quarantine_path.exists()
```

- [ ] **Step 2: Run the persistence tests once and verify RED**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/test_bound_cline_transport_persistence.py
```

- [ ] **Step 3: Implement atomic response persistence**

Serialize a `ResponseEnvelope` using `canonical_json`, create a `0600` temporary file with
`O_EXCL` beneath `BridgePaths.responses`, write and `fsync` all bytes, atomically link/rename to the
final request-derived response path, and `fsync` the parent directory. If the path already exists,
compare bytes only; identical bytes are an idempotent observation, while different bytes raise the
duplicate circuit breaker and preserve both payloads.

- [ ] **Step 4: Implement content-free failure quarantine**

Hash raw stdout/stderr and store only typed failure metadata, hashes, exit status, and the exact
failure kind beneath `BridgePaths.quarantine`. Never write provider response bodies, credential-like
text, or arbitrary worker prose. A failure must not create a successful response file.

- [ ] **Step 5: Implement handoff persistence**

Write one canonical `HandoffRecord` beside the transaction evidence using create-only `0600`
semantics and directory `fsync`. Include candidate HEAD, request/transaction/session IDs, model
tuple, response/failure hashes, and a bounded next-action code. Do not include credentials or raw
response text.

- [ ] **Step 6: Run GREEN and static checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/test_bound_cline_transport.py tests/runtime/test_bound_cline_transport_persistence.py
/Users/bob/GitHub/paeos/.venv/bin/ruff check runtime/integrations/bound_cline_transport.py tests/runtime/test_bound_cline_transport.py tests/runtime/test_bound_cline_transport_persistence.py
/Users/bob/GitHub/paeos/.venv/bin/pyright runtime/integrations/bound_cline_transport.py
```

- [ ] **Step 7: Commit**

```bash
git add runtime/integrations/bound_cline_transport.py tests/runtime/test_bound_cline_transport.py tests/runtime/test_bound_cline_transport_persistence.py
git commit -m "feat(bridge): persist bound responses and handoffs"
```

---

### Task 4: Add the Explicit CLI and Supervised Runtime Adapter

**Files:**
- Create: `ops/bound_cline_worker.py`
- Create: `tests/ops/test_bound_cline_worker.py`
- Modify: `runtime/integrations/chat_bridge.py`
- Modify: `ops/autonomous_run.py`

**Interfaces:**
- Consumes: `dispatch_once`, `BoundWorkerConfig`, `RequestEnvelope`, and existing `ChatBridgeRuntime` package binding.
- Produces: CLI `main(argv) -> int` and opt-in `BoundClineWorkerRuntime.run(package) -> RunOutput`.

- [ ] **Step 1: Write failing CLI and runtime tests**

```python
def test_cli_rejects_missing_absolute_state_root_before_launch(tmp_path, monkeypatch):
    monkeypatch.setattr(bound_cline_worker, "dispatch_once", pytest.fail)
    assert bound_cline_worker.main(["--state-root", "relative"]) == 2

def test_cli_rejects_interactive_and_legacy_transport_flags(tmp_path):
    assert bound_cline_worker.main(["--state-root", str(tmp_path), "--clipboard"]) == 2

def test_runtime_returns_worker_writes_without_creating_court_state(tmp_path):
    runtime = fake_bound_runtime(tmp_path)
    output = runtime.run(bound_task_package(tmp_path))
    assert output.status is TaskStatus.COMPLETE
    assert not (tmp_path / "court" / "dispositions").exists()
```

- [ ] **Step 2: Run the new tests once and capture RED output**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/ops/test_bound_cline_worker.py
```

- [ ] **Step 3: Implement the thin CLI boundary**

Require absolute `--state-root`, `--request-path`, `--prompt-path`, `--recovery-worktree`,
`--node-executable`, `--host-module`, `--sdk-entrypoint`, `--core-entrypoint`,
`--qualification-record`, `--provider-id`, `--model-id`, `--model-family`, and `--session-id`.
Reject unknown options and any `--retry`, `--fallback`, credential, browser, clipboard, or
interactive option. Return `0` only for `WorkerDispatchSuccess`; return `2` for every failure and
print only canonical metadata/hashes.

- [ ] **Step 4: Implement `BoundClineWorkerRuntime` as an explicit opt-in adapter**

Add a runtime class in `runtime/integrations/chat_bridge.py` that materializes the existing task
package into a state-root-bound request/prompt, invokes `dispatch_once` exactly once, converts
successful changed files into `RunOutput`, and maps failures to `TaskStatus.FAILED` with the typed
failure hash in `trace`. Preserve the existing `ChatBridgeRuntime` behavior and all its fail-closed
tests; do not route through `monitor_loop.py`.

- [ ] **Step 5: Add dormant `bound-cline` selection**

In `ops/autonomous_run.py`, accept runtime type `bound-cline` only when all public qualification
and profile identifiers are passed through an explicit configuration object. Do not infer a profile,
provider, or model from aliases such as `paeos (main)`. Keep the default runtime unchanged and
return a clear configuration failure when the tuple is incomplete.

- [ ] **Step 6: Run focused compatibility tests and static checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/ops/test_bound_cline_worker.py tests/runtime/test_bound_cline_transport.py tests/runtime/test_chat_bridge_fail_closed.py
/Users/bob/GitHub/paeos/.venv/bin/ruff check ops/bound_cline_worker.py runtime/integrations/chat_bridge.py tests/ops/test_bound_cline_worker.py
/Users/bob/GitHub/paeos/.venv/bin/pyright ops/bound_cline_worker.py runtime/integrations/chat_bridge.py
```

- [ ] **Step 7: Commit**

```bash
git add ops/bound_cline_worker.py tests/ops/test_bound_cline_worker.py runtime/integrations/chat_bridge.py ops/autonomous_run.py
git commit -m "feat(bridge): expose bound cline runtime"
```

---

### Task 5: Adversarial Verification, Review, and Antigravity Handoff

**Files:**
- Modify: `tests/runtime/test_bound_cline_transport.py`
- Modify: `tests/runtime/test_bound_cline_transport_persistence.py`
- Create: `reviews/tasks/PAEOS_BOUND_CLINE_WORKER_STDIO_review.md`
- Modify only for evidence: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`, `operations/CURRENT_STATE.md`, `MessyChangesNeedsReview.md`

**Interfaces:**
- Consumes: all prior task commits, fake-host raw logs, and static/test outputs.
- Produces: independent implementation evidence and a durable handoff; no gate/debt/seal change.

- [ ] **Step 1: Add discriminative adversarial tests**

Add one test per invariant: wrong request ID, wrong transaction key, stale response, duplicate
response, path escape, symlinked executable, qualification hash drift, wrong model family, unknown
frame, out-of-order sequence, oversized frame, post-terminal frame, tool-before-approval, hidden
retry, timeout, nonzero exit, uncertain side effect, response tamper, handoff tamper, and attempted
GUI/clipboard/CDP invocation. Each test asserts the named `TransportFailureKind`, no successful
response, and a durable quarantine record.

- [ ] **Step 2: Run the adversarial suite and full non-gateway suite once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/test_bound_cline_transport.py tests/runtime/test_bound_cline_transport_persistence.py tests/ops/test_bound_cline_worker.py
env UV_CACHE_DIR=/tmp/paeos-audit-uv-cache uv run pytest --ignore=tests/model_router/test_gateway_server.py -q
```

Preserve raw output and exact exit codes. The gateway test remains excluded by policy.

- [ ] **Step 3: Run changed-path static checks and diff validation**

```bash
/Users/bob/GitHub/paeos/.venv/bin/ruff check runtime/integrations/bound_cline_transport.py ops/bound_cline_worker.py runtime/integrations/chat_bridge.py tests/runtime/test_bound_cline_transport.py tests/runtime/test_bound_cline_transport_persistence.py tests/ops/test_bound_cline_worker.py
/Users/bob/GitHub/paeos/.venv/bin/pyright runtime/integrations/bound_cline_transport.py ops/bound_cline_worker.py runtime/integrations/chat_bridge.py
git diff --check
git status --short
```

- [ ] **Step 4: Write the implementation review and handoff**

Record exact commits, changed paths, test collection/pass/fail counts, static results, fake-host
limitations, transport failure classifications, and the current candidate HEAD. State explicitly:

```text
Worker: Admitted: 0 | Rejected: 1 | Remediated: 0
Court: Sealed: 0 | Remanded: 0 | Remediated: 0
DEBT-0058: OPEN
DEBT-0060: OPEN
L14/L17: not performed by the builder
```

Do not create a Court row, close a debt, claim Gate completion, or claim SAKG resumption. The
handoff must tell Antigravity how to resume from the exact branch/HEAD and which one-shot external
actions remain separately authorized.

- [ ] **Step 5: Commit review evidence only**

```bash
git add reviews/tasks/PAEOS_BOUND_CLINE_WORKER_STDIO_review.md PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md operations/CURRENT_STATE.md MessyChangesNeedsReview.md
git commit -m "docs(review): verify bound cline worker transport"
```

## Completion Criteria

The plan is complete only when every task is green, the full non-gateway suite is reconciled, the
old GUI bridge remains disabled, the transport has no retry/fallback or unbound terminal path, and
the review/handoff preserves current accounting and open debts. This implementation still does
not repay `DEBT-0058`/`DEBT-0060`, seal any gate, or resume SAKG; those require independent operational
evidence and Court adjudication.

### Task 1: Define Bound Transport Contracts and Path/Request Validation

**Files:**
- Create: `runtime/integrations/bound_cline_transport.py`
- Test: `tests/runtime/test_bound_cline_transport.py`

**Interfaces:**
- Consumes: existing `RequestEnvelope`, `ResponseEnvelope`, `BridgePaths`, `TransactionStore`, `validate_request`, `validate_response`, and `ModelFamily`.
- Produces: `TransportFailureKind`, `BoundWorkerConfig`, `TransportFailure`, `HandoffRecord`,
  `WorkerDispatchSuccess`, `WorkerDispatchFailure`, `WorkerDispatchResult`, and pure
  `_validate_binding(...)` and `_validate_paths(...)` helpers.

- [ ] **Step 1: Write failing tests for accepted and rejected bindings**

```python
def test_valid_request_and_config_pass_binding(tmp_path):
    request, config = make_bound_request_and_config(tmp_path)
    _validate_binding(request, config)

def test_main_branch_is_rejected_before_process_launch(tmp_path):
    request, config = make_bound_request_and_config(tmp_path, branch="main")
    with pytest.raises(TransportProtocolError, match="main/trunk"):
        _validate_binding(request, config)

def test_symlinked_host_and_prompt_are_rejected(tmp_path):
    request, config = make_bound_request_and_config(tmp_path, symlink_host=True)
    with pytest.raises(TransportProtocolError, match="symlink"):
        _validate_paths(request, config, tmp_path / "prompt.md")
```

- [ ] **Step 2: Run the focused tests and verify the intended RED failures**

Run:

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/test_bound_cline_transport.py
```

Expected: import or missing-symbol failures for the new module; no production process is started.

- [ ] **Step 3: Implement frozen contracts and fail-closed validation**

Implement the enums/dataclasses exactly as defined in the Interfaces section. Require absolute existing regular files
for request, prompt, node, host, SDK, Core, and qualification paths; resolve each without following
symlinks and verify it remains beneath the configured state/worktree or qualified package root.
Reject a branch named `main` or `trunk`, a worktree outside `recovery_worktree`, empty IDs, an
unknown family, nonpositive timeout/turn values, and any configured provider/model mismatch with
the request envelope. Do not read profile contents or credentials.

- [ ] **Step 4: Run GREEN and static checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/test_bound_cline_transport.py
/Users/bob/GitHub/paeos/.venv/bin/ruff check runtime/integrations/bound_cline_transport.py tests/runtime/test_bound_cline_transport.py
/Users/bob/GitHub/paeos/.venv/bin/pyright runtime/integrations/bound_cline_transport.py
```

Expected: all focused tests pass; Ruff and Pyright report no diagnostics on the changed scope.

- [ ] **Step 5: Commit**

```bash
git add runtime/integrations/bound_cline_transport.py tests/runtime/test_bound_cline_transport.py
git commit -m "feat(bridge): define bound cline transport contract"
```

---

### Task 2: Implement One-Shot Framed Process Execution and Tool Policy

**Files:**
- Modify: `runtime/integrations/bound_cline_transport.py`
- Test: `tests/runtime/test_bound_cline_transport.py`
- Reuse read-only: `runtime/integrations/cline_sdk_protocol.py`, `runtime/integrations/cline_sdk_host.mjs`, `runtime/worker_admission.py`, `runtime/integrations/cline_worker.py`

**Interfaces:**
- Consumes: `BoundWorkerConfig`, validated request/prompt, `encode_frame`, `read_frame`, `HostEventMachine`, `evaluate_tool_request`, and the existing transaction reducer.
- Produces: `_run_host_once(...)`, `_execute_approved_tool(...)`, and typed `TransportFailure` results.

- [ ] **Step 1: Add failing event-loop tests using a fake local host**

The fake host writes canonical framed `hello`, `provider_attempt_started`, `tool_request`, and
`terminal` events to stdout and reads framed tool decisions from stdin. Add tests proving:

```python
def test_dispatch_executes_only_preapproved_editor_and_exact_command(tmp_path):
    result = dispatch_once(*fake_request_files(tmp_path), fake_config(tmp_path))
    assert isinstance(result, WorkerDispatchSuccess)

def test_unknown_tool_is_rejected_before_execution(tmp_path):
    result = dispatch_once(*fake_request_files(tmp_path, tool="read_files"), fake_config(tmp_path))
    assert_failure(result, TransportFailureKind.TOOL_DENIED)

def test_extra_cd_or_separator_is_rejected(tmp_path):
    result = dispatch_once(*fake_request_files(tmp_path, command="cd /tmp && pytest"), fake_config(tmp_path))
    assert_failure(result, TransportFailureKind.COMMAND_MISMATCH)

def test_second_provider_attempt_in_one_turn_is_rejected(tmp_path):
    result = dispatch_once(*fake_request_files(tmp_path, duplicate_attempt=True), fake_config(tmp_path))
    assert_failure(result, TransportFailureKind.PROVIDER_ATTEMPT_OVERFLOW)
```

- [ ] **Step 2: Run the event-loop tests and capture RED output**

Run the four named tests once. They must fail because no dispatcher/event loop exists; do not run a
real Cline process or provider.

- [ ] **Step 3: Implement the framed host lifecycle**

Launch exactly `[str(config.node_executable), str(config.host_module)]` with `shell=False`,
`cwd=request.workspace_root`, `start_new_session=True`, and a minimal environment containing only
`CLINE_DATA_DIR`, `LANG`, and the fixed `PATH`. Send one canonical `start` frame containing the
request/session/model/qualification hashes and prompt. Accept events only through
`HostEventMachine`; reject unknown, duplicate, out-of-order, oversized, truncated, or
post-terminal frames.

For each `tool_request`, call `evaluate_tool_request` before any side effect. Permit only the
existing `editor` and exact `run_commands` contract. Execute approved tools in the request sandbox,
send one matching `tool_response`, and record the decision hash. Track provider attempts by turn and
stop with `PROVIDER_ATTEMPT_OVERFLOW` if a turn exceeds one attempt. Never add a retry or fallback.

- [ ] **Step 4: Implement timeout and process-group cleanup**

Use `time.monotonic()` and the configured deadline. On timeout, cancellation, protocol violation,
or uncertain process exit, send one cancel frame when possible, terminate the process group, collect
stdout/stderr bytes, and return a failure with side-effect certainty `UNKNOWN`. Never classify a
timeout as success and never start another process.

- [ ] **Step 5: Run GREEN, Node syntax, and static checks**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/test_bound_cline_transport.py
node --check runtime/integrations/cline_sdk_host.mjs
/Users/bob/GitHub/paeos/.venv/bin/ruff check runtime/integrations/bound_cline_transport.py tests/runtime/test_bound_cline_transport.py
/Users/bob/GitHub/paeos/.venv/bin/pyright runtime/integrations/bound_cline_transport.py
```

- [ ] **Step 6: Commit**

```bash
git add runtime/integrations/bound_cline_transport.py tests/runtime/test_bound_cline_transport.py
git commit -m "feat(bridge): run bound cline host once"
```

---
