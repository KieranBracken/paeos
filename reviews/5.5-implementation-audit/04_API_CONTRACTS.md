# 04 — API Audit (Investigation 5)

Complete public-surface enumeration. Anything not listed here does not exist; any module
exposing more is a defect. ✚ = interface that was MISSING from the corpus (defect, now pinned).

## Store API (internal to kernel; not a syscall)
```
put_objects(batch: [(path_hash, bytes)]) → staged
update_refs(manifest_deltas) → staged
commit(staged, message) → snapshot_id            # atomic; the ref transaction
get(hash) → bytes | NOT_FOUND
read_ref(namespace) → manifest
snapshot() → snapshot_id ; at(snapshot_id) → StoreView
✚ rebuild_indexes() → report                     # BOOT-4 canonical rebuild (was implicit)
✚ managed_paths() → [glob]                       # H-06 reset scope (was undefined)
```

## Kernel function APIs (pure)
```
validate(batch, StoreView) → ok | Violation(check_id)        # registry-ordered
live(evidence_hash, StoreView) → bool                        # K2
✚ regression_target(goal, StoreView) → LatticeState          # T1 (was implicit in prose)
✚ pending_reactions(StoreView) → [Reaction]                  # H-05 state-driven reactor (was event-framed)
compile(goal_hash, role, StoreView) → Context
route(goal, classification, policies) → DispatchRecord       # no store access (02 correction)
✚ conserve(parent_budget, child_allocs) → ok | violation     # K11 shared predicate (was ambient)
```

## Syscalls (K4 §11, frozen; patched per 01)
```
READ(selector, snapshot?)         selector = pinned DSL (B-08)
WRITE(objects, expect)            provenance stamped server-side (B-02); status/budget
                                  fields kernel-maintained (B-01)
EXEC(check_ref, worktree, lease)  ✚ signature: takes a Check artifact ref + worktree,
                                  not a raw cmd (B-07) — K4 §11 amendment required
SPAWN(role, goal, lease)          two-phase budget lease (03); worktree provisioning (B-04)
```

## Adapter SPI (5 functions, F-SPI) — survives audit with one change
`sandbox_exec` gains `workdir: worktree_ref` parameter (B-07). Otherwise frozen as packaged.

## Reactor interface
```
✚ react(Reaction, lease) → WRITE                 # each reaction independently committed,
                                                 # expect-guarded (03 idempotence)
```

## CLI (founder ABI, 5 verbs — unchanged)
`author | resolve | inject | curate | audit` — audit gains subcommands
✚ `audit conservation | audit queue | audit interventions | audit store` (BOOT-5 manual run).
Still zero writes from audit.

## Harness API
```
run(adapter, suite: C1..C8 | L0..L5) → report
✚ fault(plan) → controlled kill schedule          # C5 needs an injection API — missing
                                                  # from corpus AND from PAEOS-5 backlog (see 07)
```

## Schemas that must exist but were never written (H-04) — now demanded from F-SCHEMA
`SpawnRecord {agent, role, goal, context_manifest_ref, lease, adapter, model}` ·
`DispatchRecord {goal, classification_ref, protocol, fanout, evidence_reqs, child_budget, escalate}` ·
`FiringEvent {at_snapshot, goal, effect}` ·
`GenesisRecord` (K4 §13.1 field list, as schema) ·
`Check` (B-07) · ref-manifest formats (B-04) · lease file (03).

## Verdict on the API layer
No API should disappear; two must change shape (EXEC, sandbox_exec); nine were missing.
All misses are contract-level — none required new architecture, which is the difference
between an incomplete spec and a wrong one.
