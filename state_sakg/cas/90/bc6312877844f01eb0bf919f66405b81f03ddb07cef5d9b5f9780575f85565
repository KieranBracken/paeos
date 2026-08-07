# 03 — Boot Sequence, Shutdown, Crash Recovery (Investigations 6, 7)

Every step cites its forcing clause. There is no "normal startup" step.

## Boot (any process: reconciler, cli, harness)

```
BOOT-1  Locate store root: --store flag, else PAEOS_STORE env, else nearest ancestor
        containing store/genesis-record ref.            ⟵ must be pinned or engineers invent (B-class; pinned here)
BOOT-2  Working-tree recovery: git status on kernel-managed paths (store/**);
        if dirty ⟹ reset store/** to HEAD. NEVER touch other paths.        ⟵ H-06, K4 §11 atomicity
BOOT-3  Genesis verification: read GenesisRecord via meta-schema; verify
        constitutional_basis hashes against spec/ files; load adapter trust roots.
        Missing/invalid genesis ⟹ refuse to start (empty store: only `genesis` may run).
                                                        ⟵ K4 §13, B-03
BOOT-4  Cache audit: liveness reverse index + head index + dependents index present
        and stamped with current HEAD? If not ⟹ rebuild from objects (mandatory
        canonical rebuild path).                        ⟵ D1: caches are never trusted, always rebuildable
BOOT-5  Validator self-check: registry loads; schema artifacts at HEAD parse;
        constitution admission re-verified (cheap; catches manual store tampering
        — detection per parchment clause).              ⟵ K6, H2
BOOT-6  (reconciler only) Acquire the global write lease (H-01). Stale lease
        (dead process): break after timeout T_lease; lease is advisory state in
        store/refs/lease.json — safe because single machine + BOOT-2.
BOOT-7  (reconciler only) Reactor catch-up: one full idempotent pass — compute all
        pending automatic transitions from current snapshot (T1–T5). No cursor,
        no event log.                                   ⟵ H-05, D1
BOOT-8  Enter loop / execute command.
```

## Shutdown
There is no graceful-shutdown protocol and none is permitted to be required: any exit
path must be equivalent to a crash (D1). SIGTERM = SIGKILL semantics. Anything a shutdown
handler would do (flush, checkpoint) indicates illegal buffered state — review-reject.

## Crash recovery matrix

| Failure point | Surviving state | Recovery |
|---|---|---|
| Mid-WRITE (before commit) | last commit | BOOT-2 reset discards partial working-tree writes; proposer retries (M-03) |
| Mid-commit (git object written, ref not moved) | last commit | git atomic ref update guarantees HEAD never points at partial state; orphan git objects are garbage, ignored |
| Mid-reactor-reaction | committed store | BOOT-7 idempotent pass re-derives and re-executes the reaction; duplicate-reaction protection = reactions are WRITEs with `expect` preconditions ⟹ second attempt IDENTITY_CONFLICTs into no-op |
| Mid-SPAWN (agent running) | store + spec worktree | agent is lost (crash-only, D1); goal remains at prior state; budget lease expires ⟹ un-debited (leases are two-phase: reserve at SPAWN, settle at ProposedWrites commit; unsettled reservations expire at boot) ⟵ new pin: two-phase budget lease — required or crashed spawns leak budget (was unspecified; B-class, pinned here) |
| Mid-EXEC | store | sandbox process killed; no evidence emitted; NONZERO/absent both safe (evidence only exists if EXEC completed emission atomically with its WRITE) |
| Power loss | fsync'd commits | git durability semantics; require core.fsync defaults on (pin in store spec) |
| Index corruption | objects | BOOT-4 rebuild |
| Founder deletes store/ history | nothing (parchment) | detection only: BOOT-3/5 fail loudly; no defense exists or is claimed (H2) |

## New pins introduced by this investigation (append to SC register)
- Store-root resolution order (BOOT-1)
- Lease file + timeout semantics (BOOT-6)
- Two-phase budget leases with boot-time expiry of unsettled reservations (crash table)
- fsync requirement (crash table)
