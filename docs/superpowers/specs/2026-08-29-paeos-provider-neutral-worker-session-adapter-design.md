# PAEOS Provider-Neutral Admission Probe Adapter Design

**Status:** Founder-approved direction; adversarially amended design pending Founder approval
**Date:** 2026-08-29  
**Scope:** Gate A worker admission remediation  
**Branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Implementation baseline:** `bfbbc48e6e9950bcd76f1f2f843f9e29b0acdf42`
**Original design commit:** `40dcb05d076eaf89a12b16662b538b6dcdcd1775`
**Authority:** Founder  
**Architect/Overseer:** Codex GPT-5.6 Sol  
**Implementation role:** replaceable worker only; no self-ratification

## 1. Decision

PAEOS will stop treating the ordinary Cline CLI invocation as the security and admission
boundary. Gate A will add the smallest provider-neutral **admission-probe transport** contract and
implement one qualified Cline Core/Hub transport behind existing PAEOS admission policy. It will
not create a second provider registry, transaction manager, capability system, evidence store, or
production worker contract.

The generalized provider and supervisor registries remain Gate C work. Durable claims, fencing,
and reconciliation remain Gate B work. Production task confinement and typed tool execution remain
Gate D work. Gate A proves only that one exact Cline/runtime/provider/model tuple can perform a
disposable admission probe without hidden capabilities, retries, or identity drift.

The existing `ClineWorkerTransport` CLI path remains quarantined diagnostic compatibility code.
It is not eligible for the production worker pool unless it independently satisfies the same
adapter contract in a future qualification.

### 1.1 Adversarial review disposition

The original direction was correct, but its first draft was too broad for Gate A. It independently
specified registries, durable leases, tool mediation, and evidence publication already owned by
other gates or existing kernel seams. That would have produced parallel authorities and made later
migration harder. This amendment keeps the enforceable Cline Core/Hub boundary while applying the
mandatory reuse rule from the autonomy design: `REUSE_UNCHANGED`, `EXTEND_WRAP`, or
`REPLACE_WITH_MIGRATION_EVIDENCE` for every affected seam.

### 1.2 Normative boundaries

This amendment is subordinate to and must compose with:

- `docs/superpowers/plans/2026-08-26-paeos-cline-worker-admission.md` for Gate A;
- `docs/superpowers/specs/2026-08-26-paeos-ai-supervised-autonomy-design.md`, especially
  sections 4.1, 5, 8, and 10;
- `docs/superpowers/specs/2026-08-28-paeos-gates-b-g-worker-handoff.md` for gate ownership;
- `docs/superpowers/plans/2026-08-26-paeos-transaction-fencing-projection.md` for Gate B;
- `docs/superpowers/plans/2026-08-28-paeos-provider-adapter-registry.md` for Gate C provider
  registration; and
- `docs/superpowers/plans/2026-08-26-paeos-taskpackage-worker-confinement.md` for Gate D.

If this document conflicts with a canonical gate owner, the implementation stops for an explicit
amendment. It does not resolve the conflict by duplicating the owner.

## 2. Motivation and scars

This design is required by observed failures, not architectural preference:

1. Historical Cline workers expanded bounded commands, performed forbidden reads/searches, and
   made false verification claims. This is recorded as `DEBT-0058`.
2. Gate A Task 5 produced evidence-backed worker bindings at commit `07e4264`, but the live route
   still depended on ordinary CLI behavior.
3. Live probe `qwen3-8-admission-01` on Cline `3.0.60` returned `Unauthorized` before tool
   execution even after operator credential rotation. The probe-specific `--data-dir` had no
   usable authenticated state.
4. That Cline session advertised `enable_spawn: true` and `enable_teams: true`, contradicting the
   admission contract.
5. Raw output recorded two identical unrecoverable authorization attempts inside one invocation,
   contradicting PAEOS's sole-retry-authority invariant.
6. The structured result reduced the exact cause to generic `ADMISSION_REJECTED`, forcing an
   auditor to recover `AUTH_FAILED` from raw text.
7. Cline CLI `3.0.60` retained the desktop approval IPC schema but changed other operational
   defaults. IPC compatibility alone is therefore insufficient qualification.

Preserved evidence root:
`/Users/bob/.local/share/paeos/runtime-v2/worker-admission/qwen3-8-admission-01/`.

## 3. Goals

- Prove a narrow adapter contract that Gate C can register without changing PAEOS policy or
  lifecycle code.
