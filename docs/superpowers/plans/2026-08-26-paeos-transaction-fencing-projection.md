# PAEOS Transaction Fencing and Projection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox syntax for durable tracking.

**Goal:** Repay DEBT-0059 by making the kernel ledger the canonical transaction history while
providing crash-rebuildable queue queries, expected-prior comparison, and monotonic fencing that
prevents stale or competing processes from committing.

**Architecture:** Keep the reviewed seven-state reducer in
`runtime/integrations/bridge_protocol.py`. Represent each accepted reducer input as a canonical
`CONTROL_PLANE_TRANSACTION` ledger event. A pure projector folds verified ledger rows into
`ProjectedTransaction` records. SQLite WAL stores only a replaceable projection tagged with its
source ledger head. The single Execution Layer coordinator performs comparison and append; it
updates the projection only after the ledger commit. A missing update rebuilds from ledger. An
uncertain external side effect is terminal for automation.

**Tech Stack:** Python 3.12, frozen dataclasses, `kernel.ledger.Event`, SQLite WAL, file-system
durability, pytest, Hypothesis, Ruff, Pyright.

**Spec:** `docs/superpowers/specs/2026-08-26-paeos-ai-supervised-autonomy-design.md` sections 4-5

## Global Constraints

- Complete this plan before any production supervisor or worker dispatch.
- Do not add transaction states. `CONTINUE`, `REMAND`, `HALT`, and `NEEDS_FOUNDER` remain response
  dispositions, not states.
- Do not make the projection, `TransactionStore` JSON, PID, lock file, clock, or log canonical.
- Do not dual-write the ledger and projection as one success condition. Ledger commit succeeds
  first; projection update is rebuildable.
- A fence is logical authority. Wall time is used only for deadlines.
- Any post-dispatch ambiguity must commit `SIDE_EFFECT_UNCERTAIN`, producing
  `RECONCILIATION_REQUIRED`; never retry it automatically.
- Preserve raw malformed records in quarantine and preserve the eleven breaker classes.

---

## Task 1: Define Canonical Transaction Events and a Pure Projector

**Files:**

- Create: `runtime/control_plane/__init__.py`
- Create: `runtime/control_plane/events.py`
- Create: `runtime/control_plane/projection.py`
- Test: `tests/runtime/control_plane/test_projection.py`
- Reuse: `runtime/integrations/bridge_protocol.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class TransactionCommand:
    request_id: str
    transaction_key: str
    run_id: str
    stage_id: str
    payload_hash: str
    event: TransactionEvent
    actor: str
    at: str
    expected_prior_digest: str
    fencing_token: int
    lease_owner: str | None = None
    lease_expires_at: str | None = None
    last_side_effect: str | None = None

@dataclass(frozen=True, slots=True)
class ProjectedTransaction:
    record: TransactionRecord
    digest: str
    fencing_token: int
    ledger_seq: int
    ledger_head: str

def transaction_event(command: TransactionCommand) -> Event: ...
def project_row(current: ProjectedTransaction | None, row: LedgerRow) -> ProjectedTransaction: ...
def rebuild_projection(rows: Iterable[LedgerRow]) -> dict[str, ProjectedTransaction]: ...
```

- [x] **Step 1.1: Write RED reducer-projection tests**

Cover exact happy-path folding, invalid transition, stale `expected_prior_digest`, decreasing or
reused fence, duplicate `transaction_key`, malformed payload, unknown schema, and both terminal
states. Assert the existing `reduce_transaction()` remains the only state-transition function.

- [x] **Step 1.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_projection.py
```

Expected: collection fails because `runtime.control_plane.events` and `.projection` do not exist.

- [x] **Step 1.3: Implement the minimal event codec and projector**

Use `SCHEMA_VERSION`, `canonical_json()`, and `reduce_transaction()` from the reviewed protocol.
The canonical event kind is `CONTROL_PLANE_TRANSACTION`; the payload contains the complete
command and no model-authored free-form authority. Compute the projected digest from canonical
record bytes plus fence and ledger sequence.

- [x] **Step 1.4: Run GREEN and property tests**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_projection.py \
  tests/chatgpt_bridge/test_semantic_identity.py
```

Expected: all selected tests pass; generated invalid event sequences never create an unreviewed
state or move out of a terminal state.

- [x] **Step 1.5: Commit**

```bash
git add runtime/control_plane tests/runtime/control_plane/test_projection.py
git commit -m "feat(control-plane): derive transactions from ledger events"
```

---

## Task 2: Add Ledger-Head-Bound SQLite Projection Storage

