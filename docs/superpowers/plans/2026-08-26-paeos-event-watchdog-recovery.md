# PAEOS Event Watchdog and Safe Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox syntax for tracking.

**Goal:** Replace sluggish GUI/repository-idle monitoring with deterministic transaction-event
deadlines and safe recovery decisions that restart stateless adapters without replaying ambiguous
side effects.

**Architecture:** The watchdog reads a verified ledger-derived projection and a monotonic clock.
It distinguishes transport heartbeat from meaningful progress, evaluates immutable deadline
policy, and emits typed recovery proposals. The canonical coordinator validates and commits any
lease expiry, adapter restart, provider rotation, halt, or reconciliation transition. The watchdog
cannot edit evidence, redesign work, ratify, promote, or dispatch by itself. Storage pressure
halts new work before forensic evidence is discarded.

**Tech Stack:** Python 3.12, frozen dataclasses, monotonic fake clock, existing transaction
projection/coordinator, filesystem quota observations, pytest, Ruff, Pyright.

**Spec:** `docs/superpowers/specs/2026-08-26-paeos-ai-supervised-autonomy-design.md` sections 9-10

## Global Constraints

- Depends on fenced transactions, headless supervisor adapters, and production worker confinement.
- Repository mtime, commit age, log age, Chrome, terminal text, and PID existence are diagnostic
  only and cannot declare progress or authorize recovery.
- Streaming tokens and heartbeats prove liveness, not lifecycle progress.
- Default policy: heartbeat 15s, soft diagnostic 120s, pre-side-effect hard stall 300s, tool
  deadline 300s, Trace-A transaction deadline 1800s, Trace-B checkpoints at least every 300s.
- No broad exception handler may sleep and continue the same transaction.
- Only proven pre-side-effect work can lose its lease safely. Possible side effect means
  `RECONCILIATION_REQUIRED` and no autonomous replay.
- One quarantined or Founder-gated goal does not block unrelated goals unless shared ledger,
  kernel, signing, or projection integrity is affected.

---

## Task 1: Define Meaningful Events and Deadline Policy

**Files:**

- Create: `runtime/control_plane/liveness.py`
- Test: `tests/runtime/control_plane/test_liveness_policy.py`

**Interfaces:**

```python
class ProgressKind(StrEnum):
    HEARTBEAT = "HEARTBEAT"
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_PROGRESS = "TOOL_PROGRESS"
    TOOL_FINISHED = "TOOL_FINISHED"
    ARTIFACT_COMMITTED = "ARTIFACT_COMMITTED"
    RESPONSE_PERSISTED = "RESPONSE_PERSISTED"
    RESPONSE_VERIFIED = "RESPONSE_VERIFIED"

@dataclass(frozen=True, slots=True)
class DeadlinePolicy:
    heartbeat_seconds: int = 15
    soft_stall_seconds: int = 120
    pre_side_effect_hard_stall_seconds: int = 300
    default_tool_seconds: int = 300
    trace_a_seconds: int = 1800
    trace_b_checkpoint_seconds: int = 300

@dataclass(frozen=True, slots=True)
class LivenessSnapshot:
    transaction_key: str
    state: TransactionState
    fencing_token: int
    last_heartbeat_monotonic: float | None
    last_meaningful_monotonic: float
    active_tool_deadline_monotonic: float | None
    transaction_deadline_monotonic: float
    side_effect_certainty: SideEffectCertainty
```

- [ ] **Step 1.1: Write RED pure-policy tests with a fake clock**

Test exact threshold boundaries, tokens without progress, authorized long-tool progress, clock
regression, missing heartbeat, missing meaningful event, tool timeout, task timeout, Trace-B
checkpoint, terminal state, and side-effect certainty. No test sleeps.

- [ ] **Step 1.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_liveness_policy.py
```

Expected: collection fails because `runtime.control_plane.liveness` does not exist.

- [ ] **Step 1.3: Implement pure time evaluation**

Convert monotonic observations into typed facts before persistence. The canonical ledger stores
logical event ordering and policy/deadline facts; it does not claim wall-clock order is authority.

- [ ] **Step 1.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_liveness_policy.py
```

- [ ] **Step 1.5: Commit**

```bash
git add runtime/control_plane/liveness.py \
  tests/runtime/control_plane/test_liveness_policy.py
git commit -m "feat(control-plane): define event-based liveness policy"
```

---

## Task 2: Implement a Read-Only Watchdog Decision Engine

**Files:**