- Keep credentials outside worker sandboxes, prompts, canonical evidence, and model-visible state.
- Make PAEOS the sole authority for tools, retries, fallbacks, and admission.
- Disable spawn, teams, skills, MCP tools, and all unconfigured capabilities mechanically.
- Bind one immutable probe to one adapter version, authenticated profile lock, process, session,
  sandbox, model receipt, tool journal, and evidence bundle.
- Normalize failures into stable machine-readable reason codes without discarding raw evidence.
- Detect provider, model, family, capability, version, process, and session drift fail-closed.
- Support unattended normal-path probing after one-time operator authentication, while halting
  cleanly on token expiry, revocation, or ambiguous local ownership.
- Preserve Builder != Auditor using physical, evidence-backed model-family receipts.
- Fail qualification when the provider runtime hides its attempt count, physical model identity,
  capability state, or session correlation.

## 4. Non-goals

- PAEOS will not read, copy, print, rotate, refresh, or archive authentication secrets.
- This design does not admit every Cline model, every free model, or logical `paeos-code`.
- This design does not authorize Gate B, a live canary, SAKG resumption, merging, or promotion.
- This design does not implement the Gate C provider/supervisor registries, Gate B transaction
  projection, Gate D production capability broker, or Gate G lifecycle revalidation.
- The adapter will not choose fallback providers or models.
- The adapter will not repair incomplete evidence after execution.
- The adapter is not a general-purpose agent orchestrator and cannot own canonical task history.
- No claim is made that OAuth never expires or third-party interfaces never drift.
- Passing Gate A does not make the adapter a production worker. Gate D must separately bind a
  frozen L11 `TaskPackage` and `CapabilityToken` before any real task mutation.

## 5. Trust boundary

PAEOS owns:

- canonical task and lifecycle state;
- immutable task contracts and capability policy;
- provider/model eligibility decisions;
- retry, cooldown, fallback, and quota policy;
- tool approval and sandbox execution;
- evidence requirements, admission assessment, and debt records; and
- Court submission and lifecycle advancement.

The adapter owns only:

- authenticated provider session mechanics;
- version-specific wire translation;
- creation and termination of one provider session; and
- collection of raw provider/session observations.

The model owns no durable state and receives no credential material or policy authority.

The trusted computing base for this gate is deliberately explicit: the PAEOS admission evaluator,
the exact adapter implementation, the pinned Cline Core/Hub runtime and its documented automation
boundary, the pinned Node runtime and SDK-host wrapper, the OS process/filesystem primitives used
for isolation, and the local evidence hashing code. Provider output, model prose, profile contents,
repository text, session messages, UI labels, and adapter-reported claims are untrusted
observations until independently reconciled.

If Cline Core/Hub requires importing undocumented private internals, cannot expose provider-attempt
telemetry, or cannot mechanically deny native tools, the route is unqualifiable. Convenience or a
successful artifact does not compensate for an opaque trust boundary.

### 5.1 Threat model and residual risk

The design must resist a model requesting undeclared tools, Cline silently enabling defaults,
provider/model substitution, hidden provider retries, stale or injected sessions, profile
cross-contamination, duplicate events, malformed evidence, credential leakage, adapter/runtime
upgrade drift, and crashes around possible side effects. Controls are preventive where possible;
post-run logs alone are not a security boundary.

The profile root and every ancestor below the configured private runtime root must be owned by the
expected local user, non-symlinked, and non-group/world-writable. The adapter and SDK dependency
closure are hash-pinned and qualified together. A compromised host account, compromised Cline
package, or malicious provider remains inside the trusted-computing-base/residual-risk envelope;
Gate A cannot cryptographically prove behavior hidden inside those components. Such evidence must
never be described as stronger than host-observed qualification.

## 6. Component architecture

### 6.1 Existing-seam reuse matrix

- `ProbeContract`, `RawWorkerRun`, `PhysicalModelReceipt`, `WorkerBinding`,
  `admitted_worker_binding`, and `enforce_receipt_decorrelation` in
  `runtime.worker_admission`: **EXTEND_WRAP**. Preserve their authority and compatibility; add
  versioned observations only when the existing type cannot express them.
- `evaluate_tool_request` and `DesktopApprovalBroker`: **EXTEND_WRAP** for the disposable probe.
  The Core/Hub adapter may use a different callback transport, but must delegate to the same pure
  decision function and produce compatible `ToolDecisionRecord` evidence.
- `paeos.model_router` catalog, physical-family derivation, A-08, and normalized error types:
  **REUSE_UNCHANGED**. Adapter code does not create a second model catalog or error taxonomy.
