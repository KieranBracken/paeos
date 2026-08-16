# PAEOS Phase 1 Roadmap — Soft-Loop Execution Substrate

**Status:** DRAFT for founder review (CER-5). Produced by the PAEOS Engineering Runtime, 2026-07-28.
**Grounding:** PAEOS-8 §10 (B1.A–G task rows), §12 (delegation ladder), §157 (Phase-1 goal); PAEOS-7
§8 (phases), 7.6 §5/§8 (TaskPackage + MCP contracts), PAEOS-9/9A (context compiler). Derived, not
invented (CER-6).

## 1. What Phase 1 is

**Goal (§157):** *one autonomous end-to-end run* — Claude Code agents (Planner / Builder / Verifier
/ Adversary) take an intake to a **sealed, court-passed, adversary-reviewed** change, behind **real
information barriers**, with **scars written**, and triage fast/full path working.

**Ladder position (§12):** Phase 1 climbs **R1 → R2 → R3**:
- **R1→R2 (Assisted):** a Claude Code Builder+Verifier produce a *sealed change under human gates*.
- **R2→R3 (Supervised autonomy):** *one unattended run reaches `SEAL` needing only a human signature.*

**Now unblocked:** DEBT-0002 (spawnability) is validated & sealed — scoped programmatic agent
sessions are real, so the execution substrate is buildable.

**The invariant (§12):** autonomy grows **only in `runtime/` (and `mcp/`)** — Z2, untrusted. The
kernel is **frozen**; any `kernel/`/`constitution/` change is always HARD-LOOP + human-signed
(7.5 A-2). No Phase-1 task modifies the TCB except via the amendment path.

## 2. Task breakdown (the B1.x groups)

| Task | What it builds | Founder-named component | Dep | Exit criterion (sealed) | Lead threat |
|------|----------------|-------------------------|-----|-------------------------|-------------|
| **B1.A** | **MCP servers** in `mcp/` — constitution / ledger / memory / artifacts / court, capability-gated (7.6 §8) | *MCP integration in `mcp/`* | Phase 0 ✓ | Each server exposes only its 7.6 methods; **ledger `append` NOT exposed**; unauthorized method denied | T1 |
| **B1.B** | **Agent dispatcher + `runtime/claude_code.py` + Task-Package Context Compiler** — compile context (PAEOS-9/9A) into a `TaskPackage` (7.6 §5), spawn a scoped Claude Code session, parse `TaskResult` | *task-package context compiler* + *agent runtime in `runtime/`* | B1.A | A Builder session writes only its `write_scopes`; result artifacts land in CAS; trace persisted | T9 injection; scope-escape |
| **B1.E** | **Verification Court** — deterministic re-run + mutation; wires the B0.14 canaries to a *real* detector | *evidence collector* | B1.B | Court reproduces every claim; unmet claim ⇒ remand; **canary caught** | T2 reward-hack |
| **B1.D** | **Information-Barrier Manager + Review harness** — isolated adversary that sees only the sealed bundle | (part of *soft loop*) | B1.B | Adversary session provably cannot read builder context (SI-5, FR-3) | T1 self-exfil |
| **B1.C** | **Planner / Builder skills + roles** for stages 7/9/10 (design → plan → impl) | (part of *agent runtime*) | B1.B | An intake produces design → plan → branch-impl, each a bound artifact | — |
| **B1.G** | **Triage cost gate** (fast/full path) + per-goal budget (K11) | (part of *soft loop*) | B1.B | Routine goal → fast path; kernel-touching → full path; budget breach halts | T6 triage-inflation |
| **B1.F** | **Scar store** + signature matching; injection at stages 0/7/8/11 (learning) | (part of *soft loop*) | B1.A | A written scar auto-injected on a matching goal; broad-signature scar quarantined | T3 poison |

**The "initial soft reconciliation loop"** = a `runtime/lifecycle_runner.py` that pulls a goal,
routes it (B1.G triage), dispatches agents (B1.B), collects court-verified evidence (B1.E), passes it
through the **already-built Phase-0 gate (B0.6)** and **seal (B0.9)**, writing scars (B1.F). It is not
a new task — it is the *composition* of B1.B + E + G + F over the sealed Phase-0 kernel, and its
first unattended success is the **R2→R3** exit.

## 3. Recommended build order (DAG-honest)

```
B1.A (MCP)  →  B1.B (dispatcher + context compiler)  →  B1.E (court)  →  B1.D (barriers)
                                                     →  B1.C (roles)   →  B1.G (triage/budget)
B1.A ─────────────────────────────────────────────  →  B1.F (scars)
                                                     →  INTEGRATE: soft-loop run → R2→R3 seal
```

1. **B1.A** first — the MCP narrow waist every agent reaches the kernel through.
2. **B1.B** is the keystone — it *productionizes the DEBT-0002 spike* (scoped spawn + `write_scopes`
   + trace) and builds the context compiler. Everything else dispatches through it.
3. **B1.E** next so evidence is *court-verified* (real reproduction) before roles produce it.
4. **B1.D** barriers before the adversary runs; **B1.C** roles; **B1.G** economics; **B1.F** learning.
5. **Integration** — the soft-loop run that takes one intake to a human-signed seal (R2→R3).

## 4. Debts that become load-bearing in Phase 1 (sequence these)

- **DEBT-0005 (evidence-reproduction sandbox)** — becomes **blocking at B1.E**: the court reproduces
  *agent-produced* commands, so the OS sandbox (7.5 §T2/EXEC) must land before/with B1.E. **Repay at
  B1.E.**
- **DEBT-0003 (durable ledger backend)** — real multi-session runs need cross-process persistence.
  **Repay early (before/with B1.B)** so dispatched sessions share one durable ledger.
- **DEBT-0004 (constitution corpus population)** — the court/adversary (B1.E/D) and scars (B1.F) query
  real Z0 clauses; and genesis needs the frozen corpus. **Founder-legislated; schedule before B1.E
  consumes real constitutional queries.**
- **Standing cautions (§10):** FastAPI read API (operator control plane); event `schema_ver` migration
  policy. Assign within Phase 1.

## 5. Governance (unchanged)

- Every B1.x task runs the full lifecycle: L17 Constitutional Review (CER-4) + founder ratification.
- `runtime/` + `mcp/` are **Z2** — not LOC-budgeted like the kernel, but MCP access is
  **capability-gated** (the narrow waist), and agents hold **no ambient authority** (7.6 §5).
- **Kernel frozen:** F2 stays HARD-LOOP for any `kernel/`/`constitution/` touch; autonomy never grows
  in the TCB.
- Ed25519 keys move to the kernel process env (never to an agent), founder owns rotation (7.5 A-5).

## 6. Recommendation

Approve this ordering, then begin **B1.A (MCP servers)**. First checkpoint for founder ratification:
**B1.B green** = the DEBT-0002 spike productionized into a real dispatcher — the R1→R2 rung within
reach. Await founder approval before starting implementation (CER-5).
