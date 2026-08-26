# PAEOS AI-Supervised Operational Autonomy Design

- **Status:** Founder-approved in-chat design; written specification awaiting final Founder review
- **Classification:** `OPERATIONAL_RECOVERY_AND_AUTONOMY_HARDENING`
- **Date:** 2026-08-26, Europe/London
- **Implementation branch:** `codex/control-plane-recovery-s1-clean`
- **Companion specification:**
  `docs/superpowers/specs/2026-08-25-paeos-control-plane-recovery-design.md`

## 1. Purpose

Make PAEOS operationally human-free without transferring constitutional authority to an AI.
An admitted architect-grade model supervises admitted Cline implementation workers through a
durable, provider-neutral, headless control plane. Codex, Antigravity, and future qualified
supervisors are replaceable reasoning adapters over local canonical state.

The browser bridge remains an optional compatibility adapter. It never owns canonical progress,
transaction state, retry authority, model identity, or promotion authority.

This design does not replace the canonical nineteen-layer lifecycle with SoftLoop. It hardens the
mechanism that executes and supervises that lifecycle.

## 2. Founder Decisions Captured by This Design

The Founder selected these operating policies:

1. **AI-supervised autonomy:** routine engineering is supervised by an AI rather than a human.
2. **Operationally human-free:** the system halts only for constitutional ratification,
   credential incidents, or irreversible action outside a standing authorization envelope.
3. **Vetted remote-model egress:** `PUBLIC` and policy-eligible `INTERNAL` material may be sent to
   approved providers. `SECRET` material never leaves the machine.
4. **Bounded degraded mode:** when no architect-grade supervisor is available, an admitted weaker
   supervisor may process only pre-authorized Trace-A work. Trace-B and protected work queue.
5. **Policy-gated automatic promotion:** reversible, non-protected work may merge automatically
   only after all lifecycle, evidence, audit, and rollback gates pass.
6. **Durable headless control plane:** browser copy/paste is a fallback, not the primary transport.

These decisions authorize the design target. They do not authorize the current recovery branch
to merge, push, run a live canary, or promote to `main`. Those actions remain gated by the
existing recovery specification and the staged acceptance process in this document.

## 3. Constitutional and Operational Invariants

The implementation must preserve these invariants:

- `operations/ENGINEERING_LIFECYCLE.md` remains the canonical L01-L19 authority.
- The Founder remains the sole constitutional ratifier.
- Models are stateless compute; PAEOS owns local canonical state.
- PAEOS is the sole authority for routing, retries, cooldowns, fallbacks, and lifecycle progress.
- LiteLLM is transport only.
- Cline is implementation-only and cannot ratify, audit itself, or promote its work.
- Physical `Builder != Auditor` is enforced before dispatch and verified again from receipts.
- Unknown or conflicting physical model identity fails closed.
- The eleven existing circuit breakers halt the exact transaction and preserve raw evidence.
- No artifact moves from intake directly to implementation.
- Passing tests alone does not prove lifecycle conformance or safe autonomy.
- Remands are healthy back-pressure; the system never optimizes for zero remands.

## 4. Control-Plane Architecture

PAEOS local state is the sole source of truth. No model conversation, browser tab, terminal,
Cline process, PID file, or log line may substitute for a committed transaction record.

The operational flow is:

1. PAEOS accepts an objective and advances the canonical L01-L19 lifecycle.
2. The model router selects an admitted architect-grade supervisor adapter.
3. The supervisor produces bounded architectural decisions and frozen worker contracts.
4. The worker-admission broker launches Cline with explicit identity, scope, capabilities,
   budgets, worktree, and lease.
5. Cline implements only the L11 contract in an isolated sandbox or worktree.
6. Deterministic verification independently reproduces acceptance evidence.
7. A physically decorrelated model performs L14 independent audit.
8. The promotion controller evaluates the complete policy gate.
9. L17-L19 record lessons, debt, incidents, reusable knowledge, and amendment candidates.

