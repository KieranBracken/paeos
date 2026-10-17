# PAEOS Control-Plane Recovery Subproject 1 Implementation Plan

> **For Cline paeos-code:** Execute this plan task by task in a clean, bound implementation
> worktree. Stop after every task for Codex Overseer review. Do not use the legacy bridge to
> route this work.

**Goal:** Isolate all bridge test/runtime state behind an injected state root and establish a
fail-closed, immutable transaction protocol without activating a new overseer adapter.

**Architecture:** Add a pure bridge-protocol module containing immutable envelopes, canonical
hashing, write-once persistence, an explicit transaction reducer, correlation checks, quarantine,
and legacy-state migration. Update ChatBridgeRuntime to use unique request/response files beneath
an explicit state root. Reduce the watchdog to read-only observation. The protocol exists as a
foundation only; subprojects 2 and 3 will bind the Codex adapter and authenticated Cline worker
provenance.

**Tech Stack:** Python 3.12, frozen dataclasses, StrEnum, pathlib, hashlib, json, tempfile,
pytest, Ruff, Pyright.

**Spec:** docs/superpowers/specs/2026-08-25-paeos-control-plane-recovery-design.md

**Global Constraints:**

- Classification is OPERATIONAL_RECOVERY_ONLY.
- The code baseline is af83198192aef72e1ef88615e4ca586a449acb71. The implementation
  branch starts from the immutable tag paeos-control-plane-recovery-s1-contract-v1 so the
  approved L11 design and this corrected plan remain traceable in the branch.
- Implementation happens in a new isolated worktree on a codex/ branch. Never work in the dirty
  main checkout and never promote to main or trunk.
- Cline paeos-code is the implementation worker. Codex GPT-5.6 Sol supervises, reviews, remands,
  and reports. Neither may self-ratify.
- Do not invoke an unconfigured subagent, unrequested skill, GUI bridge, Chrome, clipboard,
  AppleScript, terminal keystroke, or arbitrary visible terminal.
- Do not restart or resume legacy transaction sequence 81. Import it only as
  RECONCILIATION_REQUIRED.
- Do not resume run r-5485b72c, validate historical seals, modify SAKG, alter the 19-layer
  lifecycle, or treat SoftLoop as that lifecycle.
- Do not copy the uncommitted 1,130-line monitor_loop.py rewrite from the dirty main checkout.
- A timeout or uncertain side effect never authorizes a resend. No identical failed command may
  be repeated without a new rationale.
- Every test must use tmp_path for bridge state. Test code must not change into the production
  repository or write beneath /Users/bob/GitHub/paeos/.paeos_state.
- The immutable request schema is implemented here but not emitted by ChatBridgeRuntime yet.
  That runtime does not know the physical worker identity required by the approved schema.
  Subprojects 2 and 3 will activate the schema only after truthful worker and overseer binding
  exists.
- Preserve exact command output, git status, environment, and state-root hashes for Codex review.

## Baseline Gate

Before Task 1, Cline creates a clean worktree from the approved baseline:

    git worktree add -b codex/control-plane-recovery-s1 \
      /private/tmp/paeos-control-plane-recovery-s1 \
      paeos-control-plane-recovery-s1-contract-v1

Then verify:

    git -C /private/tmp/paeos-control-plane-recovery-s1 status --short --branch
    git -C /private/tmp/paeos-control-plane-recovery-s1 \
      describe --tags --exact-match HEAD

Expected:

    ## codex/control-plane-recovery-s1
    paeos-control-plane-recovery-s1-contract-v1

Prove the approved contract commit changed no code relative to the code baseline:

    git diff --quiet \
      af83198192aef72e1ef88615e4ca586a449acb71 \
      paeos-control-plane-recovery-s1-contract-v1 \
      -- . ':(exclude)docs/superpowers/specs/**' ':(exclude)docs/superpowers/plans/**'

Expected: exit 0.

Record the known clean-baseline collection failure once:

    cd /private/tmp/paeos-control-plane-recovery-s1
    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/chatgpt_bridge/test_semantic_identity.py

Expected: collection fails because IDENTITY_VERSION cannot be imported from the committed
ops/chatgpt_bridge/monitor_loop.py. Preserve that output. Do not repeat the identical command.

## Task 1: Add Immutable Protocol Envelopes and Write-Once Storage

**Files:**

- Create: runtime/integrations/bridge_protocol.py
- Replace: tests/chatgpt_bridge/test_semantic_identity.py:1-end

The old semantic-identity test file imports an uncommitted monitor implementation. Replace those
tests with protocol-level tests against a new dependency-free module. Do not modify
monitor_loop.py.

### Step 1.1: Write the first eight failing tests

Replace tests/chatgpt_bridge/test_semantic_identity.py with imports from
runtime.integrations.bridge_protocol and these eight tests:

1. test_bridge_paths_are_contained_by_injected_root
2. test_canonical_hash_is_order_independent
3. test_distinct_event_identity_changes_transaction_key
4. test_request_rejects_missing_or_unknown_worker_identity
5. test_request_allows_null_tty_only_for_declared_headless_transport
6. test_response_disposition_has_no_ratify_member
7. test_write_once_json_refuses_overwrite
8. test_load_json_rejects_malformed_input

