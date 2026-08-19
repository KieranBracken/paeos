# System Design — `is_institutional(cls: LifetimeClass) -> bool`

Status: DESIGN ONLY — no implementation. Stage: L08 DESIGN (`StageId DESIGN`, PAEOS-9 §. spine).
Role: PLANNER. Date: 2026-08-02.
Scope of this artifact: the classification predicate to be added to `runtime/lifetime.py`.
Implementation (edit of `runtime/lifetime.py`) is deferred to L12 IMPLEMENT — out of this
stage's write capability by design (DESIGN precedes IMPLEMENT on the operational spine,
PAEOS-9 §; L08→L11→L12).

---

## 1. Goal restatement (acceptance surface)

Add one new **pure, total** public predicate to `runtime/lifetime.py`:

```
is_institutional(cls: LifetimeClass) -> bool
```

Contract: returns `True` **iff** `cls ∈ {LifetimeClass.L3, LifetimeClass.L4,
LifetimeClass.L5}` (the durable / institutional lifetime classes); returns `False`
for `L0`, `L1`, `L2`. Export it by adding the string `"is_institutional"` to the
module `__all__`.

Acceptance oracle (the court's evidence command, run by IMPLEMENT):

```
python -c "from runtime.lifetime import is_institutional, LifetimeClass as L; \
  assert is_institutional(L.L5) and is_institutional(L.L4) and is_institutional(L.L3) \
  and not is_institutional(L.L2) and not is_institutional(L.L1) and not is_institutional(L.L0); \
  print('is_institutional-verified')"
```

Exit 0 + stdout `is_institutional-verified` is the pass condition.

---

## 2. Component graph (blast radius)

```
                 ┌─────────────────────────────┐
                 │  runtime/lifetime.py         │
                 │                              │
   LifetimeClass │  enum LifetimeClass (exists) │  ← read-only dependency
   (existing) ───┼─▶ is_institutional(cls)      │  ← NEW pure function
                 │       │                      │
                 │       └─▶ membership test    │
                 │           {L3,L4,L5}         │
                 │                              │
                 │  __all__  += "is_institutional"  ← NEW export line
                 └─────────────────────────────┘
                          ▲            ▲
                          │            │ (future) callers import the predicate
             acceptance oracle    downstream policy code
             (§1, IMPLEMENT)      (no callers introduced here)
```

- **New nodes:** exactly one function symbol + one `__all__` entry. No new module,
  no new type, no new import.
- **Edges introduced:** `is_institutional → LifetimeClass` (name reference only).
- **Orphan/gap check:** the sole new node is reachable (exported via `__all__`,
  exercised by the acceptance oracle). No dangling dependency; `LifetimeClass` is a
  pre-existing symbol the objective guarantees present ("This function does NOT yet
  exist — add it" implies the enum already does). **No orphan, no gap.**

---

## 3. Interface / contract

| Property        | Value |
|-----------------|-------|
| Signature       | `def is_institutional(cls: LifetimeClass) -> bool:` |
| Purity          | Pure — no I/O, no mutation, no store/ledger/syscall access. |
| Totality        | Total over the 6-member enum domain `{L0,L1,L2,L3,L4,L5}`. |
| Determinism     | Same input → same output; referentially transparent. |
| Domain          | `LifetimeClass` (the six-member enum). |
| Codomain        | `bool`. |
| Truth partition | `{L3,L4,L5} → True` (durable/institutional); `{L0,L1,L2} → False`. |
| Side effects    | None. Idempotent. |
| Export          | Added to `__all__` as the literal `"is_institutional"`. |

**Recommended body** (canonical, membership-set form — closed over the intended set,
robust to enum re-ordering, O(1)):

```python
def is_institutional(cls: LifetimeClass) -> bool:
    """True iff cls is a durable/institutional lifetime class (L3, L4, L5)."""
    return cls in {LifetimeClass.L3, LifetimeClass.L4, LifetimeClass.L5}
```

Rationale for the set-membership form over an ordinal comparison
(`cls.value >= LifetimeClass.L3.value`): the objective specifies the True-set
**extensionally** ({L3,L4,L5}), so encoding it extensionally means the code cannot
silently drift if enum integer values are ever renumbered or a hypothetical `L6` is
appended. This keeps the predicate's meaning pinned to the *named* classes, not to an
accident of ordinal layout — the safer choice under PAEOS's "no silent semantic drift"
posture.

---

## 4. Data flow

```
caller ──cls:LifetimeClass──▶ is_institutional
                                   │
                                   ├─ evaluate  cls ∈ {L3,L4,L5}
                                   │
                                   └──bool──▶ caller
```

Single synchronous frame. No durable substrate touched (contrast the LSM/ledger paths
in PAEOS-7 §; this predicate is a leaf pure function, the L0-unit-test tier of the
test taxonomy, PAEOS-4.5 §: "pure functions vs golden fixtures"). It carries no budget,
performs no WRITE, and is safe to call from any context including read-only snapshots.

---

## 5. State machine

The function itself is **stateless** — it has no lifecycle. The only state relevant to
this design is the *implementation artifact's* progression through the operational
spine, which this DESIGN stage hands off:

```
  L08 DESIGN (this artifact)  ──▶  L11 PLAN  ──▶  L12 IMPLEMENT  ──▶  L13 VERIFY
   design_coherent evidence          plan          edit lifetime.py    run §1 oracle
                                                    + __all__ entry     → is_institutional-verified
```

Transition guard L12→L13: the acceptance oracle (§1) must exit 0 with the exact
stdout token. This DESIGN stage produces no runtime state and asserts no green oracle;
it asserts only design coherence.

---

## 6. Assumptions surfaced (PAEOS-6)

Explicit assumptions this design rests on, each falsifiable:

- **A1.** `LifetimeClass` already exists in `runtime/lifetime.py` and defines members
  `L0…L5`. *(Guaranteed by the objective wording; falsifier: import of
  `LifetimeClass` fails → the design's precondition is void and IMPLEMENT must first
  add the enum.)*
- **A2.** The enum has **exactly** six members `L0..L5`; no `L6+` exists. *(Falsifier:
  a member outside {L0..L5} exists → totality claim in §3 breaks and the True/False
  partition must be re-specified. The set-membership form in §3 degrades gracefully —
  any unlisted member returns False — but the extensional intent should be re-confirmed.)*
- **A3.** A module-level `__all__` list already exists to append to. *(Falsifier:
  `__all__` absent → IMPLEMENT must create it containing at least `"is_institutional"`;
  the export requirement still holds.)*
- **A4.** "institutional" ≡ "durable" ≡ the upper three classes {L3,L4,L5}; the lower
  three {L0,L1,L2} are the non-durable/ephemeral classes. *(Direct from the objective;
  no independent corpus definition of a `LifetimeClass`-named enum was found in the
  readable scope — constitution/, spec/, design/ — so the objective is the authority
  for this semantic. Falsifier: a spec clause defining a conflicting membership.)*
- **A5.** No existing symbol named `is_institutional` is present (objective states the
  function does not yet exist). *(Falsifier: a name collision at add-time → IMPLEMENT
  reconciles rather than duplicates.)*

---

## 7. Perspectives covered

- **Correctness:** partition is exhaustive and disjoint over the 6-member domain; the
  acceptance oracle (§1) pins all six inputs, so the design is fully covered by its own
  test — one positive assertion per institutional class, one negative per ephemeral
  class (mirrors PAEOS-4.5 §'s "≥1 positive + ≥1 negative" coverage discipline).
- **Maintainability / drift-resistance:** extensional set form (§3) keeps meaning tied
  to named members, not ordinal values.
- **Purity / safety:** leaf pure function; no substrate, budget, or authority surface
  touched — cannot violate append-only/store invariants (nothing to violate).
- **Interface hygiene:** `__all__` export makes the predicate part of the module's
  public contract deliberately, not incidentally.
- **Scope discipline:** this stage writes only `design/`; the `runtime/lifetime.py`
  edit is explicitly deferred to L12 IMPLEMENT, honoring DESIGN-before-IMPLEMENT
  ordering and this worker's write capability.

---

## 8. Implementation handoff (for L12)

Minimal, mechanical, two edits — no ambiguity remains:

1. Add the function body from §3 to `runtime/lifetime.py` (place it beside the
   `LifetimeClass` definition / other module-level predicates, matching surrounding
   style).
2. Append `"is_institutional"` to the module `__all__`.
3. Run the §1 acceptance oracle; expect exit 0 and stdout `is_institutional-verified`.

No other file changes required. No new dependencies. No fixture changes.

---

## Evidence: `design_coherent`

- **Assumptions surfaced (PAEOS-6):** §6 (A1–A5), each with an explicit falsifier.
- **Perspectives covered:** §7 (correctness, maintainability, purity/safety, interface
  hygiene, scope discipline).
- **No orphan / no gap:** §2 blast-radius graph — the single new node is exported and
  exercised by the acceptance oracle; its one dependency (`LifetimeClass`) pre-exists;
  no dangling edges, no unreachable symbol, no unmet dependency.

Design is coherent and complete for a one-stage handoff to PLAN/IMPLEMENT.
