# PAEOS AI-Supervised Operational Autonomy Design

- **Status:** Founder-approved in-chat design; adversarial revision 2 awaiting final Founder review
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
mechanism that executes and supervises that lifecycle. It also does not create a second kernel,
ledger, capability system, or worker contract: it composes the existing PAEOS execution
architecture and runtime interface contracts into an operational control plane.

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
existing recovery specification and the staged acceptance process in this document. Automatic
promotion cannot bootstrap its own authority: the first integration that installs this control
plane requires a separate Founder-ratified L16 disposition. Only later eligible work may use the
standing automatic-promotion envelope.

## 3. Constitutional and Operational Invariants

The implementation must preserve these invariants:

- `operations/ENGINEERING_LIFECYCLE.md` remains the canonical L01-L19 authority.
- The Founder remains the sole constitutional ratifier.
- Models are stateless compute; PAEOS owns local canonical state.
- The kernel's append-only, hash-chained, single-writer ledger remains the only canonical source
  for lifecycle and promotion state. A control-plane queue is a verified operational projection,
  never a parallel authority.
- PAEOS is the sole authority for routing, retries, cooldowns, fallbacks, and lifecycle progress.
- LiteLLM is transport only.
- Cline is implementation-only and cannot ratify, audit itself, or promote its work.
- Existing `TaskPackage` and `CapabilityToken` contracts remain the only worker authority objects.
- Physical `Builder != Auditor` is enforced before dispatch and verified again from receipts.
- Unknown or conflicting physical model identity fails closed.
- The eleven existing circuit breakers halt the exact transaction and preserve raw evidence.
- Z0 canaries, protected-path classification, and promotion law are not writable by hosted models.
- Repository, research, provider, and browser content is provenance-tagged untrusted data and may
  never become control instructions merely because it appears in a prompt.
- No artifact moves from intake directly to implementation.
- Passing tests alone does not prove lifecycle conformance or safe autonomy.
- Remands are healthy back-pressure; the system never optimizes for zero remands.

### 3.1 CER-6 Derivation Register

The design introduces no free-standing constitutional concepts:

- provider-neutral supervisors derive from the hosted-intelligence boundary in
  `spec/PAEOS-9-execution-architecture.md` and the session-continuity invariant;
- local canonical state and policy-owned routing derive from the inference-mesh specification;
- scoped worker execution derives from `TaskPackage`, `CapabilityToken`, SI-1, A-6, and L12;
- immutable context packages derive from `RuntimeContext` and the Task Package Compiler;
- fencing and expected-prior comparison repay the concrete DEBT-0059 last-writer-wins race while
  preserving the ledger single-writer invariant;
- prompt/data separation derives from threat-model T9;
- rotating canaries and categorical quarantine derive from threat-model T8;
- physically decorrelated audit derives from A-08 and L14;
- policy-gated repository integration derives from L16 and the single-threaded integration rule;
- the headless adapter is a remediation of the observed browser, clipboard, screen-lock, and
  repeated-dispatch scars, not a new source of authority.

If implementation cannot derive a required interface from these artifacts, it must halt and file
an Improvement Proposal rather than extending this document by implication.

## 4. Control-Plane Architecture

The kernel ledger is the canonical source of lifecycle truth. Immutable envelopes and traces live
in CAS; a local control-plane projection provides queue and lease queries and is accepted only
when its recorded ledger head verifies. No model conversation, browser tab, terminal, Cline
process, PID file, projection row, or log line may substitute for a committed ledger event.

The operational flow is:

1. PAEOS accepts an objective and advances the canonical L01-L19 lifecycle.
2. The model router selects an admitted architect-grade supervisor adapter.
3. The supervisor produces bounded architectural artifacts. L09/L10 must challenge a Trace-B
   design before L11 can freeze implementation scope.
4. The worker-admission broker launches Cline with explicit identity, scope, capabilities,
   budgets, worktree, and lease.
5. Cline implements only the L11 contract in an isolated sandbox or worktree.
6. Deterministic verification independently reproduces acceptance evidence.
7. A physically decorrelated model performs L14 independent audit.
8. The promotion controller evaluates the complete policy gate.
9. L17-L19 record lessons, debt, incidents, reusable knowledge, and amendment candidates.

The supervisor may request actions but cannot mutate canonical or transaction state directly. The
deterministic coordinator is an implementation of the existing Execution Layer reference monitor,
not an additional authority. It evaluates claim arbitration, fencing, retry eligibility, adapter
activation, and promotion preconditions; only the kernel's single-writer path commits events.

## 5. Durable Transaction Model