Use these exact fixture values:

    def valid_request(**changes: object) -> RequestEnvelope:
        values: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "request_id": "req-001",
            "transaction_key": transaction_key(
                request_id="req-001",
                run_id="run-001",
                stage_id="L14",
                semantic_hash="a" * 64,
                evidence_manifest_hash="b" * 64,
                payload_hash="c" * 64,
            ),
            "created_at": "2026-08-25T10:00:00+00:00",
            "expires_at": "2026-08-25T10:10:00+00:00",
            "goal_id": "goal-001",
            "run_id": "run-001",
            "stage_id": "L14",
            "role": "BUILDER_OUTPUT_REVIEW",
            "workspace_root": "/private/tmp/paeos-control-plane-recovery-s1",
            "worker_transport_id": "cline:paeos-code",
            "worker_session_id": "session-001",
            "worker_pid": 4242,
            "worker_tty": "/dev/ttys001",
            "worker_model_provider": "openai",
            "worker_model_id": "implementation-model",
            "worker_model_family": "implementation-family",
            "semantic_hash": "a" * 64,
            "evidence_manifest_hash": "b" * 64,
            "payload_hash": "c" * 64,
            "allowed_dispositions": (
                Disposition.CONTINUE,
                Disposition.REMAND,
                Disposition.HALT,
                Disposition.NEEDS_FOUNDER,
            ),
        }
        values.update(changes)
        return RequestEnvelope(**values)

    def valid_response(request: RequestEnvelope, **changes: object) -> ResponseEnvelope:
        text = "Evidence is incomplete; remand."
        values: dict[str, object] = {
            "schema_version": SCHEMA_VERSION,
            "request_id": request.request_id,
            "transaction_key": request.transaction_key,
            "run_id": request.run_id,
            "stage_id": request.stage_id,
            "payload_hash": request.payload_hash,
            "lease_owner": "codex-overseer",
            "overseer_model_provider": "openai",
            "overseer_model_id": "gpt-5.6-sol",
            "overseer_model_family": "gpt-5.6",
            "disposition": Disposition.REMAND,
            "response_text": text,
            "response_hash": content_hash(text),
            "source_task_id": "codex-task-001",
            "completed_at": "2026-08-25T10:02:00+00:00",
        }
        values.update(changes)
        return ResponseEnvelope(**values)

Assertions must prove:

- Every BridgePaths directory resolves beneath tmp_path/state/bridge.
- Dict insertion order does not alter canonical_json or content_hash.
- Changing request_id changes transaction_key.
- Empty, whitespace, or unknown provider/model/family values raise ProtocolViolation.
- worker_tty=None fails for cline:paeos-code and succeeds for
  headless:cline-paeos-code only when session ID and PID remain present.
- The exact Disposition values are CONTINUE, REMAND, HALT, NEEDS_FOUNDER.
- A second write to the same path raises FileExistsError and leaves the first bytes unchanged.
- Malformed JSON raises ProtocolViolation and leaves the raw file unchanged.

### Step 1.2: Run the tests to verify RED

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/chatgpt_bridge/test_semantic_identity.py

Expected: collection fails with ModuleNotFoundError for
runtime.integrations.bridge_protocol. This is a new failure rationale, not a repeat of the
baseline monitor import.

### Step 1.3: Implement the minimal protocol primitives

Create runtime/integrations/bridge_protocol.py with these public interfaces:

    SCHEMA_VERSION = "paeos-bridge-v2"

    class ProtocolViolation(RuntimeError):
        pass

    class Disposition(StrEnum):
        CONTINUE = "CONTINUE"
        REMAND = "REMAND"
        HALT = "HALT"
        NEEDS_FOUNDER = "NEEDS_FOUNDER"

    class TransactionState(StrEnum):
        NEW = "NEW"
        PREPARED = "PREPARED"
        CLAIMED = "CLAIMED"
        RESPONDED = "RESPONDED"
        CONSUMED = "CONSUMED"
        RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
        QUARANTINED = "QUARANTINED"

    @dataclass(frozen=True, slots=True)
    class BridgePaths:
        state_root: Path

        def __post_init__(self) -> None:
            object.__setattr__(self, "state_root", self.state_root.resolve())

        @property
        def bridge_root(self) -> Path:
            return self.state_root / "bridge"

        @property
        def requests(self) -> Path:
            return self.bridge_root / "requests"

        @property
        def responses(self) -> Path:
            return self.bridge_root / "responses"

        @property
        def quarantine(self) -> Path:
            return self.bridge_root / "quarantine"

        @property
        def transactions(self) -> Path:
            return self.bridge_root / "transactions"

        def ensure(self) -> None:
            for path in (
                self.requests,
                self.responses,
                self.quarantine,
                self.transactions,
            ):
                path.mkdir(parents=True, exist_ok=True)

Define frozen, slotted RequestEnvelope and ResponseEnvelope dataclasses with exactly the fields in
the approved design. Use tuple[Disposition, ...] for allowed_dispositions and str | None for
worker_tty.

Implement:

    def canonical_json(value: object) -> str
    def content_hash(value: str | bytes | Mapping[str, object]) -> str
    def transaction_key(
        *,
        request_id: str,
        run_id: str,
        stage_id: str,
        semantic_hash: str,
        evidence_manifest_hash: str,
        payload_hash: str,
    ) -> str
    def validate_request(request: RequestEnvelope) -> None
    def validate_response(response: ResponseEnvelope) -> None
    def write_once_bytes(path: Path, payload: bytes) -> None
    def write_once_json(path: Path, value: object) -> None
    def load_json(path: Path) -> dict[str, object]

Canonical JSON must use:

    json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )

Normalize dataclasses with dataclasses.asdict, Path as str, StrEnum as value, tuples as lists, and
mappings recursively. transaction_key is the SHA-256 of this canonical object:

    {
        "schema_version": SCHEMA_VERSION,
        "request_id": request_id,
        "run_id": run_id,
        "stage_id": stage_id,
        "semantic_hash": semantic_hash,
        "evidence_manifest_hash": evidence_manifest_hash,
        "payload_hash": payload_hash,
    }

Validation rules:

- All identifiers match [A-Za-z0-9_.:-]+ and contain no slash.
- All six hash fields used by the two envelopes are lowercase 64-character hexadecimal strings.
- created_at, expires_at, and completed_at parse as timezone-aware ISO-8601 values.
- expires_at is later than created_at.
- workspace_root is absolute.
- worker_pid is positive.
- provider, model ID, and model family are non-empty and are not unknown, none, null, or
  unavailable, case-insensitively.
- worker_tty may be None only when worker_transport_id begins with headless:.
- allowed_dispositions is non-empty, contains no duplicates, and contains only Disposition values.
- response_hash equals content_hash(response_text).