**Files:**

- Create: `runtime/control_plane/sqlite_projection.py`
- Test: `tests/runtime/control_plane/test_sqlite_projection.py`
- Modify: `runtime/integrations/bridge_protocol.py`

**Interfaces:**

```python
class ProjectionCorruption(RuntimeError): ...
class ProjectionHeadMismatch(RuntimeError): ...

class SqliteControlPlaneProjection:
    def replace_from_verified_ledger(self, rows: Sequence[LedgerRow], head_hash: str) -> None: ...
    def apply_committed(self, row: LedgerRow, verified_prior_head: str) -> None: ...
    def get(self, request_id: str, *, verified_ledger_head: str) -> ProjectedTransaction: ...
    def claimable(self, *, verified_ledger_head: str) -> tuple[ProjectedTransaction, ...]: ...
    def recorded_head(self) -> tuple[int, str] | None: ...
```

- [ ] **Step 2.1: Write RED persistence and poison tests**

Test WAL/full-sync configuration, atomic replacement, restart, ledger-ahead/projection-behind,
projection-ahead, forged row digest, forged recorded head, missing row, extra row, and crash after
ledger append but before projection update. A poisoned projection must answer no claim query.

- [ ] **Step 2.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_sqlite_projection.py
```

Expected: collection fails because `SqliteControlPlaneProjection` does not exist.

- [ ] **Step 2.3: Implement replaceable projection storage**

Use `BEGIN IMMEDIATE`, `PRAGMA journal_mode=WAL`, and `PRAGMA synchronous=FULL`. Store the source
`ledger_seq`, `ledger_head`, event row hash, projected digest, fence, and canonical record JSON.
No projection API may accept an unverified caller-supplied state record.

Keep `TransactionStore` as a compatibility/materialization seam only. Mark its module docstring and
call sites accordingly; new coordinator code must not treat its mutable JSON as canonical.

- [ ] **Step 2.4: Run GREEN and crash-gap tests**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_projection.py \
  tests/runtime/control_plane/test_sqlite_projection.py
```

Expected: all pass; deleting or corrupting the projection causes deterministic rebuild or a
fail-closed error, never a second ledger event.

- [ ] **Step 2.5: Commit**

```bash
git add runtime/control_plane/sqlite_projection.py \
  runtime/integrations/bridge_protocol.py \
  tests/runtime/control_plane/test_sqlite_projection.py
git commit -m "feat(control-plane): add ledger-bound queue projection"
```

---

## Task 3: Serialize Comparison, Append, and Fencing in the Execution Layer

**Files:**

- Create: `runtime/control_plane/coordinator.py`
- Test: `tests/runtime/control_plane/test_coordinator.py`
- Modify: `kernel/ledger_sqlite.py`
- Modify: `tests/kernel/test_ledger_sqlite.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class CommitReceipt:
    request_id: str
    transaction_key: str
    ledger_seq: int
    ledger_head: str
    projected_digest: str
    fencing_token: int

class StaleComparison(RuntimeError): ...
class StaleFence(RuntimeError): ...

class TransactionCoordinator:
    def prepare(self, record: TransactionRecord, *, expected_ledger_head: str) -> CommitReceipt: ...
    def apply(self, command: TransactionCommand, *, expected_ledger_head: str) -> CommitReceipt: ...
    def recover_projection(self) -> str: ...
```

- [ ] **Step 3.1: Write RED contention tests**

Use independent SQLite connections and processes. Two claimants start from the same projected
digest: exactly one may append `CLAIM`; the other receives `StaleComparison` or `StaleFence` and
does not create a ledger row. Cover stale owner after handoff, old process waking after a newer
fence, and a crash immediately before and after append.

- [ ] **Step 3.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_coordinator.py \
  tests/kernel/test_ledger_sqlite.py
```

Expected: new coordinator tests fail because comparison/fencing is absent; existing ledger tests
remain green.

- [ ] **Step 3.3: Implement the coordinator without a second writer**

The coordinator owns the sole `Ledger`. Within one serialized commit section it:

1. verifies the chain and exact expected head;
2. derives current transaction state from ledger rows;
3. checks expected digest and strictly newer fence;
4. builds and appends one canonical event;
5. fsyncs through the ledger backend;
6. applies the committed row to the projection, rebuilding on mismatch;
7. returns a receipt from committed bytes.

Do not let adapter/watchdog processes instantiate competing `Ledger` writers. They submit typed
commands to this coordinator seam.

- [ ] **Step 3.4: Run GREEN repeatedly for concurrency only**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_coordinator.py \
  tests/kernel/test_ledger_sqlite.py
```