- `kernel.evidence`, CAS, and Court evidence rules: **REUSE_UNCHANGED** as canonical evidence
  authority. Gate A may stage a manifest, but does not create another evidence ledger.
- `kernel.capability.CapabilityBroker`, `TaskPackage`, and Gate D confinement:
  **REUSE_UNCHANGED / DEFER**. A disposable probe uses its existing narrow policy; production
  tool authority is not implemented here.
- Gate B transaction states, claims, fencing tokens, and `RECONCILIATION_REQUIRED`:
  **DEFER AND COMPOSE**. Gate A records side-effect certainty but does not invent a parallel
  durable transaction state machine.
- Gate C provider and supervisor registries: **DEFER AND COMPOSE**. Gate A stores one local,
  immutable qualification record; Gate C later registers the adapter through its canonical
  descriptor assembly.

Any implementation plan must state the applicable disposition before touching each seam and must
include a characterization test before an `EXTEND_WRAP` change.

### 6.2 `AdmissionProbeTransport`

A minimal provider-neutral protocol implemented by the existing CLI diagnostic transport and the
new Cline Core/Hub transport:

```python
class AdmissionProbeTransport(Protocol):
    def run_probe(
        self,
        contract: ProbeContract,
        evidence_root: Path,
    ) -> RawWorkerRun | AdapterFailureReceipt: ...
```

It accepts the existing immutable `ProbeContract`; it does not define a production worker
contract. It exposes no provider-specific credential object and has no methods for routing,
retrying, promotion, Court submission, lifecycle advancement, or task-package mutation.

### 6.3 `AdapterQualificationRecord`

Gate A writes a single create-only qualification record rather than creating a registry. The
record is keyed by adapter ID/protocol version, implementation hash, exact Core/Hub runtime name,
semantic version and binary/module hash, automation-protocol/schema hash, provider/model tuple,
capability-schema hash, host isolation profile hash, and qualification evidence hash.

Qualification records are trusted local startup inputs, never runtime-discovered executable
plugins. A mismatch produces `ADAPTER_VERSION_UNQUALIFIED` before authentication or provider
invocation. Gate C later consumes this record through its canonical provider/adapter registry.

### 6.4 `AuthenticatedProfileHandle`

A dedicated Cline runtime profile exists outside repository and evidence roots. It is created with
directory mode `0700`; sensitive files remain `0600` or stricter. The adapter launches or connects
to the supported Cline process by profile path or opaque local handle. Secret values must never
appear in argv, environment variables, IPC payloads, logs, receipts, process listings, or hashes.

The handle exposes only a random non-secret profile UUID, an operator-maintained authentication
epoch, an authentication status class (`READY`, `AUTH_FAILED`, `EXPIRED`, `UNKNOWN`), an exclusive
OS lock, and a runtime connection handle. The UUID is not derived from profile contents. The
authentication epoch increments after every reauthentication and invalidates earlier
qualifications without identifying or hashing a secret.

Before Gate B exists, the OS lock is a local concurrency guard only. It grants no durable claim or
replay authority, and an ambiguous stale lock halts for operator recovery. After Gate B, profile
ownership must use the canonical claim/fencing primitives rather than a second lease mechanism.

### 6.5 `ClineCoreAdmissionAdapter`

Uses a documented, versioned Cline Core/Hub automation boundary rather than ordinary CLI agent
mode. A public SDK, documented local protocol, or stable Hub IPC is acceptable. Direct imports of
undocumented/minified private internals are not a supported production boundary; if unavoidable
for an experiment, the route remains diagnostic-only and is qualified to the exact content hash.

The adapter negotiates an explicit protocol version and capability set and must prove in the
physical session manifest:

- tools enabled only through the PAEOS approval callback;
- spawn and teams disabled;
- skills and MCP/settings tools disabled;
- provider-native editor, shell, web, filesystem, model-routing, and model tools unavailable
  unless the probe contract names the mediated operation;
- exact provider, model, sandbox/workspace, session, and invocation IDs;
- one provider attempt per declared model turn; and
- no automatic fallback, credential refresh, continuation, or model substitution.

Initial qualification pins `backendMode="local"` in a dedicated wrapper process and a dedicated
data directory. `auto` is forbidden because it can silently switch between hub and local hosts;
shared hub and remote modes are separate future qualification tuples. The adapter supplies the
session ID rather than accepting an implicit one. For local mode, a host-injected `fetch`
observation wrapper records only attempt number, provider request ID, timing, status, and
side-effect certainty—never authorization headers or prompt/response bodies. Per-session or stored
provider overrides that bypass this observer are forbidden and must be detected during startup.