write_once_bytes must create a temporary file in the target directory, flush and fsync it, then
hard-link it to the final path with os.link. FileExistsError is allowed to escape. Always unlink
only the private temporary file in finally. Never unlink, truncate, or replace the target.
write_once_json calls canonical_json and appends one newline. load_json reads bytes once, rejects
non-object JSON, and wraps JSONDecodeError in ProtocolViolation without changing the source.

### Step 1.4: Run focused tests to verify GREEN

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/chatgpt_bridge/test_semantic_identity.py

Expected: 8 passed.

Run static checks:

    /Users/bob/GitHub/paeos/.venv/bin/ruff check \
      runtime/integrations/bridge_protocol.py \
      tests/chatgpt_bridge/test_semantic_identity.py
    /Users/bob/GitHub/paeos/.venv/bin/pyright \
      runtime/integrations/bridge_protocol.py

Expected: both commands exit 0.

### Step 1.5: Review and commit

    git diff --check
    git diff -- \
      runtime/integrations/bridge_protocol.py \
      tests/chatgpt_bridge/test_semantic_identity.py
    git status --short

Codex review gate: no monitor_loop.py change, no RATIFY disposition, no mutable request/response
write path, and all eight tests are behaviorally discriminative.

    git add runtime/integrations/bridge_protocol.py \
      tests/chatgpt_bridge/test_semantic_identity.py
    git commit -m "feat(bridge): add immutable protocol envelopes"

Stop and report the commit hash plus raw test/static-check output to Codex.

## Task 2: Inject State Root into ChatBridgeRuntime

**Files:**

- Modify: runtime/integrations/chat_bridge.py:33-179
- Modify: ops/autonomous_run.py:47-102
- Modify: tests/runtime/test_chat_bridge_fail_closed.py:67-100 and append new cases

ChatBridgeRuntime remains a compatibility transport in this subproject. It writes a unique prompt
file and waits for a unique correlated response file, both under the injected state root. It does
not emit the approved oversight envelope because physical worker identity is not yet available.

### Step 2.1: Rewrite the live-state test and add five failing tests

In test_bridge_adversarial_review_requires_real_orchestrator_output:

- Remove monkeypatch.chdir(REPO).
- Remove every reference to REPO / ".paeos_state".
- Set state_root = tmp_path / "state".
- Construct ChatBridgeRuntime with state_root=state_root.
- Have the test orchestrator wait for the exact request path below state_root/bridge/requests and
  write the exact response path below state_root/bridge/responses using write_once_bytes.
- Create tmp_path/production-sentinel/unchanged.txt before execution, hash its contents before and
  after, and assert the hash is unchanged.
- Assert every created bridge file is relative to state_root.resolve().

Add:

    def test_bridge_rejects_preexisting_correlated_response(tmp_path: Path) -> None

Pre-create the exact response path with valid-looking output, then call run. Assert the result
has TaskStatus.FAILED, its trace contains BRIDGE_STALE_RESPONSE, the response bytes are unchanged,
and an exact raw copy exists under state_root/bridge/quarantine.

Add:

    def test_bridge_refuses_reusing_exchange_id(tmp_path: Path) -> None

Execute the same package twice. The first execution may complete through a test orchestrator. The
second must return TaskStatus.FAILED with BRIDGE_DUPLICATE_REQUEST in its trace before delivery.
Assert the first request bytes were not overwritten and no second logical delivery occurred.

Add:

    def test_bridge_rejects_unbound_or_mismatched_worker_before_delivery(
        tmp_path: Path,
    ) -> None

Construct one package whose capability binding has an empty session and one whose binding run ID
does not match package.run_id. Call run for each with a distinct task ID. Assert both return
TaskStatus.FAILED with BRIDGE_UNBOUND_WORKER in the trace and that requests/ remains empty.

Add:

    def test_bridge_missing_response_times_out_without_retry(tmp_path: Path) -> None

Construct the runtime with timeout_seconds=0.01 and poll_seconds=0.001. Do not create a response.
Assert TaskStatus.FAILED, BRIDGE_RESPONSE_TIMEOUT in the trace, exactly one immutable prompt, and
zero retries or additional request files.

Add:

    def test_bridge_malformed_response_is_quarantined(tmp_path: Path) -> None

Have the test orchestrator write the bytes b"\xff" to the exact response path. Assert
TaskStatus.FAILED, BRIDGE_MALFORMED_RESPONSE in the trace, the original response bytes unchanged,
and an exact raw copy beneath quarantine.

### Step 2.2: Run tests to verify RED

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/runtime/test_chat_bridge_fail_closed.py

Expected: failures because ChatBridgeRuntime does not accept state_root and still uses global
current_prompt.md/current_output.md.

### Step 2.3: Implement explicit state-root routing

Change the constructor to require a keyword-only Path:

    def __init__(
        self,
        *,
        state_root: Path,
        workspace_root: Path | None = None,
        workspace_source: Path | None = None,
        artifact_resolver: Callable[[Hash], bytes] | None = None,
        mcp_config_path: Path | None = None,
        timeout_seconds: float = 300.0,
        poll_seconds: float = 0.25,
    ) -> None:
        self._paths = BridgePaths(state_root)
        self._paths.ensure()
        self._workspace_root = workspace_root
        self._workspace_source = (
            workspace_source.resolve() if workspace_source is not None else None
        )
        self._artifact_resolver = artifact_resolver
        self._mcp_config_path = mcp_config_path
        self._timeout_seconds = timeout_seconds
        self._poll_seconds = poll_seconds

Create a private safe exchange identifier:

    _SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9_.-]+$")

    def _exchange_id(package: TaskPackage) -> str:
        components = (
            package.run_id,
            package.task_id,
            package.stage.name.lower(),
        )
        if any(not _SAFE_COMPONENT.fullmatch(part) for part in components):
            raise ValueError("unsafe bridge exchange identifier")
        return "--".join(components)