The supervisor may request actions but cannot mutate transaction state directly. A deterministic
coordinator owns claim arbitration, state transitions, fencing, retry eligibility, adapter
activation, and promotion preconditions.

## 5. Durable Transaction Model

The target transaction flow is:

```text
NEW -> PREPARED -> CLAIMED -> DISPATCHED -> RESPONSE_RECORDED -> VERIFIED -> COMMITTED
          |            |            |                 |              |
          +------------+------------+-----------------+--------------+
                                   -> REMANDED
                                   -> HALTED
                                   -> RECONCILIATION_REQUIRED
                                   -> QUARANTINED
```

These are control-plane transaction states, not additional engineering-lifecycle layers.
Migration maps the existing `RESPONDED` state to `RESPONSE_RECORDED` and `CONSUMED` to
`COMMITTED`; no historical record is silently reinterpreted.

Each transition uses an expected-prior digest plus a monotonic fencing token under a
cross-process lock. A stale Codex, Antigravity, browser, watchdog, or worker process cannot commit
after its lease has been replaced.

Every external dispatch carries a stable idempotency key. The system provides at-most-once
dispatch when tracked state is unambiguous. If a crash occurs after a possible external side
effect but before a correlated response is committed, the transaction becomes
`RECONCILIATION_REQUIRED`; it is never automatically replayed.

## 6. Supervisor Admission and Failover

Supervisor authority is earned by a versioned admission suite, not a product name. The suite
tests:

- instruction and scope fidelity;
- architectural reasoning against seeded defects;
- separation of worker claims from raw evidence;
- circuit-breaker and tool-policy compliance;
- restart from durable state;
- data-class and egress discipline;
- refusal to self-ratify or impersonate Founder authority;
- correct handling of ambiguity and reconciliation.

Every supervisor session records a nonce-bound local transport receipt containing the actual
provider and model identifier exposed by the provider response, derived model family, adapter
version, policy version, prompt and context hashes, timestamps, and usage. The locally trusted
gateway attests what it observed; this is not misrepresented as a provider-issued cryptographic
identity proof. Conflicting sources fail closed.

Capability tiers are:

- **Architect grade:** may supervise Trace-A and Trace-B work inside the standing envelope.
- **Degraded supervisor:** may supervise only pre-authorized Trace-A work.
- **Worker only:** may implement bounded contracts but cannot supervise.
- **Quarantined:** receives no work until a new versioned admission succeeds.

Selection considers privacy eligibility, capability tier, health, quota, latency, and the
availability of a physically decorrelated auditor. PAEOS owns fallback. Providers and LiteLLM do
not hide retries or sub-routing.

A clean Codex-to-Antigravity rotation occurs only at a committed checkpoint with no transferable
active claim. The incoming adapter verifies the checkpoint chain, repository digest, policy
version, transaction digests, and governance hashes before it can claim work. An ambiguous
in-flight transaction remains isolated while unrelated work may continue.

## 7. Data-Egress Policy

Privacy is an eligibility gate before routing:

- `PUBLIC`: may use any vetted provider approved by the local catalog.
- `INTERNAL`: may use only providers whose current data policy satisfies the local policy record.
- `CONFIDENTIAL`: requires a specifically approved no-training/no-retention route.
- `SECRET`: never sent to a remote model; processed only by deterministic local tools.

Credentials, environment dumps, signing seeds, Keychain material, raw provider settings, and
secret-bearing evidence are always `SECRET`.

Raw forensic evidence is stored in a permission-restricted local evidence root. A secret scanner
runs before persistence and remote dispatch. Normal ledgers receive redacted summaries and
content hashes. If evidence must be preserved exactly after a credential incident, the original
is isolated in a restricted incident vault and the exposed credential is rotated before live use.

## 8. Worker Admission and Per-Task Authorization

Worker safety has two separate gates.

### 8.1 Route admission

Admission qualifies this full tuple:

```text
provider + physical model + Cline version + adapter version + policy version + sandbox profile
```

