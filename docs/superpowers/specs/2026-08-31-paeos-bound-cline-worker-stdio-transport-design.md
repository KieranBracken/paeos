# PAEOS Bound Cline Worker Stdio Transport Design

**Status:** Approved design; implementation not yet started  
**Scope:** Isolated control-plane recovery worktree only  
**Date:** 2026-08-31

## Problem

The existing `ChatBridgeRuntime` already creates an immutable request under a state-root-bound
bridge directory and waits for a correlated response. The historical GUI bridge did not complete
that protocol: it watched `cline_output.log`, wrote `chatgpt_response.md`, and used clipboard/CDP
activity. Those files were not the request's response path, so normal runs could wait until a
compatibility timeout even while a GUI process was alive. The legacy entrypoints are therefore
fail-closed and must remain so.

The temporary Cline/GLM worker should be usable without a human copy/paste loop, while preserving
PAEOS as the policy and transaction authority. The replacement must be a machine-bound transport,
not a faster GUI automation loop.

## Goals

1. Deliver one PAEOS request to one explicitly bound Cline worker session through a local,
   state-root-bound stdio channel.
2. Write exactly one response envelope to the request's correlated response path, with request,
   transaction, session, model, and payload hashes bound together.
3. Preserve the eleven circuit breakers, fail closed on malformed or ambiguous state, and retain
   raw failure evidence without exposing credentials.
4. Keep the worker implementation-only and supervised. The transport must not self-ratify, create
   Court seals, advance lifecycle layers, promote refs, or resume SAKG.
5. Capture physical provider/model/family metadata so a later non-GLM auditor can prove
   `Builder != Auditor`.
6. Leave a durable, secret-blind handoff that Antigravity can resume from the exact transaction
   boundary.

## Non-goals

- Re-enabling `ops/chatgpt_bridge/monitor_loop.py`, AppleScript, clipboard, CDP, or browser
  scraping.
- Adding a generic background "soft loop" or an unbounded retry loop. The first implementation is
  run-once per transaction; scheduling remains outside this transport.
- Reading, copying, hashing, or logging credential values.
- Closing `DEBT-0058` or `DEBT-0060`, admitting an unattended worker, sealing a gate, or changing
  Court/lifecycle accounting.
- Calling a provider during unit or integration tests. Real Cline probes remain a separately
  authorized operational activity with `RetryPolicy.NONE` and no fallback.
- Modifying `main` or `trunk`, pushing, merging, rebasing, or mutating the quarantined worktree.

## Architectural Context

PAEOS remains the sole policy authority:

```text
Codex/Antigravity Overseer
          |
          v
PAEOS transaction + policy router
          |
          v
Bound Cline worker transport (local framed stdio)
          |
          v
Cline SDK host -> Cline worker session (GLM builder)
```

The transport consumes the existing canonical transaction and bridge protocol types. It must not
create a second ledger or history. A request is accepted only when its transaction, capability
binding, state root, recovery worktree, provider/model tuple, and session identity agree.

## Components and Responsibilities

### 1. Bound worker dispatcher

Add `runtime/integrations/bound_cline_transport.py` with a small, run-once
`BoundClineWorkerTransport` dispatcher and a `dispatch_once(...)` entry point that:

- accepts an already-created request envelope, immutable prompt, and separately hash-bound tool
  policy;
- validates that the request and all paths are beneath the supplied absolute state root;
- requires an isolated recovery worktree and refuses `main`/`trunk` or a path outside the
  worktree allowlist;
- acquires one non-blocking transaction/session lease and rejects duplicate or stale requests;
- launches one worker host with `shell=False`, an explicit absolute executable/module tuple, an
  explicit cwd, and a minimal environment allowlist;
- records PID, process-start token, boot ID, session ID, provider/model IDs, model family, and
  qualification hashes without recording credential material; and
- delegates all tool decisions to the existing PAEOS admission/policy functions.

The dispatcher never interprets worker prose as authority. A worker response is data until the
overseer and the Court independently verify it.