For each run call derive:

    exchange_id = _exchange_id(package)
    prompt_path = self._paths.requests / f"{exchange_id}.prompt.md"
    output_path = self._paths.responses / f"{exchange_id}.response.md"

Before writing the prompt:

- Validate package.capability.bound_to before creating any bridge file. Its session must be
  non-empty and its goal ID, run ID, stage, and role must exactly match the package. Otherwise
  return RunOutput with TaskStatus.FAILED and BRIDGE_UNBOUND_WORKER in trace.
- If output_path exists, preserve an immutable raw quarantine copy and return RunOutput with
  TaskStatus.FAILED and BRIDGE_STALE_RESPONSE in trace.
- Persist the prompt with write_once_bytes. If FileExistsError occurs, return RunOutput with
  TaskStatus.FAILED and BRIDGE_DUPLICATE_REQUEST in trace.
- Never unlink prompt_path or output_path.
- Wait only for output_path. Never consume a global current_output.md.
- Stop at timeout_seconds with TaskStatus.FAILED and BRIDGE_RESPONSE_TIMEOUT in trace. Do not
  retry or create another prompt.
- Read the response bytes once and decode strict UTF-8. Empty, whitespace-only, or invalid UTF-8
  is BRIDGE_MALFORMED_RESPONSE: preserve a raw quarantine copy, fail, and do not delete or
  truncate the source.

Use a private helper for failures so the actual repository interface remains consistent:

    def _failed_run(code: str, message: str) -> RunOutput:
        return RunOutput(
            status=TaskStatus.FAILED,
            writes=(),
            evidence=(),
            trace=f"{code}: {message}".encode("utf-8"),
            cost=Cost(
                tokens=0,
                wallclock_s=0.0,
                model_ver="chat-bridge-compatibility",
            ),
        )

Replace hard-coded /Users/bob/GitHub/paeos references in the generated prompt:

- Workspace source comes from self._workspace_source.
- Court evidence path comes from self._paths.state_root / "court".
- The instruction identifies the already-bound Cline worker and explicitly forbids spawning
  subagents, invoking skills, ratifying, promoting, or changing terminals.

In ops/autonomous_run.py pass the scheduler state directory explicitly:

    runtime = ChatBridgeRuntime(
        state_root=state_dir.resolve(),
        workspace_source=repo_root,
        artifact_resolver=cas.get,
    )

Update all other ChatBridgeRuntime construction sites found by:

    rg -n "ChatBridgeRuntime\\(" .

Every construction must pass an explicit state_root. Test constructions use tmp_path only.

### Step 2.4: Run focused tests to verify GREEN

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/runtime/test_chat_bridge_fail_closed.py

Expected: 12 passed.

Also verify no test selects production state:

    rg -n 'monkeypatch\\.chdir|/Users/bob/GitHub/paeos/\\.paeos_state|current_prompt|current_output' \
      tests/runtime/test_chat_bridge_fail_closed.py

Expected: no matches.

Run static checks:

    /Users/bob/GitHub/paeos/.venv/bin/ruff check \
      runtime/integrations/chat_bridge.py \
      ops/autonomous_run.py \
      tests/runtime/test_chat_bridge_fail_closed.py
    /Users/bob/GitHub/paeos/.venv/bin/pyright \
      runtime/integrations/chat_bridge.py \
      ops/autonomous_run.py

Expected: both commands exit 0.

### Step 2.5: Review and commit

    git diff --check
    git diff -- \
      runtime/integrations/chat_bridge.py \
      ops/autonomous_run.py \
      tests/runtime/test_chat_bridge_fail_closed.py
    git status --short

Codex review gate: state_root is required, no production path remains, no request or response is
deleted, duplicate/stale/missing/malformed paths fail closed, ambiguous worker binding causes zero
delivery, and the compatibility transport is not presented as the Codex adapter.

    git add runtime/integrations/chat_bridge.py \
      ops/autonomous_run.py \
      tests/runtime/test_chat_bridge_fail_closed.py
    git commit -m "fix(bridge): isolate runtime state by explicit root"

Stop and report the commit hash plus raw test/static-check output to Codex.

## Task 3: Add the Fail-Closed Transaction Reducer

**Files:**

- Modify: runtime/integrations/bridge_protocol.py:1-end
- Modify: tests/chatgpt_bridge/test_semantic_identity.py:1-end

### Step 3.1: Add eleven failing reducer and store tests

Append these tests, bringing the semantic-identity file to exactly 19 tests:

9. test_reducer_accepts_the_single_happy_path
10. test_claim_requires_a_lease_owner
11. test_uncertain_side_effect_requires_reconciliation
12. test_circuit_breakers_are_exact_and_timeout_has_no_retry_transition
13. test_reconciliation_is_terminal_for_automation
14. test_founder_or_overseer_recovery_may_quarantine_reconciliation
15. test_response_correlation_accepts_exact_binding
16. test_mismatched_response_is_quarantined_and_not_consumed
17. test_legacy_sequence_81_migrates_to_reconciliation
18. test_malformed_stored_record_is_quarantined
19. test_duplicate_transaction_key_cannot_create_second_active_request

In test 16 loop over request_id, transaction_key, run_id, stage_id, payload_hash, lease_owner, and
disposition mutations inside one test function. Give every case a fresh tmp_path subdirectory.
Each case must raise ProtocolViolation, leave the transaction at CLAIMED, leave the mismatched
response unchanged, and create an exact raw quarantine copy. Keeping the cases inside one test
function preserves the plan's exact test count while still exercising every binding independently.

For the legacy test use:

    legacy = {
        "state": "SUBMITTED",
        "dispatch_seq": 81,
        "request_id": "legacy-seq-81",
        "transaction_key": "d" * 64,
        "run_id": "legacy-run",
        "stage_id": "legacy-stage",
        "payload_hash": "e" * 64,
    }

Assert state is RECONCILIATION_REQUIRED, legacy_state is SUBMITTED, legacy_dispatch_seq is 81,
and legacy_raw_hash equals content_hash(canonical_json(legacy)).