If Core/Hub cannot expose complete capability state and provider-attempt telemetry, the adapter is
unqualifiable. A configuration request or UI setting is not proof that the runtime obeyed it.

#### 6.5.1 Local feasibility finding and mandatory checkpoint

The installed `cline` package is version `3.0.60` and declares public `@cline/sdk` and
`@cline/core` dependencies at `0.0.81`. Its exported declarations include `ClineCore.create`,
`start`, `subscribe`, `abort`, `stop`, explicit provider/model/session fields, runtime flags for
tools/spawn/teams/MCP settings, per-tool policies, injected local `fetch`, and persisted session
snapshots. This makes the public SDK a plausible boundary and the preferred implementation target.

That inventory is not qualification. Before implementation Task 1, a read-only feasibility record
must hash the installed packages and prove which public exports provide: credential-profile use,
deny-by-default tool selection, approval callbacks, attempt-level transport observations, physical
provider/model evidence, session correlation, and bounded termination. The direct CLI readiness
check on 2026-08-29 returned `SecItemCopyMatching failed -50`; it was not retried and must not be
treated as a working authenticated control path. If any required SDK property is absent, the plan
stops with a precise gap instead of falling back to CLI, Zen/yolo, browser automation, or private
internals.

#### 6.5.2 Python-to-SDK host boundary

PAEOS remains Python. The adapter therefore launches a small, pinned Node SDK-host wrapper with a
shell-free argv, exact working directory, minimal environment allowlist, dedicated
`CLINE_DATA_DIR`, and hashes for Node, the wrapper, `@cline/sdk`, `@cline/core`, and their resolved
lockfile/dependency closure. No package installation or version resolution occurs at invocation
time.

The wrapper accepts exactly one canonical, length-prefixed JSON request on stdin and emits
length-prefixed structured events on stdout; stderr is raw diagnostic evidence. Unknown messages,
oversize frames, duplicate sequence numbers, invalid UTF-8, non-canonical data, or post-terminal
events terminate the invocation. The wrapper owns no policy: it only translates SDK events,
forwards one declared tool request to the Python probe callback, and applies the returned decision.
It cannot execute a provider-native default tool or choose a retry, model, or provider.

### 6.6 Probe tool callback

The Core/Hub callback transport delegates every request to existing `evaluate_tool_request` and
emits compatible `ToolDecisionRecord` evidence. For Gate A it supports only the exact disposable
one-edit/one-verification-command probe. It is not a general `PaeosToolMediator` and cannot mint
capabilities.

No provider-native tool may execute outside the callback. Production typed operations, signed
`CapabilityToken` enforcement, OS budgets, symlink defense, and network confinement remain Gate D.

### 6.7 Invocation evidence exporter

The adapter stages one create-only invocation manifest containing approved non-secret artifacts
for the exact session. It never copies the profile, settings, tokens, cookies, account records, or
unrelated sessions. Existing CAS/evidence code remains the canonical publisher and Court binding;
the adapter exporter cannot seal or ratify its own output.

## 7. Core contracts

### 7.1 Extended `ProbeContract`

Gate A extends the existing `ProbeContract` or wraps it in a versioned transport envelope. It does
not introduce a competing `WorkerSessionContract`. The envelope contains only transport concerns:

- contract, invocation, and predecessor-probe IDs;
- adapter ID, protocol version, and qualification-record digest;
- expected authentication epoch;
- provider, model, and expected family;
- payload, sandbox, workspace, and environment-manifest hashes;
- exact probe operation and canonical argument predicate;
- timeout and maximum declared model-turn count;
- `retry_budget_per_turn=0`;
- evidence staging root and retention class; and
- expected artifact and discriminative verification contract.

Contract-budgeted continuation after an approved tool result is a new model turn, not a retry.
Every permitted turn remains within the declared maximum and the same session/task binding. The
adapter must reject unknown envelope fields or unsupported protocol features rather than infer
defaults.

### 7.2 `AdapterFailureReceipt`

Required immutable fields:

- invocation and contract IDs;
- adapter/runtime identity and hashes;
- adapter observation state at failure;
- normalized reason code;
- retryability classification;
- side-effect certainty (`NOT_DISPATCHED`, `PROVIDER_ACCEPTED`, `TOOL_EFFECT_POSSIBLE`, or
  `UNKNOWN`);
- process/session identity if created;
- raw stdout/stderr hashes;
- manifest/messages hashes when present;
- evidence bundle hash; and
- host boot ID, monotonic observation reading, and diagnostic wall timestamp.

