"""Task 14 backfill behavior and append-only output tests."""

from __future__ import annotations

from pathlib import Path

from sakg.backfill import backfill_outcomes, discover_historical_records, parse_historical_record

ROOT = Path(__file__).resolve().parents[2]
DEBT = ROOT / "ledger/debt/DEBT-0062.md"
INCIDENT = ROOT / "tests/sakg/fixtures/backfill/INCIDENT-0001.md"
DECISION = "sakg://paeos-recovery/Decision/01J00000000000000000000F01"


def test_backfill_discovers_debt_and_incident_records_and_preserves_gaps() -> None:
    paths = discover_historical_records(
        (ROOT / "ledger/debt", ROOT / "tests/sakg/fixtures/backfill")
    )
    assert DEBT in paths and INCIDENT in paths
    result = backfill_outcomes(paths, namespace="paeos-recovery", run_id="test-backfill")
    assert result.scanned >= 2
    assert result.produced >= 2
    assert all(node["type"] == "Outcome" for node in result.nodes)
    assert all(
        edge["relation"] == "decision_realized_as_historical_outcome" for edge in result.edges
    )


def test_unbound_record_is_an_explicit_gap_and_never_emits_an_outcome(tmp_path: Path) -> None:
    source = tmp_path / "DEBT-UNBOUND.md"
    source.write_text("# unbound\n\n## Compromise\nNo decision is named.\n", encoding="utf-8")
    result = backfill_outcomes((source,), namespace="paeos-recovery", run_id="gap-test")
    assert result.produced == 0
    assert result.gaps[0].reason == "decision-binding-missing"


def test_explicit_source_binding_is_recorded() -> None:
    record = parse_historical_record(DEBT)
    assert record.decision_id == DECISION
    assert record.binding_method == "explicit"
    assert record.source_hash and len(record.source_hash) == 64