- Create: `runtime/control_plane/watchdog.py`
- Test: `tests/runtime/control_plane/test_watchdog.py`
- Modify: `ops/chatgpt_bridge/watchdog.py`
- Modify: `tests/chatgpt_bridge/test_watchdog_observer.py`

**Interfaces:**

```python
class RecoveryAction(StrEnum):
    NONE = "NONE"
    DIAGNOSE = "DIAGNOSE"
    EXPIRE_PRE_SIDE_EFFECT_LEASE = "EXPIRE_PRE_SIDE_EFFECT_LEASE"
    RESTART_STATELESS_ADAPTER = "RESTART_STATELESS_ADAPTER"
    ROTATE_PROVIDER = "ROTATE_PROVIDER"
    REQUIRE_RECONCILIATION = "REQUIRE_RECONCILIATION"
    HALT_SHARED_CONTROL_PLANE = "HALT_SHARED_CONTROL_PLANE"

@dataclass(frozen=True, slots=True)
class WatchdogDecision:
    transaction_key: str
    fencing_token: int
    action: RecoveryAction
    reason_code: str
    observed_ledger_head: str
    evidence_hashes: tuple[str, ...]

def decide_recovery(
    snapshot: LivenessSnapshot,
    *,
    now_monotonic: float,
    projection_verified: bool,
    shared_integrity_healthy: bool,
) -> WatchdogDecision: ...
```

- [ ] **Step 2.1: Write RED decision-matrix tests**

Cover each action, ambiguous side effect, poisoned projection, ledger-chain failure, stale fence,
terminal transaction, unrelated-goal isolation, rate limit before/after acceptance, deterministic
bad request, scope violation, provenance conflict, circuit breaker, and identical failed command.

- [ ] **Step 2.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_watchdog.py \
  tests/chatgpt_bridge/test_watchdog_observer.py
```

Expected: new tests fail. Existing legacy observer tests describe compatibility behavior only.

- [ ] **Step 2.3: Implement pure decisions and demote legacy signals**

Make `ops/chatgpt_bridge/watchdog.py` explicitly report `compatibility_diagnostics`; remove any
claim that a stale repository or response file is canonical health. Do not add restart or write
behavior to the legacy observer.

- [ ] **Step 2.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_watchdog.py \
  tests/chatgpt_bridge/test_watchdog_observer.py
```

- [ ] **Step 2.5: Commit**

```bash
git add runtime/control_plane/watchdog.py ops/chatgpt_bridge/watchdog.py \
  tests/runtime/control_plane/test_watchdog.py \
  tests/chatgpt_bridge/test_watchdog_observer.py
git commit -m "feat(control-plane): decide recovery from transaction events"
```

---

## Task 3: Apply Recovery Through the Canonical Coordinator

**Files:**

- Create: `runtime/control_plane/recovery.py`
- Modify: `runtime/control_plane/coordinator.py`
- Test: `tests/runtime/control_plane/test_recovery.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class RecoveryReceipt:
    decision_hash: str
    action: RecoveryAction
    ledger_seq: int | None
    ledger_head: str
    resulting_state: TransactionState
    new_fencing_token: int | None

class RecoveryController:
    def apply(self, decision: WatchdogDecision) -> RecoveryReceipt: ...
```

- [ ] **Step 3.1: Write RED stale-decision and crash tests**

Test decision head changed, fence changed, already recovered, crash before commit, crash after
commit, adapter restart failure, provider rotation without eligible profile, lease expiry after a
side effect becomes possible, and duplicate application. A decision is advisory until committed.

- [ ] **Step 3.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_recovery.py
```

Expected: fails because the recovery controller does not exist.

- [ ] **Step 3.3: Implement compare-before-commit recovery**

Re-verify ledger head, transaction digest, fence, and side-effect certainty. Safe lease expiry
increments the fence before a new claim. Ambiguity appends `SIDE_EFFECT_UNCERTAIN`. Shared
integrity failure halts new dispatch globally; local route failure quarantines only that tuple.

- [ ] **Step 3.4: Run GREEN with transaction tests**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_recovery.py \
  tests/runtime/control_plane/test_coordinator.py \
  tests/runtime/control_plane/test_side_effect_recovery.py
```

- [ ] **Step 3.5: Commit**

```bash
git add runtime/control_plane/recovery.py runtime/control_plane/coordinator.py \
  tests/runtime/control_plane/test_recovery.py
git commit -m "feat(control-plane): apply fenced recovery decisions"
```

---

## Task 4: Add Forensic Storage Back-Pressure

**Files:**

