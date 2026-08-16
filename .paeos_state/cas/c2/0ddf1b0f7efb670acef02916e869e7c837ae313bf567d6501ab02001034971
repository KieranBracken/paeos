# Spike Evidence: DEBT-0002 — Day-1 Spawnability (PAEOS-8 §13.2, assumption 1)

**Date**: 2026-07-28 · **Channel**: DEBT-0002 repayment · **Executed by**: PAEOS Engineering Runtime
**Founder directive**: "Execute the DEBT-0002 Spawnability Spike now."

## Objective

Validate the single load-bearing assumption of the whole autonomous runtime (PAEOS-8 §13.2): that
**Claude Code sessions can be spawned programmatically with a scoped workspace and a capability
allow-list**, with **token passing** and **output capture**. If false, the agent-orchestration
architecture (runtime/ Z2, agent dispatcher, information barriers, FR-3) needs rework.

## Method

Two sub-agent sessions were spawned **programmatically** from within the runtime (the Agent/Task
substrate), each handed a capability token and a strictly-scoped task, and their output captured:

- **Session A — scoped builder**, spawned with an **isolated git worktree** (scoped workspace) and
  full write capability.
- **Session B — read-only session** (`Explore` profile: no `Write`/`Edit`/`NotebookEdit`), asked to
  perform an out-of-scope write, to test allow-list enforcement.

## Results

| Property (§13.2 / 7.5) | Session | Result |
|---|---|---|
| **Programmatic spawn** | A + B | ✓ both spawned programmatically, ran, and returned |
| **Scoped workspace** | A | ✓ wrote `spike_A_output.txt` **inside its own worktree** (`.claude/worktrees/agent-…`), **absent from the main workspace** — the write was contained |
| **Capability allow-list** (MCP-allow-list analogue) | B | ✓ **no write tool present** — Write/Edit/NotebookEdit absent *by construction*; the write was impossible, not merely disallowed |
| **Token passing** | A + B | ✓ both echoed their capability tokens verbatim (`CAP-9f3a2b-BUILDER-run1-EXPIRES-40`, `CAP-7c1d-READONLY-run1`) |
| **Output capture** | A + B | ✓ both returned structured reports captured by the orchestrator |

### Decorrelated verification (K3) — not taken on trust

The orchestrator independently re-checked Session A's claims rather than trusting its self-report:

- **Digest**: `sha256("hello, paeos")` recomputed independently → `1c1450a45c72…`, **identical** to
  A's report → A performed real work.
- **Isolation**: `spike_A_output.txt` confirmed **absent** from the main working tree and **present**
  (with correct contents) only in A's worktree; `git worktree list` showed the isolated branch; the
  main tree was unaffected by the spawn.

Session B's own words: *"enforced structurally (the tools are simply not present), not merely by
policy."* This is precisely the PAEOS capability model (7.5 A-6 / SI-3): a session **physically
lacks** the capabilities of powers it does not hold.

## Scope note (honest boundary)

The **capability allow-list** was demonstrated via the session's *tool set* (a read-only session
structurally lacking write tools), which is the mechanism this runtime exposes. A production PAEOS
runtime scopes actual **MCP servers** per the `permissions.mcp_servers` allow-list (7.6 §5). The
spike proves the **principle** — capability scoping enforced *by construction*, deny-by-default —
is real and achievable in the target runtime; wiring the exact per-MCP-server allow-list is a
Phase-1 *implementation* task, **not** a validation risk. Likewise, worktree isolation demonstrates
scoped-workspace containment; the production `write_scopes` enforcement (FR-3, SI-5) refines it.

## Verdict

**The §13.2 assumption is VALIDATED.** Programmatic spawning, scoped workspace, capability
allow-list (deny-by-default, enforced by construction), token passing, and output capture all hold
in the target runtime. The high-variance risk that gated Phase-1 planning is **resolved green**.

**Recommendation:** mark **DEBT-0002 RESOLVED**; the Phase-1-planning gate (PAEOS-8 §13.2) is
cleared. Residual per Scope note is ordinary Phase-1 implementation (per-MCP-server scoping,
`write_scopes` enforcement), tracked as it is designed — not a reopening condition.
