# PLAN — `classify_obj` lifetime accessor (`runtime/lifetime.py`)

| | |
|---|---|
| **Artifact** | Formal implementation plan: work units + evidence plan + rollback plan |
| **Stage / Role** | `PLAN` / `PLANNER` (PAEOS-7.6 §3) |
| **Status** | PLAN ONLY — no implementation, no verification run. Frozen input to `IMPLEMENT` (BUILDER) and `VERIFY` (VERIFIER). |
| **Date** | 2026-08-02 |
| **Required evidence (this gate)** | `plan_executable` — work units + evidence obligations + rollback declared; refs cited. |
| **Upstream refs** | `design/classify-obj-lifetime.md` (frozen DESIGN); `constitution/classifier_rules/` (L1 mapping authority); `constitution/README.md` (TCB / trust-zone boundary). |

---

## 0. Scope boundary (read first — capability discipline)

This worker session is **PLANNER @ PLAN** with write-capability limited to `plan/` and
read-capability limited to `constitution/`, `design/`, `plan/`. The goal objective names
two actions this stage **does not and must not perform**; they are planned here as
downstream work units, not executed:

1. **Edit `runtime/lifetime.py`** — a `runtime/`-tree write owned by **BUILDER @ IMPLEMENT**
   (PAEOS-7.6 §3 `StageId.IMPLEMENT`, `Role.BUILDER`). It is outside this session's
   write-capability; any such write is discarded as a violation. Planned as **WU-1 / WU-2**.
2. **Run the court verification command** — presupposes the implementation exists and
   produces `VERIFY`-stage evidence (`classify_obj-verified`), owned by **VERIFIER @ VERIFY**
   (`StageId.VERIFY`, `Role.VERIFIER`). Running it now would fail (the function does not yet
   exist) and would misrepresent verify-stage evidence as plan output. Planned as **WU-3**.

The four-tuple transition contract (PAEOS-7.6 §4) keeps these powers separated; honoring it
is the disciplined outcome. Evidence emitted by *this* session is `plan_executable` (this
file) — **not** `classify_obj-verified`.

---

## 1. Objective restatement (traceability)

Add a NEW public pure function to `runtime/lifetime.py`:

```
classify_obj(obj: object) -> LifetimeClass:
    return classify_type(type(obj).__name__)
```

and append the literal string `"classify_obj"` to the module `__all__`. Acceptance is the
court command (§4 / evidence E3) exiting `0` and printing `classify_obj-verified`.

This restates `design/classify-obj-lifetime.md` §2 (interface contract) and §8 (IMPLEMENT
checklist) without adding, relaxing, or reinterpreting any requirement.

---

## 2. Work units (executable, ordered, single-owner)

Each work unit is atomic, has one owning stage/role, a precondition, an exact action, a
done-check, and the evidence it feeds. WUs are strictly sequential: `WU-1 → WU-2 → WU-3`.

### WU-1 — Add the `classify_obj` function body
- **Owner:** BUILDER @ IMPLEMENT (not this session).
- **Ref:** design §2 ("Exact behavioral requirement"), §8.1.
- **Precondition (Assumption A1, design §5):** `classify_type(type_name: str) -> LifetimeClass`
  exists in `runtime/lifetime.py` with a stable signature. BUILDER confirms by reading the
  real module before editing.
- **Action (exact — no more):** insert the public function
  `def classify_obj(obj: object) -> LifetimeClass:` whose body is *precisely*
  `return classify_type(type(obj).__name__)`. No caching, no normalization, no
  special-casing, no new import, no new branch. It inherits every mapping and every
  edge case (including unknown-type handling) from `classify_type`.
- **Done-check:** the new function is present and imports cleanly
  (`from runtime.lifetime import classify_obj` succeeds).
- **Feeds:** evidence E1.

### WU-2 — Export `classify_obj` via `__all__`
- **Owner:** BUILDER @ IMPLEMENT (not this session).
- **Ref:** design §2 ("Exact export requirement"), §8.2; Assumption A4.
- **Precondition:** WU-1 complete; `__all__` present in the module (Assumption A4: it is a
  list/tuple of `str` and is the intended export surface).
- **Action (exact):** append the literal string `"classify_obj"` to `__all__`. **Do not**
  remove, reorder, or reformat existing entries. Change nothing else in the module
  (design §8.3).
- **Done-check:** `"classify_obj" in runtime.lifetime.__all__` is `True`; all pre-existing
  `__all__` entries remain, unchanged and in order.
- **Feeds:** evidence E2.

