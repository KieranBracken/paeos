# L17 Constitutional Review — Phase 3 Milestone 1: Live Fully-Autonomous Self-Hosting Run

**Date**: 2026-08-01 · **Rung**: R4 → **R5** (autonomous) · **Author role**: Auditor (recommends;
the founder ratifies — CER-5). **Status**: presented for founder ratification. **Not merged.**

## 1. What was directed

> "Run the live fully-autonomous self-hosting deployment run (`claude --mcp-config` → CourtServer
> → pool → seal) driven by `ContinuousScheduler` under the Economic Governor."

The culminating Phase-3 milestone: wire the WorkerTransport trilogy (R5.1–R5.3), the
`ContinuousScheduler` (Stage-19 RESTART), and the `EconomicGovernor` (K11) into **one live loop**
in which a real `claude` session submits its **own** probative evidence to the court over MCP, and
the loop reaches a **genuine, adversary-cleared seal** — with no evidence authored for it.

## 2. Outcome — GENUINE AUTONOMOUS SEAL (verified, not asserted)

A contained live run (`ops/autonomous_run.py`, clean sandbox workspace) sealed. Verified by:

- **K3** `Ledger.verify_chain()` → OK; the ledger holds `goal_created` → **`SealCommitted`**.
- The `SealCommitted` event carries an **`adversary_ref`** + an **Ed25519 `attestation`**. Because
  **B2.K** remands the seal on an adversary BLOCK, a `SealCommitted` event *is* proof the isolated
  adversary returned **PASS** over the sealed bundle.
- The court pool for the sealed run contained **only the Builder's** two evidence records
  (`builds`, `unit`), each **submitted by the live session via the `submit_evidence` MCP tool** —
  the discriminating one being `python3 -c "import lib.greet; assert lib.greet.greet()=='hello-paeos'"`.
- The **`ContinuousScheduler`** pulled the goal and the **`EconomicGovernor`** charged one
  full-weight allocation under **K11** (4.0M → 3.6M tokens remaining), halting cleanly on
  `source-exhausted` (no spin — §9.4).

The full chain ran end to end: `ContinuousScheduler` → `EconomicGovernor` (admit + charge) →
`SoftLoop` → live `claude` Planner (design + plan) → live `claude` Builder (wrote `lib/greet.py`,
**submitted its own evidence via `claude --mcp-config` → `court_server.py` → pool**) → `EvidenceSource`
→ Court reproduces each command in a workspace-with-change (B2.N) → probative gate (B2.O) → isolated
Adversary PASS (B2.K) → **seal** (Ed25519, K3-chained).

## 3. The changes (exactly two files — minimal wiring + one correctness fix)

- **`ops/autonomous_run.py`** (new, deployment composition; not in the TCB, not unit-tested):
  `McpWorkerTransport(pool)` → writes `mcp_config()` → `ClaudeCodeRuntime(mcp_config_path=…)` →
  `SoftLoop(evidence_source=transport)` wrapped as `run_one` → `ContinuousScheduler` under
  `EconomicGovernor`. Imports adapters from `runtime/transports/`, which is why it lives in `ops/`,
  outside the AI-010 Port-Independence boundary.
- **`runtime/integrations/__init__.py`** (live adapter): thread `mcp_config_path` into
  `ClaudeCodeRuntime` + `claude_cli_invoker` (adds `--mcp-config` and allows
  `mcp__paeos-court__submit_evidence`); a generated **evidence-submission prompt section** that
  gives the Builder its `run_id` and the probative-command convention; and **the correctness fix
  below** — all scoped to `Role.BUILDER`.

**No kernel change. No constitution change.** F1 GREEN (kernel 2644/20000 LOC), AI-010 Port
Independence still holds (the core imports zero vendor SDK; only `ops/` and `runtime/transports/mcp/`
touch MCP), ruff/pyright clean, 336 tests pass.

## 4. The architectural finding (CER-1 — the run falsified an assumption)

The first sealed-path attempts remanded, and the remand exposed a **real** latent coupling, not a
harness quirk:

> **All stages of a run share one `run_id`.** With `--mcp-config` handed to *every* session, the
> Planner's `design_coherent` / `plan_executable` citations landed in the **same** `run_id` evidence
> pool as the Builder's `builds` / `unit`. `evidence_for(run_id)` then handed the court **all four**,
> and the court tried to reproduce the Planner's citations in the **Builder's** verification workspace
> (which contains only the builder's `changed_paths`, never `design/` or `plan/`) → guaranteed REMAND.

**Derivation of the fix (not an invention):** the court is, by existing law, the **Builder's**
evidence channel — the `SoftLoop` adjudicates *the builder's artifact* against *the builder's*
verification workspace (B2.N). Planner artifacts are adjudicated by their own stage gates, never the
court pool. The MCP flow had accidentally widened that channel to every stage. The fix **restores**
the intended boundary: `--mcp-config` and the submit-evidence prompt are scoped to `Role.BUILDER`.
This removes behaviour the MCP wiring added; it weakens nothing that was previously enforced.

**Forward pointer (not filed — CER-6):** *should* the Planner's design/plan coherence be
court-adjudicated (probative design), rather than self-attested citation? That is a genuine design
question (it would need a per-stage evidence pool + a stage-appropriate verification workspace), but
it is **new mechanism**, out of scope here. Noted for a future IP, not implemented.

## 5. Honest mistake log (what remanded, and why — the R5 analogue of the R4 journey)

1. **run-1 → "builder produced no artifact"**: a flaky live Builder session left no write. Non-
   determinism, not a defect; the next run wrote correctly. (Kept as evidence the loop fails closed.)
2. **run-2 → "court remanded"**: the multi-stage `run_id` pool contamination above — the **one real
   architectural finding**. Fixed by scoping the court to the Builder.
3. **run-3 → "court remanded"**: **my** contrived sandbox seeded `lib/__init__.py` with invalid
   Python (`placeholder`), so `import lib` raised in the court's full-repo verification workspace
   (the Builder's sandbox never had that file, so its command passed *there*). A **test-harness**
   bug — and a clean demonstration that B2.N correctly rejects a command that does not reproduce in a
   clean repo. Fixed the seed; **no PAEOS change**.
4. **run-4 → SEALED**: genuine seal, verified as in §2.

## 6. Recommendation

Ratify Phase 3 Milestone 1 as **R5 achieved (live, autonomous, adversary-cleared)**. On ratification:
merge the two files ff-only to `main`, verify remote CI green, and tag. The scoping fix in §4 is the
substantive constitutional content; the rest is deployment wiring.

Deferred (unchanged from prior reviews; not blockers): governor **actual-spend metering**
(`RunOutcome.cost` + refund vs. today's ceiling-charge), multi-goal concurrency + isolation, and the
per-stage-evidence-pool question in §4.