Worker prose cannot populate the normalized reason code. Adapter-specific reason codes extend a
small `AdapterFailureKind` enum only where `paeos.model_router.types.NormalizedErrorType` has no
equivalent; provider failures reuse the existing canonical enum and normalization logic.

### 7.3 Successful result

A successful adapter result is the existing `RawWorkerRun`, extended or wrapped only where
required to bind:

- adapter qualification;
- profile UUID and authentication epoch;
- process start token;
- capability manifest hash; and
- complete evidence-bundle manifest hash.

It also records protocol version, authentication epoch, provider turn IDs, and the complete
ordered provider-attempt observations. Missing attempt telemetry is a qualification failure, not
an empty attempt list.

The resulting `WorkerBinding` remains evidence-backed and is revalidated at construction.

## 8. Invocation lifecycle

Every invocation produces these ordered adapter observations:

1. `DECLARED`
2. `ADAPTER_QUALIFIED`
3. `PROFILE_LOCKED`
4. `SESSION_CREATED`
5. `MODEL_ATTESTED`
6. `TOOL_MEDIATED`
7. `EXECUTION_FINISHED`
8. `EVIDENCE_STAGED`
9. `TERMINAL_RECEIPT_WRITTEN`

These are not Gate B transaction states and grant no lifecycle authority. Before Gate B, they are
create-only, hash-chained local observations. After Gate B integration, the canonical coordinator
references their hashes through the sole ledger-writer path. No state may be inferred from missing
evidence. The adapter cannot emit or advance itself to `ADMITTED`; the independent admission
evaluator produces `ADMITTED` or `REJECTED` from the terminal run.

### 8.1 Adapter qualification

The exact runtime and implementation hashes must match a qualified record. Unknown or changed
versions stop before authentication or provider use.

### 8.2 Profile lock

One process may hold the profile OS lock at a time. The observation binds owner PID, process start
token, host boot ID, invocation ID, monotonic acquisition reading, and nonce. PID and wall-clock
time alone are insufficient because of reuse and clock adjustment.

Before Gate B, lock loss, stale ownership, or concurrent claim returns `PROFILE_LOCK_FAILED` and
requires manual reconciliation; the adapter never auto-breaks the lock. Gate B may later replace
this conservative stop with its canonical monotonic fencing and ledger-derived claim recovery.

### 8.3 Session creation and delta proof

The authoritative session ID is returned by the documented Core/Hub create-session response and
must echo the invocation nonce. A non-secret before/after inventory of session identifiers and
metadata hashes is supporting tamper/ambiguity evidence, not the identity source. Zero returned
IDs, multiple root sessions, a missing nonce, or disagreement with the inventory returns
`SESSION_AMBIGUOUS`.

The session must bind the exact sandbox, provider, model, capabilities, process, and invocation.

### 8.4 Model attestation

Configured, provider-returned, session-manifest, and assistant-message identities must agree. The
family is derived independently from the observed model ID using the qualified catalog. Unknown
or conflicting identity fails closed.

### 8.5 Tool mediation

Tool calls are processed sequentially unless the contract explicitly permits independent
parallel calls. Each request is bound to session, invocation, call ID, tool name, canonical input
hash, and prior decision-chain hash.

An unconfigured call is denied, journalled, and terminates the session. It is never executed.

### 8.6 Completion and evidence sealing

The adapter records exit/termination state before releasing the profile lock. The exporter then
copies the invocation's non-secret session artifacts, writes a hash manifest, fsyncs files and
directories, and publishes a create-only staging result for independent CAS/evidence ingestion.

The profile lock is released only after terminal local evidence exists. Before Gate B, ambiguous
release or possible side effects returns `SIDE_EFFECT_UNCERTAIN` and blocks another invocation.
After Gate B integration, the coordinator—not the adapter—maps that fact to
`RECONCILIATION_REQUIRED`.

## 9. Retry and fallback ownership

The adapter performs no autonomous retry, model substitution, provider fallback, credential
refresh, or cooldown decision. A model turn is a contract-declared step in one session; a retry is
a repeated provider attempt for the same turn after failure. These are distinct and recorded with
separate turn and attempt identifiers.

For admission probes, each model turn permits exactly one provider attempt. A continuation turn is
allowed only when the contract requires it after a recorded tool result and the declared maximum
turn count has not been reached. Any repeated attempt after a failed turn—especially after
`AUTH_FAILED`—is a contract violation regardless of whether the provider calls it recovery,
refresh, or retry.