The reviewed recovery reducer remains the transaction state machine:

```text
NEW -> PREPARED -> CLAIMED -> RESPONDED -> CONSUMED
 |         |           |          |
 +---------+-----------+----------+-> RECONCILIATION_REQUIRED
 +---------+-----------+----------+-> QUARANTINED
```

These are control-plane transaction states, not additional engineering-lifecycle layers.
`CONTINUE`, `REMAND`, `HALT`, and `NEEDS_FOUNDER` remain correlated response dispositions, not
transaction states. Dispatch-attempted, dispatch-accepted, response-recorded, and
response-verified facts are immutable journal/evidence events. They do not justify expanding the
reducer or reinterpreting historical records.

Each transition uses an expected-prior digest plus a monotonic fencing token under a
cross-process lock. A stale Codex, Antigravity, browser, watchdog, or worker process cannot commit
after its lease has been replaced.

Transaction persistence is crash-consistent by construction:

1. immutable request/response bytes are content-addressed and durably persisted before reference;
2. the kernel appends the corresponding transaction event through its single-writer ledger path;
3. the queue projection records the ledger head from which it was derived;
4. a crash between append and projection update causes projection rebuild, not a second dispatch;
5. a projection whose head or hash does not verify is unusable for claims or gates.

Authority uses logical ledger sequence and fencing generation, never PID existence or wall-clock
ordering. Wall time controls liveness only. PID files, JSON status files, and logs are diagnostic.
The active implementation may use SQLite WAL for atomic local claim comparison, but it may not
introduce a second event history or a dual-write success condition.

Every external dispatch carries a stable idempotency key. The system provides at-most-once
dispatch when tracked state is unambiguous. If a crash occurs after a possible external side
effect but before a correlated response is committed, the transaction becomes
`RECONCILIATION_REQUIRED`; it is never automatically replayed.

## 6. Supervisor Admission and Failover

Supervisor authority is earned by a versioned, task-class-scoped admission profile, not a product
name. Admission separately records protocol compliance and reasoning capability; success at code
triage does not imply eligibility for architecture, security, or constitutional analysis. The
suite tests:

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

An alias or opaque router that cannot prove its actual upstream model lineage is
`UNVERIFIED_PHYSICAL_IDENTITY`. It is ineligible for Builder, L10 adversary, and L14 auditor roles
that require family separation. A browser adapter is eligible only if it can meet the same
identity and correlation contract; otherwise it remains a non-authoritative compatibility tool.

Capability tiers are:

- **Architect grade:** may supervise Trace-A and Trace-B work inside the standing envelope.
- **Degraded supervisor:** may supervise only pre-authorized Trace-A work.
- **Worker only:** may implement bounded contracts but cannot supervise.
- **Quarantined:** receives no work until a new versioned admission succeeds.

Admission uses versioned holdout and rotating canaries stored in Z0 so a public fixed probe cannot
be memorized. Eligibility expires on any binary, adapter, prompt, provider-policy, model, or
sandbox-profile change and on a fixed thirty-day maximum TTL. Continuous canary sampling detects
silent server-side model drift. A critical miss quarantines immediately; benign task failure may
remand work without implying a security violation.

Selection considers privacy eligibility, capability tier, health, quota, latency, and the
availability of a physically decorrelated auditor. PAEOS owns fallback. Providers and LiteLLM do
not hide retries or sub-routing.

A clean Codex-to-Antigravity rotation occurs only at a committed checkpoint with no transferable
active claim. The incoming adapter verifies the checkpoint chain, repository digest, policy
version, transaction digests, and governance hashes before it can claim work. An ambiguous
in-flight transaction remains isolated while unrelated work may continue.

A degraded supervisor may process only tasks whose Trace-A classification was already committed
by an eligible L02 path. It cannot create, lower, or reinterpret ceremony depth. Supervisor
responses commit only after complete schema validation; partial streams and prose outside the
response envelope are quarantined as evidence, not executed.

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

Secret scanning is additive, not the trust boundary. Denied paths and file classes are enforced
before content inspection; uncertain classification defaults to the more restrictive class. Every
egress request contains a content-addressed manifest of the exact bytes sent. Provider privacy
records expire after seven days or on announced policy change; stale policy makes the provider
ineligible rather than assumed safe.

All imported content is tagged with origin, trust class, and instruction status. Repository text,
research pages, dependency metadata, provider output, and browser history are data. Structured
parsers reject attempts to turn embedded text into tool calls, policy changes, or shell arguments.
Admission and canary suites include prompt-injection and confused-deputy probes.

## 8. Worker Admission and Per-Task Authorization

