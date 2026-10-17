"""CLI boundary tests: invalid input fails before any worker launch."""

from __future__ import annotations

from ops import bound_cline_worker


def test_cli_rejects_missing_absolute_state_root_before_launch() -> None:
    assert bound_cline_worker.main(["--state-root", "relative"]) == 2


def test_cli_rejects_interactive_and_legacy_transport_flags() -> None:
    assert bound_cline_worker.main(["--state-root", "/tmp/state", "--clipboard"]) == 2
