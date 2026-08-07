# 02 — Module Dependency Graph (Investigation 3)

Re-derived from scratch against the patched contracts (01_*). R §3's graph survives with
two corrections: a genuine bootstrap cycle found and broken, and one async edge that must
not be a dependency edge.

## Graph (arrows = compile/link dependency)

```
constants                                  (root)
schema        → constants
store         → constants                  (shape-agnostic: NO schema dep — B-04 keeps it dumb)
budget        → schema
liveness      → schema, store
validator     → schema, store, budget, crypto(Ed25519 verify — H-03)
compiler      → schema, store
router        → schema, budget
syscalls      → store, validator, liveness, compiler, budget, spi(types)
reactor       → liveness, validator, syscalls(WRITE client)
reconciler    → syscalls, router
cli, genesis  → syscalls
adapters/*    → spi only
conformance   → all (test-only)
```

## Cycle 1 (found, real): validator ↔ store at genesis
Validator validates objects against schema artifacts **loaded from the store** (schemas
are Policy artifacts, §9.5). But schema artifacts enter the store via WRITE, which invokes
the validator. At genesis the store is empty ⟹ nothing can ever be written.
**Constitutional break (B-03):** the validator carries a **hardcoded meta-schema** capable
of validating exactly two shapes: schema-kind policy artifacts and the GenesisRecord
(sentinel `schema: "sha256:meta.v1"`). The G1+G2 atomic batch is validated by the
meta-schema; everything thereafter by store-loaded schemas. The meta-schema is part of
the kernel spec text (frozen surface), so both independent implementations embed the
same one.

## Cycle 2 (apparent, not real): reactor → syscalls → liveness → (notifies) reactor
This is an event loop, not a dependency cycle: liveness *notifies* the reactor
(in-process queue, H-05 state-driven so notification is an optimization, polling is the
fallback). Rule: **notification edges are never link dependencies**; the reactor compiles
against liveness's pure functions only.

## Cycle 3 (prevented by rule): schema ↔ validator
Schema code must not call validation; validator must not define shapes. The drift-check
(R §1.2: code checked against artifacts) is a conformance test, not a runtime dependency —
placing it in either module would create the cycle. It lives in `conformance/`.

## Corrections to R §3
1. `store` loses its schema dependency (it was listed with a footnote; now definitive —
   store is bytes+refs, period). Consequence: I-STORE can start in parallel with F-SCHEMA,
   relaxing the Wave-1 critical path.
2. `validator` gains a crypto dependency (Ed25519 verify, H-03) — new third-party surface,
   must be pinned in the SPI/constants (same library class as SHA-256).
3. `router` loses its store dependency: route() consumes objects passed in, never reads
   (purity per K4 §7.1); the reconciler fetches. R §3 listed store — wrong.

Topological order for implementation: constants → {schema, store} → {budget} →
{validator, liveness, compiler, router} → syscalls → {reactor, cli, genesis} →
reconciler → adapters. Confirms the P-order spine with the B-03 meta-schema inserted
into validator's P1 scope.