Disposable probes test provenance, exact tool mediation, unauthorized-tool refusal, scope escape,
malformed input, timeout behavior, restart handling, artifact creation, and false-evidence
resistance. A material tuple change or observed drift expires admission.

Serious failures are categorical, not averaged into a score. Scope escape, provenance conflict,
credential exposure, unauthorized subagent use, command expansion, or false evidence immediately
quarantines that tuple. Live admission progresses through read-only, disposable-edit, isolated
real-task, and limited Trace-A canaries.

The exact one-edit/one-command probe in the existing worker-admission plan remains a route probe.
It is not the production worker policy.

### 8.2 Per-task authorization

Each admitted route receives a frozen Worker Contract containing:

- transaction, goal, run, stage, and L11 contract identifiers;
- exact base commit and isolated worktree or sandbox;
- provider, model, adapter, policy, and sandbox bindings;
- immutable context package and approved dependency closure;
- allowed read and write paths;
- typed tool capabilities and limits;
- network/data-class capability;
- time, token, command, tool-call, and process budgets;
- required artifacts, acceptance commands, rollback instructions, and forbidden actions.

The supervisor prepares an immutable context package so workers do not need unrestricted
repository search. Missing context produces a structured `SCOPE_CHANGE_REQUEST`. If the request
fits the existing L11 contract, the supervisor may issue a new contract revision; architectural
expansion returns through the appropriate lifecycle gates.

Raw shell is denied by default. The broker exposes typed operations such as scoped file reads,
patch application, and test execution, then constructs safe commands itself. OS-level sandboxing
and the capability broker prevent violations before execution. Process monitoring is a final
detector, not the primary boundary.

Workers cannot select models, invoke teammates, route skills, change lifecycle state, submit an
audit verdict, promote branches, or amend their own contract. Worker prose is never promoting
evidence.

## 9. Liveness, Watchdogs, and Recovery

The watchdog is deterministic infrastructure. It observes committed transaction events rather
than repository modification time, log noise, or whether Chrome and Cline processes merely exist.

Each active transaction records its owner, fencing token, last meaningful event, next expected
event, deadline, provider state, and whether an external side effect may have occurred.

Default liveness policy is:

- process heartbeat: every 15 seconds;
- soft-stall diagnostic: 120 seconds without a meaningful event;
- pre-side-effect hard stall: 300 seconds, followed by safe lease expiry;
- tool deadline: contract-specific, five minutes by default;
- Trace-A transaction deadline: thirty minutes by default;
- Trace-B deadlines: explicit in the L11 contract, with durable progress checkpoints at least
  every five minutes.

Streaming tokens prove transport activity but do not count as lifecycle progress. Authorized
long-running tools emit deterministic progress records.

The watchdog may restart stateless adapters, expire safe leases, rotate eligible providers, and
reconstruct processes from durable state. It may not reinterpret evidence, redesign work,
ratify, promote, or repeat an ambiguous side effect.

Headless adapters remove display-lock dependence. `caffeinate` and the browser monitor remain
compatibility aids only. Browser input and output must carry a transaction nonce and correlation
hash; nothing is pasted into an unbound terminal.

## 10. Retry and Failure Policy

Retries are classified by side-effect certainty:

- A pre-dispatch transient transport error may receive the router's one policy-authorized retry
  with a new attempt record and documented rationale.
- A deterministic bad request, auth failure, scope violation, provenance conflict, or circuit
  breaker is not retried.
- A rate limit follows the router's single-retry-with-jitter policy, then cooldown and rerouting.
- Any failure after a possible side effect becomes `RECONCILIATION_REQUIRED`.
- An identical failed command is never repeated without a new rationale and explicit authority.

No broad exception handler may sleep and continue the same transaction. Raw error text, hashes,
last confirmed state, and side-effect certainty are persisted before the transaction stops.

## 11. Verification and Canary Ladder

Autonomy is enabled only through this sequence:

