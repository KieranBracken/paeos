# PAEOS AI-Supervised Autonomy Program Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this program plan-by-plan. A plan
> may begin only when every predecessor gate in this index is committed and independently verified.

**Goal:** Replace the fragile GUI/clipboard control loop with a ledger-derived, fail-closed PAEOS
control plane that can rotate between admitted architect-grade supervisors, confine Cline to
implementation-only work, recover safely from quota and process loss, and eventually integrate
reversible Trace-A changes under a single-use promotion capability.

**Architecture:** The kernel ledger remains the only canonical event history. A deterministic
Execution Layer coordinator derives a query projection, admits supervisor and worker routes,
compiles production work into existing `TaskPackage`/`CapabilityToken` authority, observes
meaningful transaction events, and evaluates later promotion gates. Models propose; the kernel
commits. Browser, clipboard, PID, queue, terminal, and log state are never authority.

**Tech Stack:** Python 3.12, frozen dataclasses, SQLite WAL, Ed25519 capability signatures,
content-addressed storage, subprocess-free pure reducers, pytest, Hypothesis, Ruff, Pyright, Git
plumbing commands, provider-neutral headless adapters.

**Spec:** `docs/superpowers/specs/2026-08-26-paeos-ai-supervised-autonomy-design.md`

**Bootstrap handoff:**
`docs/superpowers/specs/2026-08-28-paeos-gates-b-g-worker-handoff.md`

**Disposable worker prompt:**
`docs/superpowers/handoffs/2026-08-28-cline-glm53-gates-b-g-worker-prompt.md`

## Global Constraints

- Work only in `/private/tmp/paeos-control-plane-recovery-s1-clean` on
  `codex/control-plane-recovery-s1-clean`; the dirty main checkout is out of scope.
- This recovery exception authorizes isolated control-plane repair. It does not authorize a
  merge, rebase, push, main/trunk update, deployment, credential read, or SAKG implementation.
- The Founder remains constitutional ratifier. No plan may self-ratify, classify its own protected
  change as Trace-A, or grant itself bootstrap/promotion authority.
- Ingest `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`,
  `docs/PAEOS_MODEL_ROUTER_INFERENCE_MESH_SPEC.md`, and
  `operations/ENGINEERING_LIFECYCLE.md` at every execution or remand-recovery turn.
- Preserve the seven reviewed transaction states. Dispatch and verification are events, not new
  states. SoftLoop is never substituted for L01-L19.
- Preserve raw failure evidence. Do not automatically repeat an identical failed command, probe,
  dispatch, or side effect.
- `Builder != Auditor` is proven from physical receipts before and after audit dispatch. Unknown,
  opaque, missing, stale, or conflicting lineage is ineligible.
- Correct remands are healthy. Report exact `Sealed | Remanded | Remediated` counts; never optimize
  for a zero-remand target.
- Each plan uses RED -> GREEN -> focused verification -> full applicable gates -> independent L14
  audit -> L17 review. A later plan cannot use an earlier plan's claims in place of evidence.
- Gate A Tasks 1-4 are committed at reviewed baseline `277902c`. Task 5, three live probes, L14,
  and L17 remain incomplete. Later gate design does not discharge these requirements.
- Until Gates B-E are implemented, use the isolated bootstrap execution envelope in the handoff
  specification instead of asking the incomplete chat bridge, transaction loop, or watchdog to
  supervise its own repair.
- Before any live Cline probe, the exposed recovery credential must be rotated/refreshed and the
  old material revoked without reading or logging secret values.
- Before bootstrap integration, repository-wide Ruff/Pyright gates must either be green or be
  governed by an exact Founder-ratified, hash-bound unchanged-debt baseline.

## Authority and Data Flow

```text
Founder ratification / standing envelope
                 |
                 v
Kernel single-writer ledger + CapabilityBroker
                 |
                 v
Deterministic Execution Layer coordinator
        |                 |                 |
        v                 v                 v
Supervisor adapter   TaskPackage broker   Derived projection/watchdog
        |                 |                 |
        v                 v                 v
Architect proposal   Cline implementation  Safe recovery decision
        \_________________|_________________/
                          |
                          v
              independent verification + L14
                          |
                          v
              later single-use ref update only
```