PAEOS may grant a retry only in a new invocation contract with a new invocation/probe ID. The
contract must name the permitted normalized error class. Permanent failures such as
`AUTH_FAILED`, `MODEL_MISMATCH`, `CAPABILITY_DRIFT`, and `EVIDENCE_INCOMPLETE` are never
automatically retryable.

Provider fallback returns to the PAEOS router. The adapter cannot select another model.

Attempt control must be evidenced at the actual provider-dispatch boundary. Counting assistant
messages, adapter calls, or UI events is insufficient because Core/Hub may retry below those
layers. Qualification therefore requires one of: structured provider-attempt events from the
supported protocol, or a local transport observation point that records request IDs without
recording credentials or prompt bodies. If neither exists, zero-retry behavior is unprovable and
the route is rejected.

Cancellation is terminal for the invocation. The adapter terminates only its bound child/session,
records whether provider acceptance or a tool side effect may already have occurred, and never
converts cancellation into a fresh attempt. Every invocation ID is create-only; replaying it,
receiving a duplicate tool call ID, or receiving a second terminal response is a protocol fault.

## 10. Failure taxonomy

Provider failures reuse these existing `NormalizedErrorType` values where applicable:

- `AUTH_FAILED`
- `QUOTA_EXHAUSTED`
- `PROVIDER_UNAVAILABLE`
- `TIMEOUT`
- `BAD_REQUEST`
- `MODEL_UNAVAILABLE`

The first applicable `AdapterFailureKind` is recorded separately, with additional findings
preserved:

- `ADAPTER_VERSION_UNQUALIFIED`
- `CAPABILITY_DRIFT`
- `PROFILE_LOCK_FAILED`
- `SESSION_AMBIGUOUS`
- `MODEL_MISMATCH`
- `UNKNOWN_MODEL_FAMILY`
- `TOOL_DENIED`
- `COMMAND_EXPANSION`
- `TIMEOUT_SAFE`
- `SIDE_EFFECT_UNCERTAIN`
- `EVIDENCE_INCOMPLETE`
- `VERIFICATION_NONDISCRIMINATIVE`
- `TRANSPORT_FAILED`

Raw provider text is evidence, never the normalization authority. Normalization uses structured
provider status where available and audited deterministic matching only as a compatibility
fallback.

The implementation plan must publish an explicit precedence table between canonical provider
errors and adapter failures. `AUTH_FAILED` must not collapse into `ADMISSION_REJECTED`, and a later
cleanup error must not mask an earlier capability escape or possible side effect.

## 11. Evidence and provenance bundle

Every invocation bundle contains:

- canonical task contract and hash;
- adapter/runtime identity, versions, and implementation hashes;
- qualification-record hash;
- non-secret authenticated-profile UUID and authentication epoch;
- lock and process/start-token receipts;
- session before/after delta proof;
- configured and observed provider/model/family records;
- capability manifest;
- ordered tool request/decision/result journal;
- raw stdout, stderr, and exit status;
- invocation session manifest and messages;
- artifact before/after hashes;
- baseline-fail, candidate-pass, mutation-fail, and restoration-pass receipts;
- normalized terminal result; and
- a canonical hash manifest covering every included file.

The bundle must pass a deterministic secret scanner before publication. A scanner failure returns
`EVIDENCE_INCOMPLETE`, quarantines the unpublishable staging bundle with restrictive permissions,
and alerts the Overseer without printing matched content.

Scanner reports contain only finding category, artifact-relative path, byte offset/range, scanner
rule version, and content hash—never matched bytes. The quarantine path is excluded from routine
logs and model context. Retention, maximum bundle size, and disk-watermark policy are explicit;
storage pressure halts new probes before evidence is overwritten or silently discarded. Cleanup
is a separately authorized retention operation and never runs inside the adapter invocation.

## 12. Authentication design

PAEOS uses a dedicated persistent Cline profile, authenticated once by the operator through
Cline's supported flow. PAEOS does not automate login or handle tokens.

The profile is outside:

- all Git worktrees;
- all task sandboxes;
- all evidence bundles; and
- canonical public PAEOS state.

Authentication expiry returns `AUTH_FAILED`, quarantines the adapter route, and requires operator
reauthentication. Reauthentication does not authorize replay of the failed invocation. A new
probe ID and explicit recovery disposition are required.