### WU-3 — Run the court command (acceptance oracle)
- **Owner:** VERIFIER @ VERIFY (not this session).
- **Ref:** design §7; Assumptions A2, A3, A5.
- **Precondition:** WU-1 and WU-2 complete and committed.
- **Action (verbatim — do not alter one character):**
  ```
  /Users/bob/GitHub/paeos/.venv/bin/python -c "from runtime.lifetime import classify_obj, LifetimeClass; from runtime.task_package import ExecutionContext; assert classify_obj(ExecutionContext()) is LifetimeClass.L1; print('classify_obj-verified')"
  ```
- **Done-check:** exit code `0` **and** stdout contains `classify_obj-verified`. Report both
  the exit code and stdout back to the court.
- **Feeds:** evidence E3 (`classify_obj-verified`).

**Blast radius (design §6, A-2):** additive change — one new function + one `__all__`
entry, no edit to existing behavior, non-TCB (`runtime/`, not `constitution/`; see
`constitution/README.md` — TCB is amend-only and is untouched here). Kernel classification
expected **SOFT**; no amendment path required.

---

## 3. Evidence plan (obligations → owner → oracle)

| id | Evidence obligation | Produced by | Oracle / how it is checked | Gate |
|----|---------------------|-------------|----------------------------|------|
| **E0** | `plan_executable` — this file: work units, evidence obligations, rollback declared, refs cited. | PLANNER @ PLAN (this session) | Presence of §2 (WUs), §3 (this table), §4 (rollback), and upstream refs (header + inline). | **PLAN** |
| **E1** | `classify_obj` exists and is importable, body is exactly the delegation. | BUILDER @ IMPLEMENT | `from runtime.lifetime import classify_obj` succeeds; body inspected == `return classify_type(type(obj).__name__)`. | IMPLEMENT |
| **E2** | `"classify_obj"` present in `__all__`, existing exports intact. | BUILDER @ IMPLEMENT | `"classify_obj" in runtime.lifetime.__all__`; pre-existing entries unchanged. | IMPLEMENT |
| **E3** | `classify_obj-verified` — court command exits `0`, prints the token. | VERIFIER @ VERIFY | Run §2/WU-3 command verbatim; assert exit `0` and stdout token. | **VERIFY** |

**Assumption → verification-owner ledger (design §5, carried forward):**
- A1 (`classify_type` exists, stable sig) → confirmed at **WU-1** by BUILDER.
- A2 (`LifetimeClass` closed enum with `L1`) → confirmed at **WU-3** (import + `.L1` deref).
- A3 (`classify_type("ExecutionContext") == L1`, governed by `constitution/classifier_rules/`,
  no new rule added — respects I7/K6) → confirmed at **WU-3**.
- A4 (`__all__` is the `str` export surface) → confirmed at **WU-2** by BUILDER.
- A5 (`ExecutionContext` importable from `runtime.task_package`, no-arg constructible) →
  confirmed at **WU-3** by VERIFIER.

No assumption changes the plan; each is a fact a downstream WU confirms.

---

## 4. Rollback plan

The change is additive and non-TCB, so rollback is clean and bounded.

- **Trigger:** WU-3 court command exits non-zero, fails to print `classify_obj-verified`, or
  any pre-existing `runtime.lifetime` export/behavior regresses.
- **Rollback action (BUILDER @ IMPLEMENT, on a `runtime/` write capability):**
  1. Remove the `classify_obj` function added in WU-1.
  2. Remove the `"classify_obj"` entry appended to `__all__` in WU-2, restoring the prior
     sequence exactly.
  3. Result: `runtime/lifetime.py` is byte-for-byte the pre-change module — no other lines
     were touched (design §8.3), so no collateral revert is needed.
- **Verification of rollback:** the module imports cleanly and every pre-existing export
  resolves; the new symbol `classify_obj` is absent
  (`from runtime.lifetime import classify_obj` raises `ImportError`).
- **Blast containment:** because nothing outside these two additions was modified and the
  constitution/TCB tree is untouched, rollback cannot leave partial state and requires no
  kernel amendment or ratifier action.
- **Recovery path:** after rollback, re-enter **IMPLEMENT** to correct WU-1/WU-2 against the
  real module (e.g. reconcile the true `classify_type` signature or `__all__` shape), then
  re-run WU-3.

---

## 5. Completeness check (no orphan / no gap)

- Every objective clause (§1) maps to a work unit (§2): function body → WU-1, export → WU-2,
  court command → WU-3.
- Every work unit produces or feeds an evidence obligation (§3): WU-1→E1, WU-2→E2, WU-3→E3;
  this file is E0.
- Every assumption (design §5) has a named downstream verification owner (§3 ledger).
- A rollback is declared and bounded for the only mutating stage (§4).
- All claims cite an upstream ref: `design/classify-obj-lifetime.md` (§§2, 5, 6, 7, 8),
  `constitution/classifier_rules/` (A3 authority), `constitution/README.md` (TCB boundary).

**Evidence for this gate:** `plan_executable` = this file.
