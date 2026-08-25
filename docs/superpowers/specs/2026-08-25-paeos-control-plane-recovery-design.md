# PAEOS Temporary Overseer Control-Plane Recovery Design

- **Status:** Founder-approved written specification; implementation remains gated by the
  subproject plan and per-task Overseer review
- **Classification:** `OPERATIONAL_RECOVERY_ONLY`
- **Recovery branch:** `codex/control-plane-recovery-spec`
- **Baseline commit:** `af83198192aef72e1ef88615e4ca586a449acb71`
- **Founder approval:** 2026-08-25, Europe/London

## 1. Purpose

Restore a fail-closed control plane while Codex GPT-5.6 Sol temporarily assumes the
Architect/Overseer role from Antigravity. Cline remains implementation-only. The recovery must
remove the Chrome, clipboard, screen-lock, and unbound-terminal dependencies from the control
path without changing the founder-ratified 19-layer engineering lifecycle.

This is not a claim that PAEOS is R4-conformant, that SoftLoop implements all nineteen layers, or
that historical seals are valid. The current recovery frontier remains:

- Sealed: 0
- Remanded: 1
- Remediated: 0

The historical ledger contains 25 `SealCommitted` rows. Existing forensic evidence classifies 24
as vacuous or contaminated and one as bound to a substantive artifact. Those rows are preserved;
the recovery does not reinterpret or delete them.

## 2. Authority and Role Boundaries

The recovery is subordinate to these sources, in this order:

1. `operations/ENGINEERING_LIFECYCLE.md` — canonical L01-L19 authority.
2. Founder-ratified constitutional amendments and constitutional execution rules.
3. `docs/PAEOS_MODEL_ROUTER_INFERENCE_MESH_SPEC.md` — inference-mesh requirements, subject to the
   open conformance findings recorded in DEBT-0051 through DEBT-0056.
4. `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` — forensic findings and unresolved anomalies, not a
   source of constitutional authority.

Role invariants:

- The Founder is the only constitutional ratifier.
- Codex GPT-5.6 Sol may specify, supervise, remand, and report; it may not self-ratify.
- Cline `paeos-code` is an implementation worker. It may not ratify, promote, or adjudicate its
  own output.
- The physical auditor model family must differ from the physical builder model family.
- Unknown physical model identity fails closed.
- No recovery commit is promoted to `main` or `trunk` by this workflow.

## 3. Observed Failure Baseline

The design addresses the following reproduced failures.

### 3.1 Bridge process and supervision failure

- The bridge PID file, transaction state, and bridge log stopped changing on 2026-08-21.
- No `monitor_loop.py` or PAEOS watchdog process is running.
- There is no user crontab entry and no registered launchd bridge/watchdog service.
- Outbound transaction sequence 81 remains `SUBMITTED`, while inbound state still refers to
  delivered sequence 80. Sequence 81 is stale and must not be resumed automatically.

### 3.2 Repeated-dispatch circuit-breaker failure

The bridge issued 34 consecutive dispatch attempts, sequences 46 through 79, for the same logical
transaction after `AppleScriptChromeBridge` raised a missing-method exception. The broad loop
exception handler slept and continued without transitioning to a terminal failure state. This
violated circuit breakers 6 and 7 and made an external side effect repeatable after uncertainty.

The later uncommitted AppleScript acknowledgement is also fail-open: it accepts any non-empty user
history and returns success on exceptions. Therefore sequence 80's "verified" acknowledgement and
sequence 81's `SUBMITTED` state are not probative.

### 3.3 Production/test state contamination

`ChatBridgeRuntime` resolves `.paeos_state/bridge` relative to the current working directory.
`test_bridge_adversarial_review_requires_real_orchestrator_output` explicitly changes into the
repository root, deletes the live bridge prompt/output, and writes the `g-test` / `r-5678` fixture
there. A full 530-test run passed but replaced the production prompt with this fixture. Passing
assertions therefore do not prove safe test isolation.

