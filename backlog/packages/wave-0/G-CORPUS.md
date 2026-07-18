# Worker Package: G-CORPUS — Scar Corpus Import (Sentium + PAEOS-3.5)

## Purpose
Convert the two pre-existing failure corpora — the Sentium excavation and the PAEOS-3.5
review findings — into schema-valid scar artifacts and seed taste exemplars for genesis
commit G1/G7. This satisfies I7/K6 for every genesis policy.

## Forcing kernel clause
K4 §13.1 (scar_corpus) · K6/A-18 (scars, vicarious class) · PAEOS-3 §1.2 (scarred, not arbitrary) · SC-08 (ExternalScar schema).

## Dependencies
F-SCHEMA (artifact shape). **Founder input precondition:** location of the Sentium
excavation materials must be supplied at assignment time; this package cannot start
without it. (PAEOS-3.5 findings are already in `reviews/3.5-adversarial/`.)

## Owned files
```
genesis/corpus/paeos-3.5/scar-*.json      # one per demanded ID (see below)
genesis/corpus/sentium/scar-*.json
genesis/corpus/taste/seed-*.json          # taste exemplars (K4 §14.1 namespace seeds)
genesis/corpus/index.json                 # id → path, hazard_class, scar_class
```

## File contents that must already exist
`reviews/3.5-adversarial/01..07*.md` · founder-supplied Sentium corpus · F-SCHEMA merged.

## Interfaces
Each scar: Artifact per SC-08 (`application/x-paeos-scar+json`), body
`{source, date, description, failure_mode, hazard_class}`. IDs per COORDINATION ULID
table; `index.json` maps the symbolic ids (`scar:paeos-3.5/F10` …) to ULIDs.

## Demand table (BINDING — from G-CONST; these MUST exist)
`scar:paeos-3.5/{F6,F8,F9,F10,F11,F13,F14,A-18-hazard}` — extract each from the review
files: description = the finding's Evidence section, failure_mode = its "why it matters".
`scar:sentium/{buried-decisions, founder-bottleneck, parallel-merge-incoherence,
runtime-lockin, prompt-bloat}` — mine from the Sentium corpus using the rubric below.
If a demanded Sentium scar has no genuine incident in the corpus, DO NOT invent one:
emit it as `scar_class: vicarious` with an industry-documented source (A-18 path), and
record the substitution in index.json. Fabricated scars are the worst possible defect.

## Mining rubric (for additional, non-demanded Sentium scars — cap: 20)
An incident qualifies iff the corpus documents: (a) rework caused by a lost/undocumented
decision, (b) a defect that survived review, (c) founder intervention that repeated,
(d) architectural reversal and its cost. Each extra scar: same schema, `hazard_class`
judged by revert cost. Beyond scars: extract up to 10 taste exemplars — artifacts the
founder marked good/bad with a stated reason — into `taste/seed-*.json`
(`{exemplar_ref_or_inline, verdict: good|bad, reason}`).

## Invariants
No scar without a source pointer into real material · demanded IDs complete ·
`vicarious` only where `hazard_class: irreversible` OR explicitly substituting per
demand-table rule (flag in index).

## Acceptance tests
- `index.json` covers every demanded ID; every file schema-valid against F-SCHEMA.
- Traceability spot-check: 5 random scars → their source passages exist.
- G-CONST cross-check: every scar ref in G-CONST resolves through index.json.

## Conformance tests validated downstream
G-RUN S0-exit (constitution admission) · S3 Steward first mining run consumes this corpus.

## Commit boundaries
2 commits: `corpus: paeos-3.5 scars` · `corpus: sentium scars + taste seeds`.

## Expected outputs
8 review scars + 5–20 Sentium scars + ≤10 taste seeds + index.

## Forbidden modifications
Inventing incidents · editing review files · resolving schema ambiguities locally (HALT rule).

## Review checklist
- [ ] Every demanded ID present; substitutions flagged
- [ ] Random-sample source verification (5 scars)
- [ ] No fabricated content (compare description text against sources)
- [ ] hazard_class assignments defensible (reviewer judgment)
- [ ] Taste seeds carry founder-attributable reasons only