## Ordered Plan Set

The six remaining program gates are B-G. Gate A closure remains a prerequisite where this index
states it; naming B-G as the remaining six does not imply Gate A is sealed.

### Canonical progress ledger: 48 top-level milestones / 54 detailed tasks

Progress is reported against 48 top-level milestones: Gate A has 10, Gate B has 5, Gate C has 7,
Gate D has 7, Gate E has 6, Gate F has 8, and Gate G has 5. Gate C's provider-adapter-registry
plan contains six detailed implementation tasks that are mandatory substages of its seven
top-level milestones; they are retained, verified, and never deleted, but are not counted as
additional top-level milestones. Thus both numbers are valid: **48** is the progress denominator
and **54** is the detailed execution-task count. A milestone is complete only after its applicable
tests, L13/L14/L17 evidence, and disposition pass; implementation or a remand does not earn
completion credit.

At recovery checkpoint `49edd4c` on the isolated branch, the first eight Gate A milestones have
implementation evidence. Gate A milestone 9 is in independent-audit remediation after an explicit
Antigravity `REMAND_WITH_AMENDMENTS`, and milestone 10 is blocked on fresh authenticated probes.
The current strict score is therefore **8/48 complete; 40 top-level milestones remain**.

### Gate A — Route qualification

Plan: `docs/superpowers/plans/2026-08-29-paeos-cline-sdk-admission-adapter.md` (the earlier
worker-admission plan remains historical compatibility context)

Output: three fresh-session disposable Cline probes whose raw receipts prove the full admitted
route tuple. This gate grants no production task authority.

Exit criteria:

- route receipt validation, exact tool mediation, seeded-mutation verification, and A-08 binding
  tests are green;
- credential prerequisite is complete before the first live probe;
- three distinct live probes are admitted without autonomous retry;
- L13, physically independent L14, and L17 records are committed.

### Gate B — Canonical transaction ownership

Plan: `docs/superpowers/plans/2026-08-26-paeos-transaction-fencing-projection.md`

Depends on: no live route; may execute after Gate A's unit implementation, but must finish before
any production dispatch.

Output: ledger-derived transaction projection, atomic cross-process claim comparison, monotonic
fencing, stable idempotency keys, and crash reconstruction.

Exit criteria:

- stale and competing owners cannot commit;
- projection poisoning and crash-gap tests fail closed and rebuild exactly from the ledger;
- an uncertain side effect enters `RECONCILIATION_REQUIRED` and is never replayed.

### Gate C — Interchangeable architect supervision

Plans, in order:

1. `docs/superpowers/plans/2026-08-28-paeos-provider-adapter-registry.md`
2. `docs/superpowers/plans/2026-08-26-paeos-headless-supervisor-adapters.md`

The provider-adapter-registry plan is the six-task detailed substage set nested inside Gate C's
seven top-level milestones; its work is mandatory for the plug-and-play provider requirement.

Depends on: Gate B.

Output: open provider registration with legacy compatibility; provider-neutral supervisor
protocol; versioned admission; physical receipts; durable checkpoints; Codex/Antigravity adapter
wrappers; and degraded Trace-A-only eligibility.

Exit criteria:

- opaque or conflicting lineage is refused;
- a synthetic new provider and supervisor adapter can be registered without coordinator, reducer,
  lifecycle, or audit-policy source edits;
- quota loss in every transaction state preserves durable state;
- one simulated clean adapter rotation and one forced quota-stop/resume pass without replay;
- partial, injected, or out-of-envelope model output is quarantined.

### Gate D — Production worker confinement

Plan: `docs/superpowers/plans/2026-08-26-paeos-taskpackage-worker-confinement.md`

Depends on: Gates A, B, and C.

Output: a frozen L11 contract compiled into an existing `TaskPackage`/`CapabilityToken`, typed
broker operations, provenance-tagged context, pinned binary/profile bindings, exact egress
manifests, and fail-closed OS resource confinement.

