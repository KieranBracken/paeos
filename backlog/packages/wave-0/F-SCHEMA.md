# Worker Package: F-SCHEMA — Schema Fixture Corpus + Golden Bytes

## Purpose
Produce the frozen fixture corpus that every implementation module will be tested against.
These fixtures ARE the executable form of PAEOS-4 §2; after merge they are spec-owned
(changing one is a spec amendment, R§1.13).

## Forcing kernel clause
K4 §2.2–2.7 (schemas) · K4 §12.4-C1 (round-trip) · R §1.2, §1.13.

## Dependencies
None (spec-only). Binding inputs: SPEC-CLARIFICATIONS.md SC-01..SC-06, SC-08, SC-10, SC-12.

## Owned files
```
conformance/fixtures/schema/
  manifest.json                      # index: path → {valid: bool, violates: check_id?, notes}
  artifact/{valid,invalid}/*.json
  goal/{work,incident,decision,amendment}/{valid,invalid}/*.json
  evidence/{execution,verdict,external,classification}/{valid,invalid}/*.json
  policy/{constitution,protocol,skill,role}/{valid,invalid}/*.json
  goldens/*.jcs                      # canonical bytes per valid fixture
  goldens/*.sha256                   # "sha256:<hex>" per golden
```

## File contents that must already exist
`spec/PAEOS-4-kernel.md` (authoritative field lists) · `backlog/packages/wave-0/SPEC-CLARIFICATIONS.md` · COORDINATION.md ULID allocation table.

## Interfaces
- `manifest.json` schema: `[{path, object_type, kind?, valid, violates?, description}]`.
  This is the contract consumed by I-CONST, I-SCHEMA, I-VAL, T-HARNESS.
- Golden naming: `goldens/<fixture-basename>.jcs` / `.sha256`.

## Enumeration rule (mechanical — no judgment permitted)
For each object type T, generate:
1. **minimal-valid**: only REQUIRED fields (per K4 §2 REQUIRED annotations).
2. **maximal-valid**: every optional field populated.
3. Goal: repeat 1–2 **per kind** (work, incident, decision, amendment), including each
   kind-specific payload (K4 §2.5) fully populated in the maximal case.
4. Evidence: repeat 1–2 **per class**; execution class MUST show `actor: syscall` +
   `signature` present; include one fixture with non-empty `basis` chain (2 links).
5. Policy: repeat 1–2 per kind × scope ∈ {kernel, workload:sentium}; skill fixtures
   include a 2-node `requires` DAG and a TriggerExpr per SC-06.
6. **invalid**: for each REQUIRED field of each type/kind: one fixture omitting it
   (`violates: SCH`). Plus one fixture per conditional constraint in K4 §2:
   execution evidence with `actor: agent` (violates A-09/K1-class) · goal with parent but
   no serving_clause · goal kind=decision with assignee_class=agent · amendment payload
   missing falsifier_watch · policy without scar · vicarious scar with hazard_class=
   reversible · skill without trigger · ImmutableRecord with version=2 · prev present at
   version=1 · child.workload ≠ parent.workload.
Count check: manifest MUST report ≥ 70 fixtures; every K4 §2 field name MUST appear in ≥1 fixture (lint below).

## Invariants (for this task)
All IDs from the pinned-ULID table (SC-10); all timestamps SC-04 fixed values; all hashes
SC-02 format; goldens per SC-12 (independent RFC 8785 tool, tool name+version recorded in
manifest header).

## Acceptance tests
- `lint-coverage`: every field named in K4 §2.2–2.7 appears in ≥1 valid fixture (script included in deliverable, `conformance/fixtures/schema/lint.py` or equivalent).
- `lint-manifest`: every file on disk is in manifest and vice versa; every invalid fixture names its violated check.
- Goldens: recompute with the independent tool → byte-identical (CI-runnable).

## Conformance tests validated downstream
C1 (I-SCHEMA), L1 corpus (I-VAL via F-VAL reuse of invalid fixtures).

## Commit boundaries
1 commit: `fixtures: schema corpus + goldens (F-SCHEMA)`. No partial merges — the corpus is atomic.

## Expected outputs
~70–90 fixture files, ~40 goldens, manifest, lint script.

## Forbidden modifications
`spec/**` (any) · adding fields not in K4 §2 · resolving new ambiguities (HALT + report per SPEC-CLARIFICATIONS disposition) · using I-CONST or any repo code to compute goldens.

## Review checklist (reviewer: Chief Implementation Architect)
- [ ] Enumeration rule followed exhaustively (diff fixture list against rule, not against taste)
- [ ] Zero fields present that K4 §2 does not define
- [ ] Every invalid fixture's `violates` id exists in K4 §4/§11 taxonomy
- [ ] Goldens tool independence recorded; spot-recompute 3 goldens
- [ ] Pinned ULIDs match allocation table; no generated ULIDs
- [ ] No new SC-entries needed (else: worker halted correctly?)
