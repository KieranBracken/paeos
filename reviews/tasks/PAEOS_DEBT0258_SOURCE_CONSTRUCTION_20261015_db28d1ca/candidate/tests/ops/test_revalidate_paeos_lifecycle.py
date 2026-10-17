"""Contract tests for the read-only L01-L19 lifecycle revalidation CLI."""

from __future__ import annotations

import json
from pathlib import Path

from kernel.ledger import Event, Ledger
from kernel.ledger_sqlite import SqliteLedgerStore

from ops import revalidate_paeos_lifecycle


def _ledger(path: Path) -> None:
    store = SqliteLedgerStore(path)
    try:
        with Ledger(store, writer_id="test-lifecycle") as ledger:
            ledger.append(
                Event(
                    schema_ver=1,
                    kind="STAGE_COMPLETED",
                    payload={"run_id": "RUN-001", "layer": 1},
                )
            )
    finally:
        store.close()


def _argv(ledger: Path, state_root: Path, repository: Path) -> list[str]:
    return [
        "--ledger",
        str(ledger),
        "--state-root",
        str(state_root),
        "--repository",
        str(repository),
        "--run-id",
        "RUN-001",
        "--json",
    ]


def test_cli_emits_all_layers_and_fails_closed_for_unproven_run(
    tmp_path: Path, capsys
) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    ledger = state_root / "ledger.sqlite3"
    _ledger(ledger)
    repository = tmp_path / "repository"
    repository.mkdir()

    assert revalidate_paeos_lifecycle.main(_argv(ledger, state_root, repository)) == 2
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["run_id"] == "RUN-001"
    assert len(output["layers"]) == 19
    assert [row["layer"] for row in output["layers"]] == [f"L{i:02d}" for i in range(1, 20)]
    assert output["layers"][0]["reason_code"] == "MISSING_ARTIFACT"
    assert output["sealed"] == 0
    assert output["remanded"] == 0
    assert output["remediated"] == 0
    assert output["blocking_reason_codes"]
    assert "\n" not in captured.out.strip()


def test_cli_refuses_corrupt_ledger_without_writing(tmp_path: Path, capsys) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    ledger = state_root / "ledger.sqlite3"
    ledger.write_bytes(b"not sqlite")
    before = ledger.stat()
    repository = tmp_path / "repository"
    repository.mkdir()

    assert revalidate_paeos_lifecycle.main(_argv(ledger, state_root, repository)) == 2
    assert "ledger" in capsys.readouterr().err.lower()
    after = ledger.stat()
    assert (after.st_size, after.st_mtime_ns) == (before.st_size, before.st_mtime_ns)


def test_cli_rejects_ledger_outside_state_root(tmp_path: Path, capsys) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    ledger = tmp_path / "ledger.sqlite3"
    _ledger(ledger)
    repository = tmp_path / "repository"
    repository.mkdir()

    assert revalidate_paeos_lifecycle.main(_argv(ledger, state_root, repository)) == 2
    assert "state root" in capsys.readouterr().err.lower()


def test_cli_requires_existing_repository_and_json_mode(tmp_path: Path, capsys) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    ledger = state_root / "ledger.sqlite3"
    _ledger(ledger)
    missing = tmp_path / "missing"

    argv = _argv(ledger, state_root, missing)
    assert revalidate_paeos_lifecycle.main(argv) == 2
    assert "repository" in capsys.readouterr().err.lower()

    argv = _argv(ledger, state_root, tmp_path)
    argv.remove("--json")
    assert revalidate_paeos_lifecycle.main(argv) == 2
    assert "json" in capsys.readouterr().err.lower()


def test_active_cli_has_no_mutating_or_gui_path() -> None:
    source = Path(revalidate_paeos_lifecycle.__file__).read_text(encoding="utf-8").lower()
    for forbidden in (
        "git checkout",
        "git merge",
        "git push",
        "insert into",
        "update ",
        "delete from",
        "osascript",
        "pbcopy",
        "time.sleep",
        "subprocess.popen",
    ):
        assert forbidden not in source