Expected: all pass. A repeat loop is authorized here only for the passing race/property test and
must use generated distinct transaction IDs; it must not repeat a failed external action.

- [ ] **Step 3.5: Commit**

```bash
git add runtime/control_plane/coordinator.py kernel/ledger_sqlite.py \
  tests/runtime/control_plane/test_coordinator.py tests/kernel/test_ledger_sqlite.py
git commit -m "feat(control-plane): fence canonical transaction commits"
```

---

## Task 4: Bind Idempotency and Side-Effect Certainty to Transactions

**Files:**

- Modify: `runtime/control_plane/events.py`
- Modify: `runtime/control_plane/coordinator.py`
- Modify: `runtime/integrations/bridge_protocol.py`
- Test: `tests/runtime/control_plane/test_side_effect_recovery.py`

**Interfaces:**

```python
def idempotency_key(*, transaction_key: str, operation: str, payload_hash: str) -> str: ...

class SideEffectCertainty(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    REJECTED_BEFORE_ACCEPTANCE = "REJECTED_BEFORE_ACCEPTANCE"
    ACCEPTED = "ACCEPTED"
    UNCERTAIN = "UNCERTAIN"
```

- [ ] **Step 4.1: Write RED crash-boundary tests**

Inject crashes before dispatch, after dispatch attempt, after transport acceptance, after response
bytes persist, and after response event commit. Assert only proven pre-acceptance failures are
retry-eligible. An accepted-but-uncorrelated attempt must reduce to
`RECONCILIATION_REQUIRED`; the same idempotency key cannot be dispatched again.

- [ ] **Step 4.2: Run RED once**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_side_effect_recovery.py
```

Expected: fails because certainty and idempotency policy are absent.

- [ ] **Step 4.3: Implement event-only dispatch evidence**

Persist immutable request bytes before the dispatch-attempt event. Record attempted, accepted,
response-bytes-persisted, and response-verified facts as ledger event payload fields/evidence;
never introduce states for them. Map uncertainty through existing `SIDE_EFFECT_UNCERTAIN`.

- [ ] **Step 4.4: Run GREEN and the bridge protocol suite**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q \
  tests/runtime/control_plane/test_side_effect_recovery.py \
  tests/chatgpt_bridge/test_semantic_identity.py
```

Expected: all pass; no ambiguous attempt is replayed.

- [ ] **Step 4.5: Commit**

```bash
git add runtime/control_plane runtime/integrations/bridge_protocol.py \
  tests/runtime/control_plane/test_side_effect_recovery.py
git commit -m "feat(control-plane): preserve side-effect certainty"
```

---

## Task 5: Independent Verification and Lifecycle Records

**Files:**

- Modify: `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`
- Create: `reviews/tasks/PAEOS_TRANSACTION_FENCING_PROJECTION_review.md`
- Modify: `MessyChangesNeedsReview.md` only if unresolved debt remains

- [ ] **Step 5.1: Run focused and full applicable gates fresh**

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q tests/runtime/control_plane \
  tests/chatgpt_bridge/test_semantic_identity.py tests/kernel/test_ledger.py \
  tests/kernel/test_ledger_sqlite.py
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check runtime/control_plane \
  runtime/integrations/bridge_protocol.py kernel/ledger_sqlite.py tests/runtime/control_plane
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright runtime/control_plane
git diff --check
```

Expected: focused tests and new-code static checks pass. Record full-suite/static failures exactly;
do not conceal inherited debt.

- [ ] **Step 5.2: Run discriminative mutations**

One at a time, prove tests kill: fence comparison `<=` changed to `<`, projection head validation
removed, event appended after projection, uncertain side effect made retryable, and a terminal
state allowed to transition. Restore each mutation before the next.

- [ ] **Step 5.3: Obtain physically decorrelated L14 audit**

Give the auditor only the sealed candidate/evidence bundle. Prove its physical family differs
from every builder receipt. Missing provenance is REMANDED.

- [ ] **Step 5.4: Record L17 and stop at Gate B**

Record exact Sealed/Remanded/Remediated counts, residual risks, and all L18/L19/debt routes. This
plan does not authorize a live production dispatch.

- [ ] **Step 5.5: Commit review records**

```bash
git add PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md MessyChangesNeedsReview.md \
  reviews/tasks/PAEOS_TRANSACTION_FENCING_PROJECTION_review.md
git commit -m "docs(review): record transaction fencing disposition"
```