The policy sidecar is canonical JSON and contains allowed tool names, write scopes, the exact
verification command (when applicable), the artifact path, and the request payload hash. Its
SHA-256 is included in the launch handoff and must match the configured policy digest; a prompt
cannot expand this policy.

The sidecar maps to a frozen `WorkerToolPolicy` record with fields
`request_payload_hash`, `allowed_tools`, `write_scopes`, `verification_command`, and
`artifact_path`. It is loaded once before launch and is never replaced during an invocation.

The public result type is a tagged union: `WorkerDispatchSuccess(response: ResponseEnvelope,
handoff: HandoffRecord)` or `WorkerDispatchFailure(failure: TransportFailure,
quarantine: QuarantineRecord)`. Both variants carry the immutable request ID and transaction key;
only the success variant may create the correlated response file, and neither variant can create a
Court or lifecycle record.

### 2. Framed stdio host adapter

Use the existing `runtime/integrations/cline_sdk_host.mjs` framing contract rather than an
interactive terminal. The host receives one canonical `start` frame and emits ordered events.
Only the existing `editor` and `run_commands` capabilities are enabled; MCP settings tools,
skills, subagents, teams, and all undeclared tools are disabled.

The adapter must enforce:

- protocol version and canonical JSON framing;
- invocation ID, session ID, and sequence monotonicity;
- one provider attempt per declared model turn and no hidden retry/fallback;
- pre-execution Python approval for every tool request;
- exact command fidelity, including rejection of extra `cd`, pipes, separators, redirects, or
  arguments;
- profile/qualification path containment and hash stability; and
- terminal-state exclusivity (no events or writes after terminal/failure/cancelled).

The adapter may reuse the SDK host's transport machinery, but generic supervised dispatch and
worker-admission qualification remain separate contracts. Running this transport must not imply
that `DEBT-0058` is repaid.

### 3. Correlated response writer

The dispatcher uses the private `_persist_response_once(...)` helper in
`runtime/integrations/bound_cline_transport.py`; no other component may write a response file.

On a confirmed terminal response, write one `ResponseEnvelope` to the exact response path derived
from the request ID. The write protocol is:

1. serialize canonical JSON and compute payload/response hashes;
2. create a private temporary file with `O_EXCL` and mode `0600`;
3. write all bytes, `fsync` the file, and atomically rename to the response path;
4. `fsync` the parent directory; and
5. create a content-free completion record containing the receipt hash, exit status, and evidence
   references.

If any side effect is uncertain, the dispatcher must not write a successful response. It writes a
typed failure/quarantine record instead and leaves the transaction in the existing reconciliation
state. Pre-existing response files, duplicate request IDs, malformed frames, wrong bindings,
truncation, timeout, and nonzero worker exit are all failures, never successful completion.

### 4. Handoff and observability record

Each invocation produces a secret-blind handoff record containing:

- candidate/recovery branch and exact HEAD;
- request/transaction/session IDs;
- state-root and sandbox paths;
- configured and observed provider/model/family values;
- Cline host, SDK, Node, and qualification hashes;
- ordered event and tool-decision hashes;
- response or quarantine artifact hashes;
- exit code, normalized error, side-effect certainty, and timestamps; and
- the next allowed action or hard-stop reason.

The record is for overseer continuity and later independent audit. It cannot mutate Court counts or
claim a lifecycle result.

### 5. Run-once operator entry point

Add `ops/bound_cline_worker.py` as a thin command-line boundary around
`BoundClineWorkerTransport`. It accepts only absolute state-root, request, worktree, host, and
public model/qualification identifiers. It has no credential, retry, fallback, browser, clipboard,
or interactive-terminal options. It returns exit `0` only for a validated correlated response and
exit `2` for any rejected, quarantined, or uncertain transaction.

## Data Flow

1. PAEOS creates a transaction, immutable request, and immutable policy sidecar under the dedicated
   external state root.
2. The dispatcher validates the request/policy binding and confirms the recovery worktree is clean and
   not `main`/`trunk`.