Exit criteria:

- route admission alone cannot dispatch work;
- every allowed side effect consumes an exact capability operation;
- scope, symlink, process, disk, network, budget, prompt-injection, and confused-deputy canaries
  are rejected before mutation;
- baseline, candidate, and verifier views are physically separate.

### Gate E — Deterministic liveness and safe recovery

Plan: `docs/superpowers/plans/2026-08-26-paeos-event-watchdog-recovery.md`

Depends on: Gates B-D.

Output: meaningful-event deadlines, diagnostic heartbeats, lease expiry before side effects,
reconciliation after ambiguity, storage back-pressure, and restartable stateless adapters.

Exit criteria:

- no health decision depends on repository mtime, log noise, Chrome, or mere PID presence;
- 120-second soft-stall, 300-second pre-side-effect hard-stall, tool, and task deadlines are
  deterministic policy inputs tested with a fake clock;
- no broad catch/sleep/continue loop can redispatch the same transaction.

### Gate F — Canary ladder, bootstrap, and later promotion

Plan: `docs/superpowers/plans/2026-08-26-paeos-canary-bootstrap-promotion.md`

Depends on: Gates A-E and the static-debt disposition.

Output: hidden falsifier/mutation canaries, exact activation counters, Founder-bound bootstrap
evidence, and a single-use exact-ref promotion controller for later reversible Trace-A work.

Exit criteria before Founder bootstrap disposition:

- three end-to-end Trace-A canaries pass in isolated worktrees;
- clean Codex/Antigravity rotation and forced quota-stop simulation pass;
- zero critical escapes, duplicate side effects, provenance conflicts, missed Z0 canaries, or
  unsafe replays;
- promotion remains mechanically impossible.

Exit criteria after a separate Founder L16 bootstrap integration:

- five reversible Trace-A automatic promotions pass at concurrency one;
- every capability is bound to exact repository, reviewed commit, expected target head, ref,
  disposition, and expiry;
- stale heads block without autonomous rebase; safe health-check failure reverts only the exact
  integration or halts if mechanical safety cannot be proven.

### Gate G — Operational lifecycle revalidation and SAKG resumption

Plan: `docs/superpowers/plans/2026-08-26-paeos-lifecycle-revalidation-sakg.md`

Depends on: Founder bootstrap integration and all applicable Gate F canaries.

Output: an evidence-backed revalidation of actual L01-L19 execution, exact Court dispositions,
auditor decorrelation, debt state, and an explicit SAKG resumption recommendation.

Exit criteria:

- historical AI claims are not accepted as proof;
- each layer is traced to correlated ledger/CAS/test/review evidence;
- missing or vacuous evidence yields REMANDED, not retroactive completion;
- SAKG resumes only within the verified envelope and through a new frozen task contract.

## Mandatory Stop Boundaries

Stop and preserve evidence when any of the following occurs:

- one of the eleven circuit breakers fires;
- a physical identity, policy TTL, or binary hash is missing or conflicts;
- a projection head does not match a verified ledger head;
- a side effect may have occurred but correlation is incomplete;
- a task requests classification reduction, scope expansion, or protected-path mutation;
- builder/auditor physical-family inequality cannot be proven;
- a hidden canary is missed, a seeded mutation is not installed/reached/killed, or evidence is
  vacuous;
- target head changes after review;
- the next action requires credential handling, bootstrap integration, protected promotion, or
  quarantine release not already ratified by the Founder.

## Program Verification

After every plan, record the exact commands, exit codes, artifact hashes, model receipts, and
dispositions. Before any activation claim, run:

```bash
/Users/bob/GitHub/paeos/.venv/bin/python -m pytest -q
/Users/bob/GitHub/paeos/.venv/bin/python -m ruff check .
/Users/bob/GitHub/paeos/.venv/bin/python -m pyright
git diff --check
git status --short
```

Expected: tests pass; static checks are green or match the exact Founder-ratified unchanged-debt
baseline; no unexpected file is staged; the main/trunk ref is unchanged. Do not summarize a
failing command as success.
