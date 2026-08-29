# PAEOS Provider-Neutral Worker Session Adapter Design

**Status:** Founder-approved design, pending implementation plan  
**Date:** 2026-08-29  
**Scope:** Gate A worker admission remediation  
**Branch:** `codex/control-plane-recovery-s1-clean-recovered`  
**Baseline:** `bfbbc48e6e9950bcd76f1f2f843f9e29b0acdf42`  
**Authority:** Founder  
**Architect/Overseer:** Codex GPT-5.6 Sol  
**Implementation role:** replaceable worker only; no self-ratification

## 1. Decision

PAEOS will stop treating the ordinary Cline CLI invocation as the security and admission
boundary. It will define a provider-neutral `WorkerSessionAdapter` contract and implement Cline
through its Core/Hub automation interface. Cline becomes one replaceable authenticated transport
behind PAEOS-owned policy, tools, retry control, evidence, and canonical state.

The existing `ClineWorkerTransport` CLI path remains quarantined diagnostic compatibility code.
It is not eligible for the production worker pool unless it independently satisfies the same
adapter contract in a future qualification.

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

- Make model providers and AI tools replaceable without changing PAEOS policy or lifecycle code.
- Keep credentials outside worker sandboxes, prompts, canonical evidence, and model-visible state.
- Make PAEOS the sole authority for tools, retries, fallbacks, and admission.
- Disable spawn, teams, skills, MCP tools, and all unconfigured capabilities mechanically.
- Bind one immutable task to one adapter version, authenticated profile lease, process, session,
  sandbox, model receipt, tool journal, and evidence bundle.
- Normalize failures into stable machine-readable reason codes without discarding raw evidence.
- Detect provider, model, family, capability, version, process, and session drift fail-closed.
- Support unattended operation after a one-time operator authentication, while halting cleanly on
  token expiry or revocation.
- Preserve Builder != Auditor using physical, evidence-backed model-family receipts.

## 4. Non-goals

- PAEOS will not read, copy, print, rotate, refresh, or archive authentication secrets.
- This design does not admit every Cline model, every free model, or logical `paeos-code`.
- This design does not authorize Gate B, a live canary, SAKG resumption, merging, or promotion.
- The adapter will not choose fallback providers or models.
- The adapter will not repair incomplete evidence after execution.
- The adapter is not a general-purpose agent orchestrator and cannot own canonical task history.
- No claim is made that OAuth never expires or third-party interfaces never drift.

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

## 6. Component architecture

### 6.1 `WorkerSessionAdapter`

A provider-neutral interface implemented by Cline and future providers. It accepts an immutable
`WorkerSessionContract` and returns either a complete `RawWorkerRun` or a terminal
`AdapterFailureReceipt`.

The interface must not expose provider-specific credential objects to callers.

### 6.2 `AdapterQualificationRegistry`

Stores allowlisted adapter qualifications keyed by:

- adapter ID and protocol version;
- implementation hash;
- provider runtime name and version;
- provider runtime binary/module hash;
- supported provider/model identifiers;
- capability-schema hash; and
- qualification evidence hash.

Any mismatch produces `ADAPTER_VERSION_UNQUALIFIED` before provider invocation.

### 6.3 `AuthenticatedProfileBroker`

Owns a dedicated Cline runtime profile outside repository and evidence roots. The profile is
created with directory mode `0700`; sensitive files must remain `0600` or stricter.

The broker exposes only:

- profile public fingerprint;
- authentication status class (`READY`, `AUTH_FAILED`, `EXPIRED`, `UNKNOWN`);
- exclusive lease acquisition/release; and
- a provider-runtime connection handle that never reveals token material.

The public fingerprint is derived from non-secret profile identity and configuration metadata. It
must not hash secret bytes because a secret hash is still sensitive correlatable material.

### 6.4 `ClineCoreWorkerAdapter`

Uses the installed Cline Core/Hub automation interface rather than ordinary CLI mode. It must set
explicitly:

- `enableTools=true`;
- `enableSpawn=false`;
- `enableTeams=false`;
- skills disabled;
- MCP settings tools disabled;
- model tools disabled unless named in the contract;
- exact provider and model IDs;
- exact sandbox/workspace root;
- zero repeated provider attempts for a failed model turn; and
- PAEOS-owned approval callbacks/tool executors.

If the Core/Hub interface cannot prove these settings in the physical session manifest, the
adapter returns `CAPABILITY_DRIFT`.

### 6.5 `PaeosToolMediator`

Receives proposed tool calls from the provider adapter. It validates each call against the exact
task contract, writes an immutable request record, records the decision durably, and only then
invokes a sandbox executor.

No provider-native editor, shell, spawn, team, skill, MCP, web, or filesystem capability may
execute outside this mediator.

### 6.6 `EvidenceBundleWriter`

Writes one create-only evidence bundle per invocation. It copies only the new session's approved
non-secret artifacts from the authenticated profile. It never copies the profile, provider
settings, tokens, cookies, account records, or unrelated sessions.

