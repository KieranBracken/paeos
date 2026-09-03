# SAKG Task 20 — `[T-BASELINE]` Canonical Intake

Source: item 19 of `ops/backlogs/sakg-1-intakes.json`.

**Objective:** Measurement: no-SAKG baseline harness (the §7 falsifier). Run a fixed goal set with
and without the SAKG allow-list entry, reporting deltas in research spawns, L10 remands, and
tokens; assert clean cold-start behavior against an empty graph and graceful degradation when SAKG
is unreachable.

## Deliverables and acceptance

- `sakg/baseline.py` and focused tests
- `tests/sakg/test_baseline_harness.py`
- `tests/sakg/test_empty_graph_returns_empty_not_error.py`
- `tests/sakg/test_unreachable_sakg_degrades_cleanly.py`
- `uv run pytest tests/sakg/test_baseline_harness.py -q`
- `uv run pytest tests/sakg/test_empty_graph_returns_empty_not_error.py -q`
- `uv run pytest tests/sakg/test_unreachable_sakg_degrades_cleanly.py -q`
- `uv run python -m sakg.baseline report --emit-json baseline.json`
- JSON report contains `research_spawns_delta`, `remands_delta`, and `tokens_delta`
- `uv run pyright sakg/`

Task 19 is now Court-sealed. Task 20 is open for isolated SoftLoop execution; no Task 20
implementation or seal is claimed by this intake.