Worker safety has two separate gates.

### 8.1 Route admission

Admission qualifies this full tuple and capability profile:

```text
provider + physical model lineage + Cline binary hash + adapter version + policy version
+ sandbox profile + task class + language/tool capability
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

No new `Worker Contract` authority object is created. The frozen L11 contract and deterministic
`RuntimeContext` are compiled into the existing kernel-minted `TaskPackage` and
`CapabilityToken`. Recovery-specific transport fields are an envelope around that package; they
cannot grant an operation absent from the token. The package contains:

- transaction, goal, run, stage, and L11 contract identifiers;
- exact base commit and isolated worktree or sandbox;
- provider, model, adapter, policy, and sandbox bindings;
- immutable context package and approved dependency closure;
- allowed read and write paths;
- typed tool capabilities and limits;
- network/data-class capability;
- time, token, command, tool-call, and process budgets;
- required artifacts, acceptance commands, rollback instructions, and forbidden actions.

The deterministic Context and Task Package Compilers prepare the immutable context package; the
supervisor proposes its content but is not the authority that mints it. Workers therefore do not
need unrestricted repository search. Missing context produces a structured
`SCOPE_CHANGE_REQUEST`. If it fits the existing L11 contract, a revision is recompiled and
re-hashed; architectural expansion returns through the appropriate lifecycle gates.

Raw shell is denied by default. The broker exposes typed operations such as scoped file reads,
patch application, and test execution, then constructs safe commands itself. OS-level sandboxing
and the capability broker prevent violations before execution. Process monitoring is a final
detector, not the primary boundary.

The sandbox mechanically enforces CPU, memory, process-count, open-file, disk, wall-clock, and
network budgets. Tool and CLI binaries are path-pinned and hash-bound to the admission profile.
Builder-visible source and documentation remains provenance-tagged data; embedded instructions
cannot grant a capability or alter the TaskPackage.

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

A halted, quarantined, or Founder-gated transaction does not globally block unrelated goals unless
the ledger, kernel, signing domain, or shared projection integrity is in question. Logs, traces,
CAS objects, and projection data have explicit retention and disk quotas; storage exhaustion
applies back-pressure and halts new dispatch before forensic evidence is discarded.

Headless adapters remove display-lock dependence. `caffeinate` and the browser monitor remain
compatibility aids only. Browser input and output must carry a transaction nonce and correlation
hash; nothing is pasted into an unbound terminal.

## 10. Retry and Failure Policy

Retries are classified by side-effect certainty:

- A pre-dispatch transient transport error may receive the router's one policy-authorized retry
  with a new attempt record and documented rationale.
- A deterministic bad request, auth failure, scope violation, provenance conflict, or circuit
  breaker is not retried.
- A rate limit follows the router's single-retry-with-jitter policy only when the transport proves
  the request was not accepted. A lost response after request acceptance is ambiguous and enters
  reconciliation rather than retry.
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
7. One-time Founder L16 integration of the independently proven control plane.
8. One later reversible Trace-A automatic promotion as a post-installation canary.
9. Broader policy-gated operation after the previous stages remain healthy.

Broader activation requires, at minimum:

- three successful disposable live probes for every admitted route, each in a fresh session;
- three end-to-end Trace-A canaries in isolated worktrees;
- one clean Codex/Antigravity checkpoint rotation and one forced quota-stop simulation;
- five reversible Trace-A automatic promotions at concurrency one after bootstrap integration;
- zero critical capability escapes, duplicate side effects, provenance conflicts, missed Z0
  canaries, or unsafe replays during that window.

Correct Court remands do not reset the window. A critical boundary failure quarantines the exact
route/configuration and prevents broader activation until a new admission and canary window pass.

Fault injection covers falsified provenance, stale and competing claims, symlink and scope
escapes, duplicate responses, quota loss in every transaction state, hung reasoning and tools,
vacuous tests, baseline contamination, homogeneous audit, misleading completion claims, and
crashes immediately before and after possible side effects. It also covers prompt injection,
opaque model aliases, provider-policy expiry, resource exhaustion, stale target-branch heads,
projection poisoning, ledger/projection crash gaps, and partial supervisor responses.

Workers see acceptance criteria but not every seeded mutation or hidden falsifier. Court evidence
must be discriminative: the relevant test fails against the baseline condition and passes against
the candidate for the intended reason.

The proof environment separates three immutable views: baseline, candidate, and verifier. Test
definitions, canaries, injected-mutation manifests, toolchain/dependency hashes, and expected
failure reasons are unavailable for builder modification unless L11 explicitly authorizes a test
change. Such a test change receives an independent test-design audit. Every seeded mutation must
prove it was installed, reached, and killed; an unexecuted mutation is not a passing canary.

Before the first live remote probe, the Founder/operator must rotate or refresh the credential
exposed during recovery and revoke the old material. This is a one-time bootstrap prerequisite,
not a responsibility delegated to the autonomous system.

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

The promotion controller receives a single-use capability bound to the exact reviewed commit,
expected target-branch head, repository, disposition, and expiry. It can update only that ref; it
cannot edit files, rebase, resolve conflicts, push unrelated refs, or change its own classification.
If the target head changes after verification, evidence is stale and the candidate returns for
integration-aware verification. It is never autonomously rebased and promoted on old evidence.

This automatic envelope covers repository integration only. Deployments, database migrations,
financial actions, credential changes, external messages, and other non-repository side effects
require separate lifecycle designs and standing authorization.

Kernel, lifecycle, authority, credential, signing-domain, and other constitutionally protected
changes always stop for Founder ratification. A task cannot relabel itself to escape this gate.
Change classification is the existing conservative kernel blast-radius function, not a supervisor
or worker assertion.

If the post-promotion health check fails and no later integration depends on the merge, the
controller reverts that exact merge, records an incident, and quarantines the responsible route.
If a safe mechanical revert is not provable, the system halts rather than improvising.

After the L16 disposition, the task must complete the mandatory L17 Constitutional Review and
route every lesson into its required L18/L19, Proposal, Debt, or discard-with-reason outcome. The
promotion transaction is not reported as a completed engineering task until that review commits.

## 13. Empirical Acceptance Criteria

The system may leave `SUPERVISED_RECOVERY_ONLY` only when all applicable criteria hold:

- the exposed Cline credential is rotated/refreshed and the old material revoked;
- inherited repository-wide static gates are green, or an exact Founder-ratified debt-baseline
  policy defines which unchanged findings may coexist with promotion;
- the control-plane projection rebuilds from the canonical ledger and matches its head;
- the minimum route, end-to-end, handoff, and single-flight promotion window in section 11 passes;
- every seeded invalid action is rejected for the intended reason;
- valid canaries complete without manual intervention;
- no external side effect is duplicated;
- every remote model action has an attributable physical receipt;
- every L14 pass proves physical builder/auditor family inequality;
- no opaque route or stale provider-policy record participates in a protected role;
- prompt-injection, confused-deputy, resource-exhaustion, and stale-head canaries are killed;
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
2. Repay DEBT-0059 with ledger-derived projections, cross-process comparison, and fencing tokens.
3. Implement provider-neutral headless supervisor adapters and durable checkpoints.
4. Compile production authorization through existing `TaskPackage`/`CapabilityToken` contracts,
   typed operations, provenance-tagged context, and OS sandboxing.
5. Replace liveness-by-process with event/deadline watchdogs and safe recovery rules.
6. Rotate the exposed credential, then run the fault-injection and canary ladder without promotion.
7. Resolve inherited Ruff/Pyright gates or obtain an exact Founder-ratified debt-baseline policy.
8. Obtain the one-time Founder L16 disposition that integrates the proven control plane.
9. Enable one later reversible Trace-A policy-gated promotion under the standing envelope.
10. Independently revalidate operational L01-L19 execution before autonomous SAKG work resumes.

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
- authorize deployments, migrations, financial actions, credential rotation, or external messages;
- resume SAKG development before the control plane is independently proven.

## 16. Residual Risks and Honest Limits

This design is not a seal and cannot prove itself complete. Its irreducible or only partially
mitigated risks are:

- a compromised or incorrect kernel defeats the reference monitor and ledger guarantees;
- a provider can misreport model lineage unless a directly bound endpoint supplies independently
  checkable identity, so opaque routing remains ineligible rather than solved;
- model-family inequality does not prove cognitive independence when providers share weights,
  training data, or serving infrastructure;
- canaries cover known failure classes and may miss novel hallucination or collusion behavior;
- secret scanners and prompt-injection classifiers have false negatives, which is why path,
  capability, provenance, and data-class gates remain primary;
- local host compromise, malicious privileged software, hardware failure, and unavailable remote
  providers are outside the guarantees of the model-control plane;
- operationally human-free does not mean constitutionally human-free: protected changes,
  quarantine release, bootstrap integration, and credential incidents may wait indefinitely for
  the Founder rather than fail open.

These limits are acceptance constraints, not deferred promises. A future attempt to relax one
must enter L19 or create an Improvement Proposal as required by its constitutional impact.
