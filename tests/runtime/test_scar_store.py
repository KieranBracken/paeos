from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from runtime.memory import ScarDraft, ScarQuarantined
from runtime.scar_store import SqliteScarStore


def _draft(*tags: str) -> ScarDraft:
    return ScarDraft(
        signature=frozenset(tags),
        lesson="persist the institutional lesson",
        detection="assert the lesson is injected",
        severity="high",
    )


def test_database_is_colocated_and_starts_empty(tmp_path: Path) -> None:
    store = SqliteScarStore(tmp_path)
    assert store.db_path == tmp_path / "scars.db"
    assert store.db_path.is_file()
    assert store.all_scars() == []
    store.close()


def test_record_scar_survives_a_fresh_process(tmp_path: Path) -> None:
    writer = SqliteScarStore(tmp_path)
    written = writer.record_scar(_draft("domain:sakg", "failure:timeout"))
    writer.close()

    code = """
from pathlib import Path
import json
import sys
from runtime.scar_store import SqliteScarStore
store = SqliteScarStore(Path(sys.argv[1]))
print(json.dumps([scar.__dict__ if hasattr(scar, '__dict__') else {
    'id': scar.id, 'signature': sorted(scar.signature), 'lesson': scar.lesson,
    'detection': scar.detection, 'severity': scar.severity,
} for scar in store.match_scars('domain:sakg,failure:timeout,extra:tag')]))
store.close()
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd())
    completed = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path.cwd(),
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    observed = json.loads(completed.stdout)
    assert observed == [
        {
            "id": written.id,
            "signature": ["domain:sakg", "failure:timeout"],
            "lesson": written.lesson,
            "detection": written.detection,
            "severity": written.severity,
        }
    ]


def test_matching_and_all_scars_are_deterministic(tmp_path: Path) -> None:
    store = SqliteScarStore(tmp_path)
    first = store.record_scar(_draft("domain:sakg", "failure:timeout"))
    second = store.record_scar(_draft("domain:sakg", "failure:quota"))
    assert [scar.id for scar in store.all_scars()] == [first.id, second.id]
    assert [scar.id for scar in store.match_scars("domain:sakg,failure:quota,extra")]==[second.id]
    store.close()


def test_broad_signatures_are_quarantined_without_a_row(tmp_path: Path) -> None:
    store = SqliteScarStore(tmp_path)
    with pytest.raises(ScarQuarantined):
        store.record_scar(_draft("domain:sakg"))
    assert store.all_scars() == []
    store.close()


def test_autonomous_composition_uses_state_dir_store(tmp_path: Path) -> None:
    from ops.autonomous_run import build_scheduler
    from runtime.scheduler import GlobalBudget

    state_dir = tmp_path / "state"
    scheduler, evolution, _ledger = build_scheduler(
        state_dir,
        Path.cwd(),
        global_budget=GlobalBudget(tokens=10_000, wallclock_s=30, runs=1),
        runtime_type="codex",
    )
    assert (state_dir / "scars.db").is_file()
    assert type(evolution._scars).__name__ == "SqliteScarStore"
    del scheduler
