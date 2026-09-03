# SAKG Task 17 — `[I-TRADEOFF]` Canonical Intake

Source: item 16 of `ops/backlogs/sakg-1-intakes.json`.

**Objective:** Implement `tradeoff_precedents` as the single S2 method: match `TradeOff` nodes on
axes, walk to the resolving `Decision`, and join its realized `Outcome`.

## Deliverables and acceptance

- `sakg/methods/tradeoff_precedents.py`
- `tests/sakg/test_tradeoff_precedents.py`
- `tests/sakg/test_tradeoff_golden.py`
- `tests/sakg/test_tradeoff_joins_outcome.py`
- Exactly one non-`__init__.py` method module under `sakg/methods/`
- Focused tests and static checks must pass:
  - `uv run pytest tests/sakg/test_tradeoff_precedents.py -q`
  - `uv run pytest tests/sakg/test_tradeoff_golden.py -q`
  - `uv run pytest tests/sakg/test_tradeoff_joins_outcome.py -q`
  - `test $(ls sakg/methods/*.py | grep -v __init__ | wc -l) -eq 1`
  - `uv run pyright sakg/`

Execution is queued for a fresh isolated SoftLoop state root. No Task 17 implementation or seal is
claimed by this intake.
