"""GLM/Cline CLI fail-closed tests pending trusted disclosure authority."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from kernel.types import StageId
from runtime.integrations import SessionSpec, TrustedTransportFailure, _parse_cost
from runtime.integrations.hybrid import CLINE_MODEL, _court_pool_dir, glm_cli_invoker

from tests.runtime.test_hybrid_runtime import _make_package

_PROMPT_MARKER = "SYNTHETIC_CLINE_PROMPT_MUST_NOT_BE_ECHOED"


def _spec(tmp_path: Path) -> SessionSpec:
    return SessionSpec(
        workspace=tmp_path, prompt=_PROMPT_MARKER, allowed_tools=("read",),
        read_scopes=("/",), timeout_s=120,
    )


def _cline_stream(model_id: str = CLINE_MODEL, finish: str = "completed") -> str:
    return "\n".join([
        json.dumps({"ts": "t0", "type": "agent_event", "event": {"type": "iteration_start", "iteration": 1}}),
        json.dumps({"ts": "t1", "type": "agent_event", "event": {"type": "content_end", "contentType": "text", "text": "OK"}}),
        json.dumps({
            "ts": "t2", "type": "run_result", "finishReason": finish,
            "usage": {"inputTokens": 100, "outputTokens": 5, "cacheReadTokens": 20},
            "durationMs": 1500, "text": "OK",
            "model": {"id": model_id, "provider": "cline-pass"},
        }),
    ])


def _patch_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, MagicMock]:
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/cline" if name == "cline" else None)
    provider_process = MagicMock(
        side_effect=AssertionError("Cline provider process helper was reached")
    )
    bounded_process = MagicMock(side_effect=AssertionError("bounded process runner was reached"))
    monkeypatch.setattr("runtime.integrations.hybrid._run_provider_process", provider_process)
    monkeypatch.setattr("runtime.integrations.hybrid.run_bounded_process", bounded_process)
    return provider_process, bounded_process


class _PromptAccessBomb:
    @property
    def prompt(self) -> str:
        raise AssertionError("Cline prompt was inspected before local denial")


def _assert_local_denial(
    invoker: Callable[..., object],
    spec: object,
    provider_process: MagicMock,
    bounded_process: MagicMock,
) -> None:
    with pytest.raises(TrustedTransportFailure) as raised:
        invoker(spec)
    assert raised.value.code == "disclosure_authority_unavailable"
    assert _PROMPT_MARKER not in str(raised.value)
    provider_process.assert_not_called()
    bounded_process.assert_not_called()


def test_invoker_denies_before_prompt_or_argv_construction(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider_process, bounded_process = _patch_cli(monkeypatch)
    invoker = glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))
    _assert_local_denial(invoker, _PromptAccessBomb(), provider_process, bounded_process)


def test_successful_provider_output_is_not_reached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider_process, bounded_process = _patch_cli(monkeypatch)
    invoker = glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))
    _assert_local_denial(invoker, _spec(tmp_path), provider_process, bounded_process)


def test_wrong_model_output_is_not_reached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    provider_process, bounded_process = _patch_cli(monkeypatch)
    invoker = glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))
    _assert_local_denial(invoker, _spec(tmp_path), provider_process, bounded_process)


def test_missing_run_result_is_not_reached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    provider_process, bounded_process = _patch_cli(monkeypatch)
    invoker = glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))
    _assert_local_denial(invoker, _spec(tmp_path), provider_process, bounded_process)


def test_non_completed_finish_is_not_reached(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider_process, bounded_process = _patch_cli(monkeypatch)
    invoker = glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))
    _assert_local_denial(invoker, _spec(tmp_path), provider_process, bounded_process)


def test_nonzero_exit_is_not_reached(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    provider_process, bounded_process = _patch_cli(monkeypatch)
    invoker = glm_cli_invoker(_make_package(StageId.ADVERSARIAL_REVIEW))
    _assert_local_denial(invoker, _spec(tmp_path), provider_process, bounded_process)


def test_cost_parsed_from_cline_stream() -> None:
    cost = _parse_cost(_cline_stream(), "fallback")
    assert cost.tokens == 105  # inputTokens + outputTokens
    assert cost.wallclock_s == pytest.approx(1.5)
    assert cost.model_ver == CLINE_MODEL


def test_cost_unparseable_stays_zero() -> None:
    cost = _parse_cost("not json at all", "fallback")
    assert cost.tokens == 0 and cost.model_ver == "fallback"


def test_court_pool_dir_extraction(tmp_path: Path) -> None:
    cfg = tmp_path / "mcp-config.json"
    cfg.write_text(json.dumps({
        "mcpServers": {"paeos-court": {"command": "python", "args": ["-m", "runtime.transports.mcp.court_server", str(tmp_path / "court"), str(tmp_path / "workspace")]}}
    }))
    assert _court_pool_dir(cfg) == tmp_path / "court"
    assert _court_pool_dir(None) is None
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    assert _court_pool_dir(bad) is None


def test_cline_does_not_seed_a_worker_writable_court_helper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider_process, bounded_process = _patch_cli(monkeypatch)
    cfg = tmp_path / "mcp-config.json"
    pool = tmp_path / "court"
    cfg.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "paeos-court": {
                        "command": "python",
                        "args": [
                            "-m",
                            "runtime.transports.mcp.court_server",
                            str(pool),
                            str(tmp_path / "workspace"),
                        ],
                    }
                }
            }
        )
    )
    invoker = glm_cli_invoker(_make_package(StageId.IMPLEMENT), mcp_config_path=cfg)
    _assert_local_denial(invoker, _spec(tmp_path), provider_process, bounded_process)
    assert not (tmp_path / "submit_evidence.py").exists()
