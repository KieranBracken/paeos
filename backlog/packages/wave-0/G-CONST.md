# Worker Package: G-CONST — Constitution Policy Artifacts (K1–K11, D1–D2)

## Purpose
Transcribe the ratified invariants into 13 schema-valid `Policy(kind=constitution)` objects
ready for genesis commit G4. This is transcription + assembly, not authorship: every
statement comes verbatim from K4 §4; every scar and falsifier comes from the tables below.

## Forcing kernel clause
K4 §4 (invariants) · K4 §13.1 (genesis) · K6 (scar+falsifier+firing required) · K10 (CAP) · PAEOS-3 SVK-4.

## Dependencies
F-SCHEMA (fixture-validated Policy shape). Contract dependency on G-CORPUS: the scar IDs
below are a *demand table* G-CORPUS must fulfill (see its package).

## Owned files
```
genesis/constitution/K01.json … K11.json     # Policy(kind=constitution, scope=kernel)
genesis/constitution/D01.json, D02.json      # derived guarantees, marked derived: true in body
genesis/constitution/README.md               # token count vs CAP (SC-09)
```

## File contents that must already exist
F-SCHEMA merged (Policy fixtures define the shape) · SPEC-CLARIFICATIONS.md · COORDINATION.md ULID table (K-policies use `…K01`–`…K11`, `…D01`, `…D02`).

## Interfaces
Each policy body: `{statement, derivation, enforcement_point, failure_mode}` — the four
lines of K4 §4, verbatim. Header fields per K4 §2.7 with `loading: always`.

## Scar assignment table (BINDING — resolves the G-CONST↔G-CORPUS circularity)
Scars are the PAEOS-3.5 findings (incurred during derivation — they are real incidents)
plus Sentium-corpus imports. IDs are pinned; G-CORPUS must emit exactly these:

| Policy | scar refs | scar_class |
|---|---|---|
| K1 | scar:paeos-3.5/F10, scar:paeos-3.5/F11 | incurred |
| K2 | scar:paeos-3.5/F8 | incurred |
| K3 | scar:paeos-3.5/F9 | incurred |
| K4 | scar:sentium/buried-decisions | incurred |
| K5 | scar:paeos-3.5/F6 | incurred |
| K6 | scar:paeos-3.5/F14, scar:paeos-3.5/A-18-hazard | incurred |
| K7 | scar:sentium/founder-bottleneck | incurred |
| K8 | scar:sentium/parallel-merge-incoherence (fallback: vicarious industry scar per SC-08) | per corpus |
| K9 | scar:sentium/runtime-lockin (fallback: vicarious) | per corpus |
| K10 | scar:sentium/prompt-bloat (fallback: vicarious) | per corpus |
| K11 | scar:paeos-3.5/F13 | incurred |

## Falsifier table (BINDING)
| Policy | falsifier statement (watch spec: standing Steward audit) |
|---|---|
| K1 | promotions blocked by K1 are later shown correct >X% of the time with zero caught defects over window W |
| K2 | expiry-driven regressions never precede a real defect over W (pure friction) |
| K3 | decorrelated verification finds zero defects missed by same-family verification over W |
| K4 | append-only storage cost/complexity causes incidents while audit trail is never consulted |
| K5 | compiled-context violations (had they been allowed) would have caused zero divergent behavior |
| K6 | scar-less rules would have prevented incidents that scar-gated admission delayed |
| K7 | founder decision classes recur at undiminished rate despite terminal amendments |
| K8 | serialized integration is the throughput bottleneck while producing zero coherence saves |
| K9 | no second runtime is ever attached and the waist tax bought nothing |
| K10 | context-size economics collapse (see SC/H6) |
| K11 | budget exhaustion incidents are 100% false alarms over W |

## Invariants (for this task)
Total token count of the 13 bodies ≤ 12000 (SC-09); statements verbatim from K4 §4 (diffable);
D1/D2 bodies carry `derived: true` and cite their proofs (K4 §4 D-entries).

## Acceptance tests
- Schema-valid against F-SCHEMA policy fixtures' shape (mechanical diff of field sets).
- Verbatim check: `statement` fields string-match K4 §4 S-lines.
- CAP check: token count script output committed in README.md.
- Full admission check (scars resolve, falsifiers parse) DEFERRED to G-RUN gate (I-VAL required).

## Conformance tests validated downstream
L1 (validator admission), C6 (constitution loads in every compiled context), G-RUN S0-exit.

## Commit boundaries
1 commit: `genesis: constitution artifacts (G-CONST)`.

## Expected outputs
14 files.

## Forbidden modifications
Rewording any statement · adding a 14th policy · changing scar/falsifier tables ·
touching `spec/**` or fixtures.

## Review checklist
- [ ] Statements verbatim (mechanical diff)
- [ ] Scar/falsifier tables applied exactly
- [ ] CAP arithmetic checked
- [ ] `loading: always`, `scope: kernel` on all 13
- [ ] D1/D2 marked derived with proof citations