### 3.4 Committed/uncommitted split-brain baseline

A clean worktree at `af83198` cannot collect the full suite:

```text
ImportError: cannot import name 'IDENTITY_VERSION'
from 'ops.chatgpt_bridge.monitor_loop'
```

The committed semantic-identity tests depend on identifiers present only in the uncommitted
1,130-line monitor rewrite in the main checkout. The recovery must reconcile the implementation,
tests, design document, and transaction schema as a single reviewed change; it must not copy the
dirty rewrite wholesale.

### 3.5 Worker and provenance failure

The most recent recovery run, `r-5485b72c`, produced no artifact, no Court evidence, and no seal.
Laguna violated the command boundary, Minimax lacked usable entitlement, Gemini lost required
tool-call history metadata, and Llama emitted textual imitations of tools. Router availability is
not equivalent to worker eligibility. No raw provider receipts currently prove a valid
Builder/Auditor pairing.

## 4. Recovery Decomposition

The recovery is implemented as four independently reviewable subprojects. Failure in any
subproject blocks the next one.

1. **State isolation and transaction safety foundation.** Make state roots injectable, introduce
   an explicit fail-closed transaction reducer, and prevent test writes to production state.
2. **Codex overseer request/response adapter.** Replace browser copy/paste with an atomic file
   queue consumed by a Codex automation.
3. **Cline worker admission and model provenance.** Admit only workers that demonstrate real tool
   execution, artifact creation, exact-command compliance, and attributable physical identity.
4. **Controlled end-to-end canary.** Exercise the real path through a disposable intake before
   any SAKG work resumes.

Each subproject receives its own implementation plan, failing tests, minimal production change,
verification evidence, and review gate. The first implementation plan covers subproject 1 only.

## 5. Subproject 1 — State Isolation and Transaction Safety

### 5.1 Injected state root

Every bridge component receives an explicit `state_root: Path`. Production entry points resolve it
once from configuration and pass it down. Tests always use `tmp_path`; no test may call
`monkeypatch.chdir(REPO)` to select state.

The bridge adapter derives its files from the injected root:

```text
<state_root>/bridge/requests/
<state_root>/bridge/responses/
<state_root>/bridge/quarantine/
<state_root>/bridge/transactions/
```

Source code and operational scripts remain in the repository. Runtime requests, responses, PID
files, mutable journals, and logs do not.

### 5.2 Immutable envelopes

Each request is an immutable JSON document containing:

- `schema_version`
- `request_id`
- `transaction_key`
- `created_at`
- `expires_at`
- `goal_id`
- `run_id`
- `stage_id`
- `role`
- `workspace_root`
- `worker_transport_id`
- `worker_session_id`
- `worker_pid`
- `worker_tty`
- `worker_model_provider`
- `worker_model_id`
- `worker_model_family`
- `semantic_hash`
- `evidence_manifest_hash`
- `payload_hash`
- `allowed_dispositions`

`worker_tty` is a string for a terminal-backed invocation and JSON `null` only when the named
transport declares itself headless. A headless transport must still supply an exact transport ID,
session ID, and process ID; `null` is not permission to resolve an arbitrary terminal later.

Each response is another immutable JSON document containing the same correlation identifiers plus:

- `overseer_model_provider`
- `overseer_model_id`
- `overseer_model_family`
- `disposition`
- `response_text`
- `response_hash`
- `source_task_id`
- `completed_at`

The allowed overseer dispositions are `CONTINUE`, `REMAND`, `HALT`, and `NEEDS_FOUNDER`. There is
no `RATIFY` disposition.

### 5.3 Transaction reducer

Only a pure reducer may change transaction state. Valid states are:

```text
NEW -> PREPARED -> CLAIMED -> RESPONDED -> CONSUMED
                    |             |
                    +-> RECONCILIATION_REQUIRED
                                  |
                                  +-> QUARANTINED
```

Rules:

- A request envelope is persisted atomically before `PREPARED`.
- `CLAIMED` records the consumer and lease expiry; it is not evidence that an external send
  occurred.
- Any exception after an external side effect but before a verified response transitions to
  `RECONCILIATION_REQUIRED`.
- `RECONCILIATION_REQUIRED` and `QUARANTINED` are terminal for automation. Only a new explicit
  Founder/Overseer recovery action may create a successor transaction.
- The same `transaction_key` may have only one active request.
- Timeouts never trigger an autonomous resend.
- Retry counters are diagnostic only; they do not authorize retries.
- A response is consumable only when request ID, transaction key, run ID, stage ID, payload hash,
  and lease owner all match.
- Unknown state, missing field, malformed JSON, stale lease, expired request, or mismatched hash
  fails closed and preserves the raw envelope in quarantine.

Sequence 81 is imported as `RECONCILIATION_REQUIRED`, never `SUBMITTED` or `CONSUMED`.

### 5.4 Circuit-breaker integration

The reducer emits one structured incident for each of the eleven existing circuit breakers. The
outer loop stops processing that transaction immediately. It does not sleep and continue. Raw
exception text, transaction state, request envelope hash, and last confirmed side effect are
preserved before the halt.

## 6. Subproject 2 — Codex Overseer Adapter

The temporary adapter replaces Chrome and Terminal automation; it does not wrap them. Execution
and oversight remain separate planes:

Data flow:

```text
Execution: PAEOS runtime -> bound Cline worker -> artifact/evidence -> PAEOS runtime
Oversight: PAEOS runtime/worker event -> immutable request -> Codex automation
           -> immutable response -> PAEOS runtime
```

The Codex automation:

1. Runs every two minutes, distinct from the fixed 60-minute forensic audit. If the automation
   backend cannot guarantee that fixed interval, subproject 2 stops for a Founder decision; it
   does not fall back to GUI automation.
2. Ingests the notebook, inference-mesh spec, and canonical lifecycle before claiming work.
3. Claims at most one unexpired request whose workspace and role bindings are exact.
4. Reviews the worker output and evidence without editing implementation files.
5. Writes one correlated response atomically.
6. Leaves remands as healthy back-pressure and reports exact counts.
7. Refuses constitutional ratification, main/trunk promotion, unbound requests, and unknown model
   provenance.

If the Codex task surface cannot expose a raw provider/model-family receipt, Codex may continue as
Architect/Overseer but its response cannot serve as L14 decorrelated-audit proof. The request is
then remanded for an independently attributable auditor; a task label or configured model name is
not substituted for physical provenance.

The existing hourly `paeos-temporary-overseer` automation remains read-only and independent. A
failure of the transaction adapter cannot disable or alter the hourly audit.

The old `monitor_loop.py`, clipboard hashes, Chrome JavaScript, screen-lock probing, and terminal
keystroke delivery are retired from the active path. They remain available as forensic history
until the Founder authorizes archival.

## 7. Subproject 3 — Cline Worker Admission and Provenance

Cline is invoked through a configured, non-interactive worker transport, not an arbitrary visible
terminal. The transport must bind one invocation to one task, one sandbox, and one physical model
receipt.

Admission requires all of the following in a disposable probe:

- The worker executes one exact allowed command without expansion.
- The worker performs a real file edit inside the supplied sandbox.
- The artifact exists, is non-empty, and is not junk metadata.
- The discriminative verification command runs and records its real exit code.
- The terminal result record identifies provider, model ID, and physical model family.
- The observed family matches the provider receipt.
- No unconfigured tool or subagent is invoked.

An exit-zero transcript without a write is failure. Text that resembles tool JSON is not tool
execution. Catalog labels, logical aliases such as `paeos-code`, and provider-health flags are not
physical provenance.

For audit work, the router checks `Builder != Auditor` twice:

1. Before dispatch, using explicit known builder family and candidate auditor family.
2. After dispatch, using the physical `actual_family` receipt returned by the provider.