For malformed storage, write invalid bytes to a transaction file, call
TransactionStore.load_or_quarantine, assert ProtocolViolation, assert the original is not
rewritten, and assert one raw quarantine payload plus one reason document exists.

### Step 3.2: Run tests to verify RED

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/chatgpt_bridge/test_semantic_identity.py

Expected: the first eight tests pass and the eleven new tests fail import/collection because the
reducer/store symbols do not exist.

### Step 3.3: Implement states, events, records, and transitions

Add:

    class TransactionEvent(StrEnum):
        PREPARE = "PREPARE"
        CLAIM = "CLAIM"
        RESPOND = "RESPOND"
        CONSUME = "CONSUME"
        SIDE_EFFECT_UNCERTAIN = "SIDE_EFFECT_UNCERTAIN"
        QUARANTINE = "QUARANTINE"

There is deliberately no RETRY or RESEND event.

Add the exact circuit-breaker vocabulary:

    class CircuitBreaker(StrEnum):
        NONEXISTENT_OR_UNAUTHORIZED_SUBAGENT_INVOCATION = (
            "NONEXISTENT_OR_UNAUTHORIZED_SUBAGENT_INVOCATION"
        )
        UNREQUESTED_REVIEW_OR_SKILL_ROUTING = (
            "UNREQUESTED_REVIEW_OR_SKILL_ROUTING"
        )
        PASTED_GOVERNANCE_TEXT_INTERPRETED_AS_TOOL_ARGUMENTS = (
            "PASTED_GOVERNANCE_TEXT_INTERPRETED_AS_TOOL_ARGUMENTS"
        )
        COMMAND_EXPANSION_BEYOND_THE_AUTHORIZED_COMMAND = (
            "COMMAND_EXPANSION_BEYOND_THE_AUTHORIZED_COMMAND"
        )
        SHELL_COMMAND_MUTATED_MATERIALLY_FROM_DIRECTIVE = (
            "SHELL_COMMAND_MUTATED_MATERIALLY_FROM_DIRECTIVE"
        )
        REPEATED_IDENTICAL_FAILED_TOOL_CALL_WITHOUT_NEW_RATIONALE = (
            "REPEATED_IDENTICAL_FAILED_TOOL_CALL_WITHOUT_NEW_RATIONALE"
        )
        REPEATED_IDENTICAL_COMMAND_AFTER_SAME_RESULT_WITHOUT_EXPLICIT_RERUN_AUTHORITY = (
            "REPEATED_IDENTICAL_COMMAND_AFTER_SAME_RESULT_WITHOUT_EXPLICIT_RERUN_AUTHORITY"
        )
        WRITE_ATTEMPT_OUTSIDE_CURRENT_ALLOWLIST = (
            "WRITE_ATTEMPT_OUTSIDE_CURRENT_ALLOWLIST"
        )
        TRUNK_OR_MAIN_PROMOTION_ATTEMPT = "TRUNK_OR_MAIN_PROMOTION_ATTEMPT"
        UNAUTHORIZED_LIFECYCLE_ADVANCEMENT = (
            "UNAUTHORIZED_LIFECYCLE_ADVANCEMENT"
        )
        SELF_RATIFICATION_ATTEMPT = "SELF_RATIFICATION_ATTEMPT"

Upgrade ProtocolViolation so every rejection carries a CircuitBreaker:

    class ProtocolViolation(RuntimeError):
        def __init__(self, breaker: CircuitBreaker, message: str) -> None:
            super().__init__(message)
            self.breaker = breaker

Task 1 validation failures use WRITE_ATTEMPT_OUTSIDE_CURRENT_ALLOWLIST for unsafe paths and
UNAUTHORIZED_LIFECYCLE_ADVANCEMENT for invalid or incomplete envelopes. Duplicate transaction
creation uses
REPEATED_IDENTICAL_COMMAND_AFTER_SAME_RESULT_WITHOUT_EXPLICIT_RERUN_AUTHORITY. Invalid reducer
transitions use UNAUTHORIZED_LIFECYCLE_ADVANCEMENT. Callers may supply a more specific breaker
when the observed failure directly proves one.

Add frozen, slotted dataclasses:

    @dataclass(frozen=True, slots=True)
    class TransitionEntry:
        at: str
        actor: str
        event: TransactionEvent
        from_state: TransactionState
        to_state: TransactionState

    @dataclass(frozen=True, slots=True)
    class TransactionRecord:
        schema_version: str
        request_id: str
        transaction_key: str
        run_id: str
        stage_id: str
        payload_hash: str
        state: TransactionState = TransactionState.NEW
        lease_owner: str | None = None
        lease_expires_at: str | None = None
        last_side_effect: str | None = None
        transitions: tuple[TransitionEntry, ...] = ()
        legacy_state: str | None = None
        legacy_dispatch_seq: int | None = None
        legacy_raw_hash: str | None = None

    @dataclass(frozen=True, slots=True)
    class CircuitBreakerIncident:
        schema_version: str
        breaker: CircuitBreaker
        occurred_at: str
        request_id: str
        transaction_key: str
        state: TransactionState
        raw_exception: str
        request_envelope_hash: str
        last_confirmed_side_effect: str | None

Implement:

    def incident_from_violation(
        violation: ProtocolViolation,
        *,
        record: TransactionRecord,
        occurred_at: str,
        request_envelope_hash: str,
    ) -> CircuitBreakerIncident

It copies the exact breaker and raw exception text, validates the timestamp and envelope hash, and
copies record.last_side_effect without normalizing or interpreting it. In test 12, iterate over
all eleven CircuitBreaker members, construct one ProtocolViolation per member, and prove one
incident with the same breaker is produced. Also assert TransactionEvent contains neither RETRY
nor RESEND.

