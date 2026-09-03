# PAEOS Milestone 42 Intake — `[I-LIFETIME-CONFORMANCE]` / R4 Runtime Object Classifier

**Status:** `OPEN/QUEUED`
**Opened:** 2026-09-03
**Predecessor:** Milestone 41 `[I-CEREMONY-WALK]`, candidate `fba0a21a664b9e5f8d7f76dfc04e53bcc24a42cd`
**Canonical source:** `ops/backlogs/first-r4.json`

## Objective

Add the missing public object classifier to `runtime/lifetime.py`:

```python
classify_obj(obj: object) -> LifetimeClass
```

It must return `classify_type(type(obj).__name__)` and export `classify_obj` through
`runtime.lifetime.__all__`. This is the first R4 lifetime-conformance slice; it does not alter
the existing lifetime classification rules.

## Deliverables and acceptance

1. Update `runtime/lifetime.py` and add
   `tests/runtime/test_lifetime_classify_obj.py`.
2. Prove the public API with:
   `/Users/bob/GitHub/paeos/.venv/bin/python -c "from runtime.lifetime import classify_obj, LifetimeClass; from runtime.task_package import ExecutionContext; assert classify_obj(ExecutionContext()) is LifetimeClass.L1; print('classify_obj-verified')"`
3. Run `uv run pytest tests/runtime/test_lifetime_classify_obj.py -q`.
4. Run `uv run pyright runtime/lifetime.py` and record the exact result.
5. Execute the implementation in an isolated SoftLoop under
   `/private/tmp/paeos-r4lifetime-run`, then produce candidate-bound L13 evidence and an
   independent heterogeneous L14/L17 audit pair before any seal.

## Boundary

Implementation remains worker-owned in the isolated SoftLoop. This intake authorizes neither
direct host architectural edits nor promotion to `main`/`trunk`. Historical files
`reviews/tasks/PAEOS_INTAKE_M42_L14_L17_CHECKPOINT.md` and
`reviews/tasks/PAEOS_INTAKE_M42_FOUNDER_COURT_DISPOSITION.md` are preserved legacy records tied
to an earlier candidate and are not substituted for this newly opened intake.
