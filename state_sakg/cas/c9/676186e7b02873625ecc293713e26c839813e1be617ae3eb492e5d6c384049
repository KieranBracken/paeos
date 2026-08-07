# 05 — Storage Model & Repository Topology (Investigations 2, 4)

This file IS the binding storage spec (resolves B-04, H-06, H-07). Every path exists
because a clause forces it; anything else in the tree is a defect.

## Repository layout (final; corrects R §2)

```
paeos/
  spec/                    ⟵ K4 §13.1 constitutional_basis (hashed at genesis; read-only after)
  kernel/                  ⟵ R §1.1–1.10, 1.15 (one dir per module of 02_MODULE_GRAPH)
  adapters/spi/ null/ claude-code/       ⟵ K4 §12, R §1.11–1.12
  conformance/fixtures/ l0../ harness/   ⟵ K4 §12.4, R §11 (+ fault/ per 04 ✚)
  genesis/                 ⟵ K4 §13, Wave-0 packages (inputs only; single-shot)
  cli/                     ⟵ K4 §14.1
  backlog/                 ⟵ PAEOS-5 (goal-tree source until G-RUN imports it)
  reviews/                 ⟵ K6 scars (3.5, 5.5 corpora are scar sources)
  store/                   ⟵ K4 §2.1 — THE kernel-managed namespace (H-06 reset scope)
    genesis-record.json         # sentinel presence = initialized store (BOOT-1/3)
    objects/<sha256-hex>.json   # kernel-hash-addressed; git hash irrelevant (B-04)
    objects/blobs/<sha256-hex>  # raw content (SC-01 ref target)
    refs/heads.json             # object-id → head version hash
    refs/trunks.json            # trunk name → integrator lease + tip
    refs/checks.json            # live Check inventory (B-07)
    refs/dependents.json        # derived (H-08) — cache, rebuildable
    refs/lease.json             # write lease (BOOT-6)
    index/                      # liveness reverse index — cache, rebuildable (BOOT-4)
```

Git mapping: everything above lives on branch `main` of one repo. Speculation isolation
= git worktrees on `refs/paeos/spec/<goal-id>/<n>` containing WORK FILES ONLY (H-07);
kernel objects never appear on speculation refs. `store/**` mutations occur only inside
WRITE commits. One repo total: forced by self-hosting (K4 §13.3 — kernel code must live
in the governed store).

## The four persistence classes (Investigation 4 — exhaustive)

| Class | Contents | Mutability | Regeneration |
|---|---|---|---|
| **Immutable objects** | `store/objects/**` | append-only, never rewritten (K4) | never — they are the truth |
| **Refs** | `store/refs/*.json` (except dependents) | mutated only inside WRITE commits | replayable from git history |
| **Caches** | `store/index/**`, `refs/dependents.json` | freely rebuilt | BOOT-4 canonical rebuild from objects; NEVER authoritative (D1) |
| **Working state** | speculation worktrees | disposable | none — loss is safe (crash-only agents) |

Signed: execution-class Evidence only (Ed25519, adapter keys from genesis record) —
signature travels inside the object, verified by validator check `SIG` (H-03).
Indexed: reverse read-set (liveness), head map, dependents. Nothing else may be indexed
without a canonical-rebuild proof in conformance.

## What is explicitly NOT on disk
Event logs/cursors (H-05) · agent memory of any kind (K5/D1) · configuration outside the
store (parameters are GenesisRecord fields; env vars limited to BOOT-1 store location) ·
lock files beyond `refs/lease.json`.

## Durability pins
`core.fsync` on (03) · commit granularity = WRITE batch = ref transaction ·
snapshot token = git commit id, opaque, never parsed by kernel code.