Implement this exact transition relation:

    _TRANSITIONS = {
        (TransactionState.NEW, TransactionEvent.PREPARE):
            TransactionState.PREPARED,
        (TransactionState.PREPARED, TransactionEvent.CLAIM):
            TransactionState.CLAIMED,
        (TransactionState.CLAIMED, TransactionEvent.RESPOND):
            TransactionState.RESPONDED,
        (TransactionState.RESPONDED, TransactionEvent.CONSUME):
            TransactionState.CONSUMED,
    }

reduce_transaction(record, event, *, actor, at, lease_owner=None,
lease_expires_at=None, last_side_effect=None) returns a replaced frozen record and appends one
TransitionEntry.

Additional rules:

- SIDE_EFFECT_UNCERTAIN moves NEW, PREPARED, CLAIMED, or RESPONDED to
  RECONCILIATION_REQUIRED.
- QUARANTINE moves any nonterminal state to QUARANTINED.
- QUARANTINE from RECONCILIATION_REQUIRED is permitted only for actor founder or
  overseer-recovery.
- CLAIM requires a non-empty lease_owner and a timezone-aware lease_expires_at later than at, and
  stores both.
- RESPOND and CONSUME require the existing lease_owner and a lease that is not stale at at.
- Any other transition raises ProtocolViolation and leaves the input record unchanged.
- CONSUMED, RECONCILIATION_REQUIRED, and QUARANTINED are terminal for automation.
- last_side_effect is changed only when explicitly supplied.
- actor and at are non-empty; at is a timezone-aware ISO-8601 timestamp.

Implement:

    def correlate_response(
        request: RequestEnvelope,
        response: ResponseEnvelope,
        *,
        record: TransactionRecord,
        now: str,
    ) -> None

It must validate both envelopes, reject expired requests at now, and require exact equality for
request_id, transaction_key, run_id, stage_id, payload_hash, record.lease_owner, and allowed
disposition. The record must be CLAIMED and its lease_expires_at must not be stale at now.

Implement:

    def migrate_legacy_transaction(
        raw: Mapping[str, object],
        *,
        at: str,
    ) -> TransactionRecord

Legacy outbound states DISPATCHING and SUBMITTED always map to RECONCILIATION_REQUIRED. Preserve
state, dispatch sequence, and canonical raw hash. Other unknown legacy states raise
ProtocolViolation; they are not guessed.

### Step 3.4: Implement atomic transaction storage and quarantine

Add:

    class TransactionStore:
        def __init__(self, paths: BridgePaths) -> None
        def create(self, record: TransactionRecord) -> Path
        def load(self, request_id: str) -> TransactionRecord
        def load_or_quarantine(self, request_id: str) -> TransactionRecord
        def save(self, record: TransactionRecord) -> None
        def persist_request(self, request: RequestEnvelope) -> Path
        def persist_response(self, response: ResponseEnvelope) -> Path
        def accept_response(
            self,
            request: RequestEnvelope,
            *,
            record: TransactionRecord,
            now: str,
        ) -> ResponseEnvelope

Rules:

- create scans transaction records and rejects a second nonterminal record with the same
  transaction_key.
- create, persist_request, and persist_response are write-once.
- save is the only mutable path. It writes a private file in transactions/, flushes and fsyncs,
  then uses os.replace to atomically replace only that record's state file.
- load reconstructs enums, tuples, and nested TransitionEntry values explicitly. Do not use
  unvalidated dataclass unpacking.
- load_or_quarantine catches malformed JSON, missing fields, bad enum values, and validation
  errors. It writes the exact original bytes with write_once_bytes under quarantine using a
  filename containing the raw SHA-256, writes a canonical reason JSON beside it, and raises
  ProtocolViolation.
- Quarantine never repairs, deletes, or rewrites the original.
- Path identifiers pass the same safe-component validation before path construction.
- accept_response reads the immutable response path derived from request.request_id, reconstructs
  a ResponseEnvelope explicitly, and calls correlate_response. Any parse, validation, expiry, or
  correlation failure copies the exact raw bytes plus a reason document to quarantine and raises
  ProtocolViolation. It never changes a transaction record to RESPONDED or CONSUMED on failure.

### Step 3.5: Run focused tests to verify GREEN

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/chatgpt_bridge/test_semantic_identity.py

Expected: 19 passed.

Run static checks:

    /Users/bob/GitHub/paeos/.venv/bin/ruff check \
      runtime/integrations/bridge_protocol.py \
      tests/chatgpt_bridge/test_semantic_identity.py
    /Users/bob/GitHub/paeos/.venv/bin/pyright \
      runtime/integrations/bridge_protocol.py

Expected: both commands exit 0.

### Step 3.6: Review and commit

    git diff --check
    git diff -- \
      runtime/integrations/bridge_protocol.py \
      tests/chatgpt_bridge/test_semantic_identity.py
    git status --short

Codex review gate: no retry/resend event exists, uncertain side effects fail closed, sequence 81
cannot become consumed, all correlation fields are exact, and quarantine preserves raw evidence.

    git add runtime/integrations/bridge_protocol.py \
      tests/chatgpt_bridge/test_semantic_identity.py
    git commit -m "feat(bridge): enforce fail-closed transaction reducer"

Stop and report the commit hash plus raw test/static-check output to Codex.

## Task 4: Make the Watchdog Observer-Only

**Files:**

- Replace: ops/chatgpt_bridge/watchdog.py:1-end
- Create: tests/chatgpt_bridge/test_watchdog_observer.py

The current watchdog restarts the bridge, relaunches Chrome, sends clipboard/AppleScript input,
kills processes, nudges Cline, deletes a stale PID file, and may report that it healed the
system. Remove those mutation paths. The watchdog reports health only.

### Step 4.1: Write three failing observer tests

Create:

1. test_unhealthy_report_performs_no_mutation
2. test_stale_pid_file_is_preserved
3. test_run_watchdog_reports_issues_without_recovery_actions

For the first test monkeypatch diagnostic functions to return stopped/stale conditions and
monkeypatch subprocess.Popen, subprocess.run, os.kill, Path.unlink, and Path.write_text to raise
AssertionError if called by the watchdog. Call collect_report and assert the returned issues name
the stopped bridge, stale log, missing Cline process, stale repository, and stale response.