## 7. Core contracts

### 7.1 `WorkerSessionContract`

Required immutable fields:

- contract and invocation IDs;
- predecessor probe ID when remediating a failure;
- adapter ID, protocol version, and qualification digest;
- provider, model, and expected family;
- task/payload hash;
- sandbox and workspace identity;
- exact enabled tool/capability set;
- exact tool arguments or argument predicates;
- timeout, maximum model-turn count, and retry budget per model turn;
- allowed environment variable names;
- evidence root;
- expected artifact and discriminative verification contract; and
- data classification.

Admission probes require `retry_budget_per_turn=0`. Contract-budgeted continuation after an
approved tool result is a new model turn, not a retry; every permitted turn must remain within the
declared maximum and the same session/task binding.

### 7.2 `AdapterFailureReceipt`

Required immutable fields:

- invocation and contract IDs;
- adapter/runtime identity and hashes;
- lifecycle state at failure;
- normalized reason code;
- retryability classification;
- possible-side-effect flag;
- process/session identity if created;
- raw stdout/stderr hashes;
- manifest/messages hashes when present;
- evidence bundle hash; and
- timestamp.

Worker prose cannot populate the normalized reason code.

### 7.3 Successful result

A successful adapter result is the existing `RawWorkerRun`, extended only where required to bind:

- adapter qualification;
- profile public fingerprint;
- process start token;
- capability manifest hash; and
- complete evidence-bundle manifest hash.

The resulting `WorkerBinding` remains evidence-backed and is revalidated at construction.

## 8. Invocation lifecycle

Every invocation follows this state machine:

1. `DECLARED`
2. `ADAPTER_QUALIFIED`
3. `PROFILE_LEASED`
4. `SESSION_CREATED`
5. `MODEL_ATTESTED`
6. `TOOL_MEDIATED`
7. `EXECUTION_FINISHED`
8. `EVIDENCE_SEALED`
9. `ADMITTED` or `REJECTED`

Transitions are append-only and hash chained. No state may be inferred from missing evidence.

### 8.1 Adapter qualification

The exact runtime and implementation hashes must match a qualified record. Unknown or changed
versions stop before authentication or provider use.

### 8.2 Profile lease

One process may own the profile at a time. The lease binds owner PID plus process start token,
invocation ID, acquisition time, expiry, and nonce. PID alone is insufficient because of reuse.

Lease loss, stale ambiguous ownership, or concurrent claim returns `PROFILE_LEASE_FAILED`. A stale
lease may be quarantined only after proving the recorded process/start-token pair is no longer
alive.

### 8.3 Session creation and delta proof

Before creation, the adapter records a non-secret inventory of profile session identifiers and
metadata hashes. After creation it proves exactly one new root session belongs to the invocation.
Zero or multiple candidates return `SESSION_AMBIGUOUS`.

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

The adapter records exit/termination state before releasing the profile lease. The evidence writer
then copies the invocation's non-secret session artifacts, writes a hash manifest, fsyncs files and
directories, and publishes a create-only final result.

The profile lease is released only after terminal evidence exists. If release or evidence state is
ambiguous, the invocation enters `RECONCILIATION_REQUIRED`.

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

## 10. Failure taxonomy

The first applicable normalized reason is recorded, with additional findings preserved separately:

- `AUTH_FAILED`
- `ADAPTER_VERSION_UNQUALIFIED`
- `CAPABILITY_DRIFT`
- `PROFILE_LEASE_FAILED`
- `SESSION_AMBIGUOUS`
- `MODEL_MISMATCH`
- `UNKNOWN_MODEL_FAMILY`
- `TOOL_DENIED`
- `COMMAND_EXPANSION`
- `TIMEOUT_SAFE`
- `SIDE_EFFECT_UNCERTAIN`
- `EVIDENCE_INCOMPLETE`
- `VERIFICATION_NONDISCRIMINATIVE`
- `PROVIDER_UNAVAILABLE`
- `QUOTA_EXHAUSTED`
- `TRANSPORT_FAILED`

Raw provider text is evidence, never the normalization authority. Normalization uses structured
provider status where available and audited deterministic matching only as a compatibility
fallback.

## 11. Evidence and provenance bundle

Every invocation bundle contains:

- canonical task contract and hash;
- adapter/runtime identity, versions, and implementation hashes;
- qualification-record hash;
- non-secret authenticated-profile public fingerprint;
- lease and process/start-token receipts;
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

## 13. Concurrency

Initial concurrency for a Cline authenticated profile is exactly one. Multiple models may not
share one profile concurrently.

Future concurrency requires separate authenticated profiles or provider-supported isolated
sessions plus independent leases. Increasing router concurrency alone cannot override this limit.

## 14. Adapter qualification

Qualification is separate from worker admission. It proves that the adapter can constrain and
observe the exact provider runtime version.

Qualification requires:

- schema/ABI compatibility tests against the installed runtime;
- explicit spawn/team/skill/MCP disablement proof;
- zero-retry proof for permanent errors;
- exact model/session provenance capture;
- tool mediation and denial tests;
- authenticated-profile isolation tests;
- secret-exclusion tests;
- crash/recovery tests at every lifecycle transition; and
- independent non-provider-family review.

An upgrade changes the runtime hash and automatically removes qualification until these checks
pass again.

## 15. Testing strategy

### 15.1 Unit and contract tests

- adapter protocol and failure-receipt validation;
- lifecycle transition legality;
- profile lease ownership, expiry, PID reuse, and contention;
- session delta uniqueness;
- reason-code normalization and precedence;
- evidence canonicalization and secret exclusion;
- receipt and manifest hash recomputation; and
- Builder != Auditor enforcement.

### 15.2 Integration tests

- real Cline Core/Hub session creation with spawn/teams disabled;
- exact PAEOS tool mediation;
- authenticated profile use without secret copying;
- model identity agreement across all sources;
- clean process/session termination; and
- no writes outside sandbox, evidence root, and adapter-owned profile paths.

### 15.3 Adversarial tests

- tool-name/input substitution;
- duplicate and replayed tool calls;
- alternate session injection;
- profile lease theft and stale PID reuse;
- multiple new-session ambiguity;
- provider/model/family substitution;
- capability drift after runtime upgrade;
- malformed or partial evidence;
- secret planted in provider output/evidence staging; and
- crash before and after possible side effects.

### 15.4 Discriminative mutations

At minimum, prove tests reject these reversible mutations:

1. enable spawn or teams;
2. permit a repeated provider attempt after `AUTH_FAILED`;
3. accept a conflicting physical model identity;
4. bypass the PAEOS tool mediator;
5. accept a rejected run as `WorkerBinding`;
6. omit profile lease start-token validation; and
7. publish a bundle containing a secret marker.

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
3. Introduce the provider-neutral interface without routing production work through it.
4. Implement and mechanically qualify `ClineCoreWorkerAdapter`.
5. Mark the ordinary CLI adapter `QUARANTINED_DIAGNOSTIC_ONLY`.
6. Run independent L13/L14 checks.
7. Perform new sequential live probes.
8. Update DEBT-0058 only from reconciled evidence.

No existing adapter code is deleted during this gate. Removal or consolidation belongs to a later
review after the new adapter is proven.

## 17. Rollback

Before live use, rollback is deletion/reversion of the new adapter commits while retaining all
failure and qualification evidence. The CLI adapter remains quarantined, so rollback cannot
silently reactivate it.

After any live invocation, rollback also quarantines the adapter qualification record and profile
lease state. Evidence bundles are immutable and are never deleted as part of rollback.

## 18. Lifecycle and authority

- This design is Gate A remediation, not Gate A closure.
- Implementation occurs only in an isolated worktree under a frozen implementation plan.
- Builders cannot self-verify or self-admit.
- L14 must use an attributable model family different from every production-code builder family.
- Court and Founder authority are not delegated to the adapter, model, worker, or Architect.
- Main/trunk promotion remains forbidden until L15 records and an L16 Founder disposition.
- Gate B and later gates remain blocked until Gate A is genuinely closed or their approved plans
  explicitly permit independent unit implementation without live-route consumption.

## 19. Acceptance criteria

The design is successfully implemented only when all of the following are true:

1. The ordinary Cline CLI is no longer the admitted trust boundary.
2. A provider-neutral adapter contract exists and has no Cline-specific policy semantics.
3. The Cline Core/Hub adapter uses a dedicated authenticated profile without exposing secrets.
4. Spawn, teams, skills, MCP, and unconfigured tools are physically unavailable or fail closed
   before execution and are proven absent in the session receipt.
5. Every model turn has exactly one provider attempt; terminal failures generate no repeated
   attempt, and continuation turns occur only when declared by the contract.
6. Exact normalized failures survive into structured results.
7. Profile, process, session, model, tool, artifact, and evidence identities are hash-bound.
8. Crash and concurrency ambiguity enter reconciliation rather than replay.
9. Evidence bundles pass secret scanning and contain only invocation-scoped non-secret artifacts.
10. Discriminative mutations fail for their intended protections.
11. Three new sequential live probes are independently reconciled as admitted.
12. Builder != Auditor is proven from attributable physical receipts.
13. DEBT-0058 is updated from evidence and remains open unless every repayment condition is met.
14. No main/trunk, SAKG, Court, or later-gate advancement occurs without separate authority.

## 20. Consequences

This design is larger than copying an authenticated profile or patching CLI flags, but it places
the trust boundary where PAEOS can actually enforce it. Provider adapters remain replaceable;
credentials remain outside model-visible and evidentiary state; third-party runtime drift becomes
a qualification failure rather than an invisible behavior change; and unattended operation can
halt safely instead of depending on a capable Overseer noticing worker misbehavior.