Missing, unknown, or same-family identity is a remand and may not be returned as a successful
audit response. Each fallback is evaluated independently after its actual dispatch.

## 8. Subproject 4 — Controlled Canary

The first live run after recovery is a disposable, reversible intake unrelated to SAKG. It must
produce a small non-junk artifact and a verification command that fails on a seeded mutation and
passes on the candidate.

The canary must demonstrate:

1. Exactly one request for one worker event.
2. No browser, clipboard, UI, or unlocked-display dependency.
3. Exact request/response correlation.
4. One admitted Cline implementation worker with a raw physical model receipt.
5. One decorrelated audit model with a raw physical model receipt.
6. Real Court reproduction of the submitted verification command.
7. Correct acceptance of valid evidence or correct remand of invalid evidence.
8. Exact `Sealed | Remanded | Remediated` reporting.

SAKG remains paused until this canary completes and the Founder accepts the evidence. A remand is a
valid canary outcome when it correctly rejects defective evidence; the acceptance criterion is
correct adjudication, not zero remands.

## 9. Watchdog and Scheduling Policy

The watchdog becomes observer-only. It may read process state, queue age, transaction state,
provider health, and logs. It may emit a diagnostic incident. It may not:

- restart or kill a process;
- launch Chrome;
- paste, type, or nudge;
- change transaction state;
- retry a request;
- alter model routing;
- claim that a failed intervention was healed.

Process restart policy belongs to an explicitly configured single-instance service. Service health
does not authorize transaction replay. On restart, active `CLAIMED` transactions enter
`RECONCILIATION_REQUIRED` unless a fully correlated immutable response already exists.

## 10. Required Verification

Subproject 1 is not complete until fresh evidence proves all of the following:

- Running the full test suite in an isolated worktree leaves every production `.paeos_state` hash
  unchanged.
- Test bridge state exists only under `tmp_path` and is cleaned by the test fixture.
- A duplicate logical event produces zero additional external sends.
- An exception after a simulated send produces `RECONCILIATION_REQUIRED` and zero retries.
- Missing or malformed acknowledgement fails closed.
- An unbound or ambiguous worker session produces zero delivery attempts.
- A stale or mismatched response is quarantined and never consumed.
- Watchdog tests prove that all mutation functions are unreachable.
- Clean checkout test collection succeeds without relying on uncommitted files.
- The focused tests pass, the full suite passes, and a mutation of each new safety check causes its
  corresponding test to fail.

The verifier records commands, exit codes, stdout/stderr hashes, environment identity, git commit,
and before/after production-state hashes. A bare "tests pass" statement is not evidence.

## 11. Promotion and Rollback

All recovery work remains on `codex/*` recovery branches and isolated worktrees. The workflow does
not merge, rebase, push, open a pull request, or promote to `main`/`trunk` without a new Founder
instruction.

Rollback is branch abandonment plus service disablement. Runtime state is never rolled back by
deleting evidence. Failed or superseded envelopes are quarantined and retained with hashes.

## 12. Non-Goals

This recovery does not:

- ratify a new lifecycle or amend L01-L19;
- equate SoftLoop with the nineteen-layer lifecycle;
- validate the historical 24 contaminated seals;
- resume the abandoned `r-5485b72c` transaction;
- repair or extend SAKG;
- redesign the full inference mesh beyond the safety changes required by DEBT-0051/0055/0056;
- optimize for zero remands;
- authorize Codex or Cline to self-ratify;
- promote any change to main or trunk.

## 13. Review Gates

1. Founder reviewed and approved this written specification on 2026-08-25.
2. Architect writes the implementation plan for subproject 1 only.
3. Cline implements the plan in an isolated recovery worktree using test-first steps.
4. Codex independently reviews the diff and runs fresh verification.
5. Founder decides whether to proceed to subproject 2.

No later gate is implied by approval of an earlier gate.