- Create: `runtime/control_plane/storage_policy.py`
- Test: `tests/runtime/control_plane/test_storage_policy.py`
- Modify: `runtime/control_plane/watchdog.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class StorageObservation:
    cas_bytes: int
    trace_bytes: int
    projection_bytes: int
    quarantine_bytes: int
    free_bytes: int

class StorageDisposition(StrEnum):
    ACCEPT = "ACCEPT"
    BACKPRESSURE = "BACKPRESSURE"
    HALT_NEW_DISPATCH = "HALT_NEW_DISPATCH"

def decide_storage(observation: StorageObservation, policy: StoragePolicy) -> StorageDisposition: ...
```

- [ ] **Step 4.1: Write RED quota tests**

Test soft/hard boundaries, overflow/negative values, growing quarantine, low disk, concurrent new
dispatch, terminal evidence retention, and projection rebuild. No policy may delete raw evidence
to make a test pass.

- [ ] **Step 4.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_storage_policy.py
```

- [ ] **Step 4.3: Implement back-pressure only**

At hard pressure, refuse NEW/PREPARE dispatches while allowing already-committed evidence flush
and read-only reconciliation. Retention/deletion requires a separately reviewed policy and is not
implemented by this plan.

- [ ] **Step 4.4: Run GREEN**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_storage_policy.py
```

- [ ] **Step 4.5: Commit**

```bash
git add runtime/control_plane/storage_policy.py runtime/control_plane/watchdog.py \
  tests/runtime/control_plane/test_storage_policy.py
git commit -m "feat(control-plane): halt safely on storage pressure"
```

---

## Task 5: Replace the Legacy Monitor Loop Entry Point

**Files:**

- Create: `ops/control_plane_watchdog.py`
- Modify: `ops/chatgpt_bridge/monitor_loop.py`
- Modify: `ops/chatgpt_bridge/watchdog_cron.sh`
- Create: `tests/ops/test_control_plane_watchdog_cli.py`

- [ ] **Step 5.1: Write RED CLI tests**

Assert run-once behavior, verified state-root binding, machine-readable output, no clipboard,
AppleScript, CDP, terminal keystrokes, browser polling, autonomous retry, or unbounded sleep. A
missing/invalid projection returns nonzero and preserves diagnostics.

- [ ] **Step 5.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/ops/test_control_plane_watchdog_cli.py
```

- [ ] **Step 5.3: Implement a run-once deterministic CLI**

`ops/control_plane_watchdog.py` reads one verified snapshot, prints one canonical report, submits
at most one typed recovery proposal to the coordinator, and exits. External scheduling controls
frequency. Replace `monitor_loop.py` with a deprecation/error entry point that cannot copy/paste
or dispatch; preserve the old source in Git history, not as active code.

- [ ] **Step 5.4: Run GREEN and static source assertions**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/ops/test_control_plane_watchdog_cli.py tests/chatgpt_bridge
```

Expected: all pass; active control-plane code contains no `pbcopy`, `osascript`, CDP, browser tab,
or terminal paste path.

- [ ] **Step 5.5: Commit**

```bash
git add ops/control_plane_watchdog.py ops/chatgpt_bridge/monitor_loop.py \
  ops/chatgpt_bridge/watchdog_cron.sh tests/ops/test_control_plane_watchdog_cli.py
git commit -m "fix(ops): replace GUI monitor with event watchdog"
```

---

## Task 6: L13, L14, and L17 Gate

**Files:**

- Create: `reviews/tasks/PAEOS_EVENT_WATCHDOG_RECOVERY_review.md`
- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Modify: `MessyChangesNeedsReview.md` only for unresolved debt

- [ ] **Step 6.1: Run focused and full verification fresh**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane tests/ops/test_control_plane_watchdog_cli.py \
  tests/chatgpt_bridge
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q
git diff --check
```

- [ ] **Step 6.2: Run the liveness fault matrix**

Inject hung reasoning, hung tool, token-only stream, quota loss, process death, stale fence,
projection poison, disk exhaustion, pre/post-side-effect crash, unrelated transaction, and
identical failed command. Assert exact expected disposition for each.

- [ ] **Step 6.3: Obtain physically decorrelated L14 audit**

Audit only sealed code/evidence. Ensure the watchdog implementer did not supply its own audit.

- [ ] **Step 6.4: Record L17 and stop before automatic restart is activated**

Report exact Court counts. Activation occurs only as part of the later canary ladder.

- [ ] **Step 6.5: Commit review records**

```bash
git add PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md MessyChangesNeedsReview.md \
  reviews/tasks/PAEOS_EVENT_WATCHDOG_RECOVERY_review.md
git commit -m "docs(review): record event watchdog disposition"
```
