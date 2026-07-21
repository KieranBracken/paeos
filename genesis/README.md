# genesis/ — The Bootstrap Record

The permanent, auditable record of how PAEOS came into existence. Per PAEOS-3, the
genesis authority is *recorded, not hidden* — every founding act is written into the same
store it creates, marked with genesis provenance, so the system can forever audit its own
origin. This directory is that record's staging area and runbook.

**Status: specification, not yet executed.** Genesis (G-RUN) is Wave-5 in the backlog,
gated behind the three kernel amendments from `reviews/5.5-implementation-audit/`
(B-01, B-02, B-06+EXEC) and the reissued Wave-0 packages. Nothing here should be executed
until that gate clears.

## Two kinds of thing live here — do not confuse them

1. **The runbook** (`G1.md … G7.md`) — human-readable *procedure* for each genesis WRITE
   batch: forcing clause, what it writes, its inputs, its exit evidence. Markdown. These
   are audit documents; they are what makes the bootstrap reproducible.
2. **The inputs** (`constitution/`, `corpus/`, `roles/`, `protocols/`, `root-goal.json`) —
   the actual JSON kernel objects each batch will WRITE. These are JCS-serialized,
   schema-valid Goal/Policy/Evidence objects (PAEOS-4 §2), the things that get
   content-hashed into the store. **They do not exist yet** — Wave-0 workers (G-CONST,
   G-CORPUS, G-ROLES, G-ROOT) produce them, after the amendment gate. These subdirectories
   are their deposit targets, and their paths match the Wave-0 worker packages exactly.

> Type discipline (why this separation matters): the genesis *record* that PAEOS-4 §13.1
> pins is a JSON object, not a markdown file. `G1.md` documents it; it is not it. Writing
> the genesis record as prose would produce an object the validator's meta-schema cannot
> hash or admit (PAEOS-5.5 B-03).

## Layout

```
genesis/
  README.md                     # this file
  constitutional-basis.sha256   # frozen-corpus hashes → G1's constitutional_basis (REAL, computed)
  kernel-spec.sha256            # kernel-spec integrity (audit convenience, not a §13.1 field)
  G1.md … G7.md                 # the batch runbook (sequence per PAEOS-4.5 §12, amended by B-03)
  constitution/                 # ← G-CONST: K01.json…K11.json, D01/D02.json
  corpus/                       # ← G-CORPUS: scar-*.json, taste seeds, index.json
  roles/                        # ← G-ROLES: role-builder.json, …
  protocols/                    # ← G-ROLES: proto-direct.json, …
  root-goal.json                # ← G-ROOT (FOUNDER task; not yet authored)
```

## The genesis commit sequence (source: PAEOS-4.5 §12, as amended)

| Batch | Writes | Amendment note |
|---|---|---|
| **G1+G2** | GenesisRecord **and** schema Policy artifacts, as ONE atomic WRITE | PAEOS-5.5 **B-03**: merged and validated by the meta-schema sentinel — an object cannot pin a schema that does not yet exist, so G1 cannot precede G2 |
| G3 | Validator registered; first Evidence = validator run over G1–G2 | first executable check (PAEOS-3 SVK-3) |
| G4 | Constitution policies K01–K11 (+D01/D02) | each scarred + falsifiable (K6) |
| G5 | Role policies + 4 genesis protocols | naive by construction (PAEOS-3 SVK-7) |
| G6 | Root Goal + appetite Budget | founder act (PAEOS-3 SVK-8) |
| G7 | Founder-ABI refs (decision queue, taste namespace) | K4 §14.1 |

Genesis is **single-shot**: re-running it on a non-empty store MUST fail (backlog I-GEN
acceptance). The whole sequence runs once, is recorded forever, and the authority it
establishes dissolves at ratification (S4) — see PAEOS-3 §6.

## Why this directory exists early (the recommendation this scaffolds)

When PAEOS reaches self-hosting, these records become permanent system history. Keeping
them separate from ordinary implementation artifacts (`kernel/`, `adapters/`) makes the
bootstrap independently auditable and reproducible — the reproducible-constitution test
(PAEOS-3 §S5) re-derives against exactly this staged, hashed origin.
