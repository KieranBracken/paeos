# R4 Self-Hosting Runbook (PAEOS-8 §12 R4)

**Purpose.** Drive a real backlog item through PAEOS's own soft loop with the **live** `claude`
CLI as the agent, producing a **sealed** change to PAEOS's own `runtime/`. This closes the §12
delegation ladder step **R3 → R4** (supervised autonomy → self-hosting).

This is a **deployment action**, not a test. The single live step — spawning a real `claude`
session — needs authentication and a target working tree, and by nature cannot run inside the CI
sandbox. Everything *around* it (parse, compose, gate, court, seal, ledger) is exercised by the
unit suite (`tests/runtime/test_selfhost.py`, `tests/runtime/test_selfhost_cli.py`).

The command:

```
paeos self-host <backlog.json> [--db ops/state/ledger.db] [--keys ops/keys/kernel_ed25519.key]
```

Wired in `runtime/selfhost.py` (`parse_backlog` → `run_backlog` → `outcome_summary`) and
`cli/paeos.py` (`_self_host`, the `self-host` subcommand). The driver composes a `SoftLoop` over a
**durable** SQLite ledger (DEBT-0003) and the **live** `ClaudeCodeRuntime` (B2.A), runs each
`Intake` through `SelfHostRunner`, and prints a JSON summary. Exit `0` iff every intake **SEALED**;
`2` otherwise.

---

## 1. Preconditions (operator / founder)

- [ ] **Authenticated `claude` CLI.** `ClaudeCodeRuntime` shells out to the real `claude`
      executable (B2.A `claude_cli_invoker`). Confirm `claude` is on `PATH` and logged in.
- [ ] **Signing key present.** `--keys` (default `ops/keys/kernel_ed25519.key`) resolves via
      `load_or_create_signing_key`. The key is **gitignored, F3-enforced, never committed, never
      handed to an agent** (7.5 A-5). If absent, the loader mints one — back it up out-of-band.
- [ ] **Durable ledger path writable.** `--db` (default `ops/state/ledger.db`) and its parent are
      created on first run; the run's CAS lives in `<db_parent>/cas`. The ledger is **append-only
      and single-writer** (FR-5) — one `self-host` process at a time.
- [ ] **Read scope for the agent.** The live agent needs to *see* the repo it edits. Configure the
      `claude` session's directory access (`--add-dir` / the invoker's read-scope) to the PAEOS
      working tree so the Builder can read the files its plan write-scopes name.
- [ ] **On a branch, never `main`.** A self-hosted change to `runtime/` is F2-SOFT, but merging it
      is still founder-ratified. Run on a feature branch; the seal authorizes nothing on `main`.

## 2. The backlog file

A JSON **list** of intakes. Each intake (see `runtime/selfhost.py` docstring):

```json
[
  {
    "objective": "add helper foo() to runtime/util.py",
    "changed_paths": ["runtime/util.py"],
    "plan_write_scopes": ["runtime/util.py"],
    "goal_signature": "domain:runtime,task:util",
    "verifiable": true,
    "reversible": true,
    "builder_evidence": [
      {
        "claim_id": "builds",
        "kind": "TEST",
        "command": "uv run pytest tests/runtime/test_util.py -q",
        "artifact_hash": "<sha256 of the produced artifact>",
        "exit_code": 0,
        "stdout": "..."
      }
    ]
  }
]
```

Field notes:
- `changed_paths` drives the kernel classifier (K5 weight-class). Touching `kernel/` or
  `constitution/` makes the run **KERNEL_TOUCHING** → HARD-LOOP; **do not** self-host kernel edits.
- `plan_write_scopes` bounds what the agent may write (barrier `ScopeViolation` if it strays).
- `builder_evidence` is the **staged** evidence path: the driver carries the builder's evidence so
  the court can adjudicate it deterministically. **Malformed input raises `ValueError`** at parse
  time (before any live call), so a bad backlog fails fast and cheap.
- Omitted `verifiable` / `reversible` default to `true`.

## 3. Run

```
paeos self-host ops/backlogs/first-r4.json
```

The driver runs each intake through one **shared** `SoftLoop`, so scars accumulate across the
backlog (soft-loop self-improvement) and every run is recorded on the one shared ledger. Output is
a JSON array of `{goal_id, status, detail, seal_hash}`.

## 4. R4 acceptance

R4 is met when **one real backlog item produces a sealed change to PAEOS's own `runtime/`**:

- [ ] `status == "SEALED"` and `seal_hash` non-null for the target intake.
- [ ] The seal record is on the durable ledger; `paeos replay` reconstructs the goal projection and
      `verify_against_head` passes (K3 — recompute, don't trust).
- [ ] The written artifact under `runtime/` matches its `artifact_hash` (content-addressed).
- [ ] The change was produced by a **live** `claude` session (not the scripted test runtime).

On acceptance: present the sealed change for founder ratification (F2-SOFT merge → CI → tag), then
merge ff-only.

## 5. Known remaining refinement (not a blocker for R4)

**Live evidence flow via the court MCP.** In this runbook the `Intake` *carries* the builder's
evidence (the deterministic, testable path). In a fully-autonomous run the live Builder session
produces evidence and submits it through the **court MCP** (`CourtServer`, B1.A) rather than having
it pre-declared in the backlog. Wiring `SoftLoop` to pull evidence from the court instead of the
`Intake` is the last live-integration step toward **R5** (autonomous); it changes only the evidence
*source*, not the composition or the learning loop (B2.B Observation 1). R4 acceptance above does
not depend on it — the sealed `runtime/` change is real either way.

## 6. Rollback

The ledger is append-only; a bad self-hosted change is **remanded, not merged**. If a run seals a
change you do not want, simply do not ratify/merge it — nothing reached `main`. The feature branch
and its `ops/state/ledger.db` can be discarded. No destructive rollback of the ledger is ever
performed (K1/FR-5).