3. The dispatcher acquires the session lease and starts the host with the frozen tuple.
4. The host emits a `hello` event and ordered provider/tool/terminal events over framed stdio.
5. PAEOS evaluates each tool request before execution and sends exactly one framed decision.
6. The dispatcher records raw framed output as hashes, validates the terminal result, and reconciles
   physical model metadata against the manifest and receipt.
7. On a confirmed response, the correlated response writer persists it once. On any ambiguity, it
   quarantines the raw bytes/hashes and records a reconciliation-required transition.
8. The overseer independently inspects the changed files, tests, evidence, and handoff before any
   subsequent task. A non-GLM route is required for L14/L17 review of GLM-built work.

## Failure Handling

The following conditions halt the invocation and preserve evidence without an automatic retry:

- request/response path outside the state root;
- duplicate request or pre-existing response;
- branch/worktree mismatch or a `main`/`trunk` target;
- provider/model/session/family mismatch;
- qualification or entrypoint hash drift;
- malformed, oversized, out-of-order, duplicated, truncated, or post-terminal frame;
- unauthorized tool, command expansion, spawn/team/skill/MCP-settings request;
- more than one provider attempt for a declared turn;
- timeout, process death, cancellation, nonzero exit, or uncertain side effect;
- response hash or envelope binding mismatch; or
- any attempt to write outside the task allowlist.

The raw failure is retained at a state-root-bound quarantine path. The dispatcher does not retry the
same command or provider call. A later retry requires a new request ID and a new written rationale
from the overseer/operator.

## Security and Governance Invariants

- Builder and auditor are physically decorrelated; a GLM worker cannot audit its own work.
- Worker prose cannot create `WorkerBinding`, Court, lifecycle, or promotion authority.
- State, history, transaction ownership, and tool policy remain local to PAEOS; models are stateless
  compute.
- The recovery worktree is separate from the repository checkout running any existing daemon.
- No browser, clipboard, AppleScript, unbound terminal, provider fallback, or credential disclosure
  path exists in the transport.
- Exact `Sealed | Remanded | Remediated` and `Admitted | Rejected | Remediated` counts remain
  overseer/Court outputs, not transport defaults.
- Antigravity can resume by reading the handoff record and immutable transaction artifacts; it does
  not need the old GUI bridge or a hidden process state.

## Verification Strategy

Implementation must follow TDD, with each behavior demonstrated by a failing test before production
code is written. The focused suite must cover:

1. request, response, transaction, and path binding;
2. duplicate/stale request and response rejection;
3. canonical frame parsing and sequence/terminal enforcement;
4. tool approval ordering and exact command policy;
5. provider-attempt and no-retry/fallback accounting;
6. profile/qualification hash and symlink containment;
7. timeout/process-group cleanup and uncertain-side-effect quarantine;
8. atomic `fsync`/`O_EXCL` response persistence;
9. secret-blind handoff and failure artifacts;
10. refusal of GUI/clipboard/CDP, skills, spawn, teams, and main/trunk actions; and
11. integration with the existing `ChatBridgeRuntime` without creating a second ledger.

Tests use a fake local host and synthetic receipts only. They must not access real profiles,
credentials, providers, browsers, or the user's interactive Cline terminal. Verification includes
focused pytest, changed-path Ruff/Pyright, `git diff --check`, and the full non-gateway suite with
raw output and exit codes preserved.

## Acceptance Criteria

The implementation is ready for overseer review only when:

- a request can be delivered and a response correlated without human copy/paste;
- every invalid/ambiguous condition above fails closed and leaves durable evidence;
- no GUI or clipboard process is launched;
- the worker remains implementation-only and cannot self-ratify or promote;
- the response and handoff are candidate/session/model bound and hash-verifiable;
- the old bridge tests remain green and no legacy launcher is reactivated;
- tests and static checks meet the evidence requirements; and
- the implementation explicitly leaves `DEBT-0058`, `DEBT-0060`, L14/L17, Court, gate seals, and
  SAKG status unchanged pending their independent operational evidence.

This design supplies a safer transport substrate. It does not, by itself, advance the 12/48
accounting or authorize unattended autonomy.