For the second test write a nonexistent numeric PID to tmp_path/bridge.pid, call
check_bridge_monitor, and assert the return value is (False, that_pid) and the PID file bytes are
unchanged.

For the third test, create a fixed unhealthy WatchdogReport and replace collect_report with a
test double returning that complete real-shaped report. Replace subprocess.Popen, os.kill,
Path.unlink, Path.write_text, and Path.touch with sentinels that raise AssertionError. Call
run_watchdog, assert it returns the same report, assert the warning log contains every issue, and
assert no mutation sentinel fired. This test guards the observable boundary; do not test source
text or private symbol names.

During Codex review, separately inspect the diff and run:

    rg -n 'Popen|os\\.kill|\\.unlink\\(|pbcopy|osascript|restart_bridge_monitor|relaunch_chrome|nudge_cline|heal(ed|ing)' \
      ops/chatgpt_bridge/watchdog.py

Expected: no matches. This is a review check, not a behavioral unit test.

### Step 4.2: Run tests to verify RED

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/chatgpt_bridge/test_watchdog_observer.py

Expected: failures because the legacy watchdog contains and invokes recovery mutations.

### Step 4.3: Replace the watchdog with a read-only report

Use:

    @dataclass(frozen=True, slots=True)
    class WatchdogReport:
        bridge_alive: bool
        bridge_pid: int | None
        bridge_log_age_minutes: float | None
        cline_alive: bool
        repo_idle_minutes: float | None
        response_age_minutes: float | None
        issues: tuple[str, ...]

Implement:

    def check_bridge_monitor(pid_file: Path) -> tuple[bool, int | None]
    def file_age_minutes(path: Path, *, now: float | None = None) -> float | None
    def check_cline_process() -> bool
    def repo_idle_minutes(repo_root: Path, *, now: float | None = None) -> float | None
    def collect_report(repo_root: Path, bridge_dir: Path) -> WatchdogReport
    def run_watchdog(repo_root: Path, bridge_dir: Path) -> WatchdogReport

Rules:

- check_bridge_monitor reads only the exact PID file supplied. Invalid or missing content returns
  (False, None). A numeric PID is checked with subprocess.run(["ps", "-p", str(pid), "-o",
  "pid="], capture_output=True, text=True, check=False). It never uses pgrep and never changes the
  PID file.
- check_cline_process may use subprocess.run with a read-only process listing. It does not infer
  a worker binding; it reports only presence.
- repo_idle_minutes reads git metadata or invokes read-only git log/status commands. It never
  commits, restores, cleans, checks out, or changes branches.
- collect_report reads bridge.log, the exact PID file, repository activity, and latest response
  mtime. It builds a tuple of issues without changing any file or process.
- run_watchdog logs the report to standard logging and returns it. It does not write a log file,
  launch a process, sleep/retry, alter transaction state, paste, kill, restart, or claim recovery.
- Remove every legacy function after the old __main__ block as well as the active auto-healing
  functions. Keep one __main__ entry point that only calls run_watchdog with explicit CLI paths
  and exits nonzero when issues are present.

### Step 4.4: Run focused tests to verify GREEN

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/chatgpt_bridge/test_watchdog_observer.py

Expected: 3 passed.

Run static checks:

    /Users/bob/GitHub/paeos/.venv/bin/ruff check \
      ops/chatgpt_bridge/watchdog.py \
      tests/chatgpt_bridge/test_watchdog_observer.py
    /Users/bob/GitHub/paeos/.venv/bin/pyright \
      ops/chatgpt_bridge/watchdog.py

Expected: both commands exit 0.

### Step 4.5: Review and commit

    git diff --check
    git diff -- \
      ops/chatgpt_bridge/watchdog.py \
      tests/chatgpt_bridge/test_watchdog_observer.py
    git status --short

Codex review gate: every health check is read-only, stale PID state is preserved as evidence,
there is no automatic recovery claim, and no GUI/clipboard/terminal/process mutation remains.

    git add ops/chatgpt_bridge/watchdog.py \
      tests/chatgpt_bridge/test_watchdog_observer.py
    git commit -m "fix(watchdog): make recovery monitoring observer-only"

Stop and report the commit hash plus raw test/static-check output to Codex.

## Task 5: Prove Isolation and Discriminative Safety

**Files:**

- Verify only; do not modify production, governance, lifecycle, notebook, or SAKG files.

### Step 5.1: Capture production-state manifest before tests

This command is read-only against the dirty main checkout:

    find /Users/bob/GitHub/paeos/.paeos_state -type f \
      -exec openssl dgst -sha256 {} \; |
      LC_ALL=C sort > /tmp/paeos-prod-state.before

Record:

    openssl dgst -sha256 /tmp/paeos-prod-state.before
    /Users/bob/GitHub/paeos/.venv/bin/python --version
    /Users/bob/GitHub/paeos/.venv/bin/python -c \
      'import platform, sys; print(sys.executable); print(platform.platform())'
    sw_vers
    git status --short --branch
    git rev-parse HEAD
    git log -5 --oneline

The bound Cline transport must preserve each Step 5 command's raw stdout, stderr, and process exit
code. Copy those raw transcripts outside the repository as:

    /tmp/paeos-s1-5-2-focused.log
    /tmp/paeos-s1-5-3-full.log
    /tmp/paeos-s1-5-5-mutation-1.log
    /tmp/paeos-s1-5-5-mutation-2.log
    /tmp/paeos-s1-5-5-mutation-3.log
    /tmp/paeos-s1-5-5-mutation-4.log
    /tmp/paeos-s1-5-6-focused.log
    /tmp/paeos-s1-5-6-full.log
    /tmp/paeos-s1-5-6-ruff.log
    /tmp/paeos-s1-5-6-pyright.log

If the worker transport cannot provide raw stdout, stderr, and exit status without rerunning a
command, halt before Step 5.2. Do not substitute a prose summary.