Bootstrap is explicit: the operator creates the dedicated profile, completes supported Cline
authentication, assigns its random profile UUID, increments the non-secret authentication epoch,
and exits the login process. A read-only readiness probe may then verify only status class and
runtime reachability. It may not enumerate account data or copy settings. The worker process is
started with the profile path/opaque handle, never with secret values copied into argv or its
environment.

## 13. Concurrency

Initial concurrency for a Cline authenticated profile is exactly one. Multiple models may not
share one profile concurrently. Before Gate B, a crash or uncertain lock blocks further probes
until an operator records a recovery disposition; unattended stale-lock reclamation is forbidden.

Future concurrency requires separate authenticated profiles or provider-supported isolated
sessions plus independent locks and, after Gate B, distinct fenced claims. Increasing router
concurrency alone cannot override this limit.

## 14. Adapter qualification

Qualification is separate from worker admission. It proves that the adapter can constrain and
observe the exact provider runtime version. It is bound to the exact protocol/schema version and
declared feature set; unsupported optional features are rejected during negotiation rather than
silently disabled.

Qualification requires:

- schema/ABI compatibility tests against the installed runtime;
- documented automation-boundary and upgrade-compatibility characterization;
- explicit spawn/team/skill/MCP disablement proof;
- provider-boundary attempt telemetry and zero-retry proof for permanent errors;
- exact model/session provenance capture;
- tool mediation and denial tests;
- authenticated-profile isolation tests;
- secret-exclusion tests;
- crash/recovery tests at every lifecycle transition; and
- independent non-provider-family review.

The adapter must also prove deterministic cancellation, duplicate invocation/tool-call rejection,
maximum response/event sizes, bounded shutdown, and absence of credentials in argv, environment,
logs, receipts, exception strings, and process listings.

An upgrade changes the runtime hash and automatically removes qualification until these checks
pass again.

## 15. Testing strategy

### 15.1 Unit and contract tests

- adapter protocol and failure-receipt validation;
- protocol-version negotiation, unknown fields/features, and size limits;
- lifecycle transition legality;
- profile lock ownership, boot identity, PID reuse, contention, and conservative crash stop;
- profile ownership, permission, symlink, authentication-epoch, and path-escape validation;
- session delta uniqueness;
- reason-code normalization and precedence;
- evidence canonicalization and secret exclusion;
- receipt and manifest hash recomputation; and
- Builder != Auditor enforcement.

### 15.2 Integration tests

- real Cline SDK local session creation with spawn/teams disabled;
- exact PAEOS probe-callback mediation;
- authenticated profile use without secret copying;
- pinned local backend with no automatic hub/remote fallback or provider-fetch override;
- model identity agreement across all sources;
- clean process/session termination; and
- no writes outside sandbox, evidence root, and adapter-owned profile paths.

Integration tests must use a fake or instrumented Core/Hub boundary first. A live test is not a
substitute for deterministic contract coverage and may not run until the exact runtime hash has a
qualification candidate.

### 15.3 Adversarial tests

- tool-name/input substitution;
- duplicate and replayed tool calls;
- alternate session injection;
- profile lock theft and stale PID reuse;
- multiple new-session ambiguity;
- provider/model/family substitution;
- capability drift after runtime upgrade;
- malformed or partial evidence;
- secret planted in provider output/evidence staging; and
- crash before and after possible side effects;
- hidden provider retry below the adapter call;
- duplicate invocation, tool-call, and terminal-response replay;
- cancellation before dispatch, after provider acceptance, and during a tool effect;
- credential leakage through argv, environment, error strings, process metadata, and scanner
  output; and
- evidence disk exhaustion and oversize provider events.

### 15.4 Discriminative mutations

At minimum, prove tests reject these reversible mutations:

1. enable spawn or teams;
2. permit a repeated provider attempt after `AUTH_FAILED`;
3. accept a conflicting physical model identity;
4. bypass the PAEOS probe callback;
5. accept a rejected run as `WorkerBinding`;
6. omit profile lock start-token validation; and
7. publish a bundle containing a secret marker;
8. hide a second provider attempt beneath one model turn;
9. auto-break an ambiguous profile lock; and
10. treat adapter-local state as a Gate B transaction commitment.

Each mutation is applied alone, fails for the intended reason, and is fully restored before the
next mutation.

### 15.5 Live qualification and admission

Only after mechanical qualification and independent audit:

1. run one adapter qualification canary;
2. run three sequential admission probes with new IDs linked to
   `qwen3-8-admission-01`;
3. stop after the first rejection;
4. independently reconcile every raw record; and
5. qualify only the exact adapter/runtime/provider/model tuple proven by those runs.

## 16. Migration and compatibility