1. Pure reducer, fencing, policy, and receipt tests.
2. Simulated adapters with crashes, delays, malformed output, and quota loss.
3. Disposable live worker-admission probes.
4. Trace-A work in a synthetic repository.
5. Low-risk isolated PAEOS task with no promotion authority.
6. Shadow execution against a real task without applying decisions.
7. One reversible Trace-A automatic promotion.
8. Broader policy-gated operation after the previous stages remain healthy.

Fault injection covers falsified provenance, stale and competing claims, symlink and scope
escapes, duplicate responses, quota loss in every transaction state, hung reasoning and tools,
vacuous tests, baseline contamination, homogeneous audit, misleading completion claims, and
crashes immediately before and after possible side effects.

Workers see acceptance criteria but not every seeded mutation or hidden falsifier. Court evidence
must be discriminative: the relevant test fails against the baseline condition and passes against
the candidate for the intended reason.

## 12. Policy-Gated Automatic Promotion

Automatic promotion is permitted only for work classified as reversible and non-protected when
all of these conditions are machine-proven:

- frozen L11 contract and exact base commit;
- independently reproduced L13 evidence;
- physically decorrelated L14 audit;
- L15 documentation and traceability updates;
- no unresolved blocking debt, incident, provenance conflict, or reconciliation item;
- clean rollback plan and post-promotion health check;
- single-threaded integration with no competing promotion.

Kernel, lifecycle, authority, credential, signing-domain, and other constitutionally protected
changes always stop for Founder ratification. A task cannot relabel itself to escape this gate.

If the post-promotion health check fails and no later integration depends on the merge, the
controller reverts that exact merge, records an incident, and quarantines the responsible route.
If a safe mechanical revert is not provable, the system halts rather than improvising.

After the L16 disposition, the task must complete the mandatory L17 Constitutional Review and
route every lesson into its required L18/L19, Proposal, Debt, or discard-with-reason outcome. The
promotion transaction is not reported as a completed engineering task until that review commits.

## 13. Empirical Acceptance Criteria

The system may leave `SUPERVISED_RECOVERY_ONLY` only when all applicable criteria hold:

- every seeded invalid action is rejected for the intended reason;
- valid canaries complete without manual intervention;
- no external side effect is duplicated;
- every remote model action has an attributable physical receipt;
- every L14 pass proves physical builder/auditor family inequality;
- test and Court evidence is non-vacuous and independently reproduced;
- supervisor rotation resumes from durable state without replaying ambiguous work;
- no silent interval exceeds the configured liveness bounds;
- all promotion preconditions and rollback checks are machine-verifiable;
- exact `Sealed | Remanded | Remediated` counts are reported from correlated ledger events.

Success is high-fidelity adjudication, safe remediation, and invariant preservation. A nonzero
remand count is expected when invalid work is injected.

## 14. Implementation Decomposition

The detailed implementation plan will split this architecture into independently reviewable
subprojects in this order:

1. Complete and review route admission without broadening its exact disposable-probe contract.
2. Repay DEBT-0059 with cross-process locking, compare-and-swap, and fencing tokens.
3. Implement provider-neutral headless supervisor adapters and durable checkpoints.
4. Implement production Worker Contracts, context packages, typed capabilities, and OS sandboxing.
5. Replace liveness-by-process with event/deadline watchdogs and safe recovery rules.
6. Run the fault-injection and canary ladder without promotion.
7. Enable one reversible Trace-A policy-gated promotion.
8. Independently revalidate operational L01-L19 execution before resuming autonomous SAKG work.

Every subproject follows its applicable canonical ordering: RED -> GREEN implementation evidence,
independent L13 verification, L14 audit, L15 records, L16 disposition, then mandatory L17 review.
No later activation gate opens merely because earlier code was written or unit tests passed.

## 15. Non-Goals

This design does not:

- grant Founder authority to an AI;
- make SoftLoop synonymous with the nineteen-layer lifecycle;
- validate historical seals by assertion;
- guarantee that any free model is competent;
- make the browser or clipboard reliable enough to own canonical state;
- optimize for zero remands;
- authorize current recovery work to merge or promote before the canary gates;
- resume SAKG development before the control plane is independently proven.