### Step 5.2: Run the focused recovery suite

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/runtime/test_chat_bridge_fail_closed.py \
      tests/chatgpt_bridge/test_semantic_identity.py \
      tests/chatgpt_bridge/test_watchdog_observer.py

Expected: 34 passed.

### Step 5.3: Run the full suite in the isolated worktree

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q

Expected: 538 passed. If collection or any test fails, preserve raw output, do not rerun the
identical command, and stop for Codex adjudication.

### Step 5.4: Prove production state did not change

    find /Users/bob/GitHub/paeos/.paeos_state -type f \
      -exec openssl dgst -sha256 {} \; |
      LC_ALL=C sort > /tmp/paeos-prod-state.after
    cmp /tmp/paeos-prod-state.before /tmp/paeos-prod-state.after
    openssl dgst -sha256 /tmp/paeos-prod-state.after

Expected: cmp exits 0 and the before/after manifest hashes are identical.

Also prove the implementation worktree contains no bridge runtime state:

    find /private/tmp/paeos-control-plane-recovery-s1 \
      -path '*/.paeos_state/*' -print

Expected: no output.

### Step 5.5: Run reversible mutation checks

Perform one mutation at a time with apply_patch. Run only the named test, confirm it fails for the
intended reason, then restore the deliberately changed file from the current commit before the
next mutation.

1. Change write_once_bytes to os.replace its target. Run
   test_write_once_json_refuses_overwrite. Expected: FAIL because the second value replaces the
   first. Restore with:

       git restore --source=HEAD -- runtime/integrations/bridge_protocol.py

2. Change SIDE_EFFECT_UNCERTAIN to preserve PREPARED. Run
   test_uncertain_side_effect_requires_reconciliation. Expected: FAIL. Restore with:

       git restore --source=HEAD -- runtime/integrations/bridge_protocol.py

3. Change ChatBridgeRuntime to derive its root from Path(".paeos_state"). Run
   test_bridge_adversarial_review_requires_real_orchestrator_output. Expected: FAIL because the
   injected root is unused or the expected request never appears. Restore with:

       git restore --source=HEAD -- runtime/integrations/chat_bridge.py

4. Add a subprocess.Popen call to run_watchdog. Run
   test_run_watchdog_reports_issues_without_recovery_actions. Expected: FAIL because the
   no-mutation sentinel is triggered. Restore with:

       git restore --source=HEAD -- ops/chatgpt_bridge/watchdog.py

After every restore run:

    git status --short

Expected after each restore: no output. These restores apply only to deliberate, uncommitted
mutation-test changes in the isolated worktree.

### Step 5.6: Re-run final verification after mutations are restored

    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
      tests/runtime/test_chat_bridge_fail_closed.py \
      tests/chatgpt_bridge/test_semantic_identity.py \
      tests/chatgpt_bridge/test_watchdog_observer.py
    /Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q
    /Users/bob/GitHub/paeos/.venv/bin/ruff check \
      runtime/integrations/bridge_protocol.py \
      runtime/integrations/chat_bridge.py \
      ops/autonomous_run.py \
      ops/chatgpt_bridge/watchdog.py \
      tests/runtime/test_chat_bridge_fail_closed.py \
      tests/chatgpt_bridge/test_semantic_identity.py \
      tests/chatgpt_bridge/test_watchdog_observer.py
    /Users/bob/GitHub/paeos/.venv/bin/pyright \
      runtime/integrations/bridge_protocol.py \
      runtime/integrations/chat_bridge.py \
      ops/autonomous_run.py \
      ops/chatgpt_bridge/watchdog.py

Expected: 34 focused tests pass, 538 full tests pass, Ruff exits 0, and Pyright exits 0.

Hash every preserved transcript:

    openssl dgst -sha256 /tmp/paeos-s1-5-2-focused.log
    openssl dgst -sha256 /tmp/paeos-s1-5-3-full.log
    openssl dgst -sha256 /tmp/paeos-s1-5-5-mutation-1.log
    openssl dgst -sha256 /tmp/paeos-s1-5-5-mutation-2.log
    openssl dgst -sha256 /tmp/paeos-s1-5-5-mutation-3.log
    openssl dgst -sha256 /tmp/paeos-s1-5-5-mutation-4.log
    openssl dgst -sha256 /tmp/paeos-s1-5-6-focused.log
    openssl dgst -sha256 /tmp/paeos-s1-5-6-full.log
    openssl dgst -sha256 /tmp/paeos-s1-5-6-ruff.log
    openssl dgst -sha256 /tmp/paeos-s1-5-6-pyright.log

### Step 5.7: Final evidence handoff

    git status --short --branch
    git log --oneline \
      paeos-control-plane-recovery-s1-contract-v1..HEAD
    git diff --stat \
      paeos-control-plane-recovery-s1-contract-v1..HEAD

Expected: a clean codex/control-plane-recovery-s1 branch containing exactly the four reviewed
implementation commits. Do not merge, rebase onto main, cherry-pick into main, push, or promote.

Hand Codex:

- All four commit hashes.
- Exact focused/full test counts and raw output.
- Ruff and Pyright output.
- Production-state manifest before/after hashes and cmp exit status.
- The four mutation-test failures and their intended reason.
- Final git status and diff stat.

Codex performs a separate review against the approved design and reports one of CONTINUE, REMAND,
HALT, or NEEDS_FOUNDER. Passing tests do not constitute constitutional ratification.

## Execution Handoff

Recommended execution mode: one fresh, explicitly bound Cline paeos-code session per task. Codex
reviews the diff, raw evidence, and circuit-breaker compliance after each commit before issuing
CONTINUE.

Permitted fallback: one explicitly bound Cline paeos-code session executes Tasks 1-2, pauses for
Codex review, then Tasks 3-4, pauses again, and finally performs Task 5. No task may proceed after
a failed review gate.

The implementation must not be routed through monitor_loop.py or the broken GUI bridge. The
approved isolated-recovery exception is the authority for direct Cline implementation in the
dedicated worktree only.