1. Keep commit `07e4264` worker binding and bridge-manifest work as the reviewed foundation.
2. Preserve `qwen3-8-admission-01` permanently as rejected evidence.
3. Characterize the existing CLI transport, admission types, approval broker, router errors,
   A-08, and evidence seams before modification.
4. Introduce only `AdmissionProbeTransport`, the extended/wrapped probe envelope, failure receipt,
   and one immutable qualification-record format without routing production work through them.
5. Implement and mechanically qualify `ClineCoreAdmissionAdapter` against a documented pinned
   Core/Hub boundary.
6. Mark the ordinary CLI adapter `QUARANTINED_DIAGNOSTIC_ONLY` through a machine-checked admission
   guard, not a comment or naming convention.
7. Run independent L13/L14 checks and sequential live admission probes.
8. Update DEBT-0058 only from reconciled evidence.
9. Gate B later replaces conservative local locking with canonical claims/fencing; Gate C
   registers the qualified adapter; Gate D separately authorizes production task execution.

No existing adapter code is deleted during this gate. Removal or consolidation belongs to a later
review after the new adapter is proven.

## 17. Rollback

Before live use, rollback is deletion/reversion of the new adapter commits while retaining all
failure and qualification evidence. The CLI adapter remains quarantined, so rollback cannot
silently reactivate it.

After any live invocation, rollback also quarantines the adapter qualification record and profile
lock state. Evidence bundles are immutable and are never deleted as part of rollback.

## 18. Lifecycle and authority

- This design is Gate A remediation, not Gate A closure.
- Implementation occurs only in an isolated worktree under a frozen implementation plan.
- Builders cannot self-verify or self-admit.
- L14 must use an attributable model family different from every production-code builder family.
- Court and Founder authority are not delegated to the adapter, model, worker, or Architect.
- Main/trunk promotion remains forbidden until L15 records and an L16 Founder disposition.
- Gate B and later gates remain blocked until Gate A is genuinely closed or their approved plans
  explicitly permit independent unit implementation without live-route consumption.
- Gate A closure admits only a disposable route tuple. It neither consumes nor pre-implements Gate
  C provider registration, Gate D production confinement, or Gate E automatic recovery.

## 19. Acceptance criteria

The design is successfully implemented only when all of the following are true:

1. The ordinary Cline CLI is no longer the admitted trust boundary.
2. A minimal provider-neutral admission-probe contract exists and has no Cline-specific policy
   semantics; no parallel provider registry or production worker contract is created.
3. The Cline SDK adapter uses a dedicated authenticated profile without exposing secrets.
4. Spawn, teams, skills, MCP, and unconfigured tools are physically unavailable or fail closed
   before execution and are proven absent in the session receipt.
5. Every model turn has exactly one provider attempt; terminal failures generate no repeated
   attempt, and continuation turns occur only when declared by the contract.
6. Exact normalized failures survive into structured results.
7. Profile, process, session, model, tool, artifact, and evidence identities are hash-bound.
8. Before Gate B, crash and concurrency ambiguity halt without replay; after Gate B integration,
   only the coordinator may enter canonical reconciliation.
9. Evidence staging bundles pass content-free secret scanning, size/retention checks, and contain
   only invocation-scoped non-secret artifacts before independent CAS ingestion.
10. Discriminative mutations fail for their intended protections.
11. Three new sequential live probes are independently reconciled as admitted.
12. Builder != Auditor is proven from attributable physical receipts.
13. DEBT-0058 is updated from evidence and remains open unless every repayment condition is met.
14. No main/trunk, SAKG, Court, or later-gate advancement occurs without separate authority.
15. Provider-attempt telemetry proves no hidden retry; an opaque attempt boundary cannot qualify.
16. The implementation composes with existing admission, model-router/A-08, capability, evidence,
    and Gate B-G plans using recorded reuse dispositions.

## 20. Consequences

This design is more involved than copying an authenticated profile or patching CLI flags, but the
Gate A implementation is now deliberately smaller than the original draft. It places the trust
boundary at a public, pinned SDK seam while leaving transactions, registries, production
capabilities, and canonical evidence with their existing owners. Credentials remain outside
model-visible and evidentiary state; runtime drift becomes a qualification failure rather than an
invisible behavior change.

The trade-off is conservative liveness: before Gates B and E, an ambiguous crash or profile lock
still requires operator recovery. That is intentional. Operationally human-free recovery is
earned later through canonical fencing and deterministic watchdogs; Gate A must not simulate it
with unsafe stale-lock deletion or retry loops.
