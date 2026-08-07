"""B0.13 acceptance tests for observability (PAEOS-8 §10 / §3).

Covers: structured JSON logging; secret scrubbing (secrets redacted, counts and content hashes
preserved); the cost/trace meter (one row per action); and `traced` (a log + a meter row per
action).
"""

from __future__ import annotations

import io
import json

from kernel.observability import (
    REDACTED,
    Meter,
    configure_logging,
    get_logger,
    scrub_secrets,
    traced,
)


def _lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


# ---- structured JSON logging ----------------------------------------------


def test_emits_json_with_level_and_timestamp() -> None:
    stream = io.StringIO()
    configure_logging(stream)
    get_logger("test").info("goal_advanced", goal="g1", to_state="VERIFY")
    (record,) = _lines(stream)
    assert record["event"] == "goal_advanced"
    assert record["goal"] == "g1"
    assert record["to_state"] == "VERIFY"
    assert record["level"] == "info"
    assert "timestamp" in record


# ---- secret scrubbing ------------------------------------------------------


def test_secrets_are_redacted_but_counts_and_hashes_survive() -> None:
    stream = io.StringIO()
    configure_logging(stream)
    get_logger().info(
        "seal",
        password="hunter2",
        seed="deadbeefcafe",
        signing_key="abc123",
        token="bearer-xyz",
        attestation="ed25519sig",
        tokens=42,  # a COUNT, must not be scrubbed
        artifact_hash="a" * 64,  # a public content address, must not be scrubbed
    )
    (record,) = _lines(stream)
    assert record["password"] == REDACTED
    assert record["seed"] == REDACTED
    assert record["signing_key"] == REDACTED
    assert record["token"] == REDACTED
    assert record["attestation"] == REDACTED
    assert record["tokens"] == 42  # preserved
    assert record["artifact_hash"] == "a" * 64  # preserved


def test_scrub_secrets_processor_directly() -> None:
    out = scrub_secrets(None, "info", {"api_key": "x", "tokens": 3, "goal": "g"})
    assert out["api_key"] == REDACTED
    assert out["tokens"] == 3
    assert out["goal"] == "g"


# ---- cost / trace meter ----------------------------------------------------


def test_meter_records_a_row_per_action() -> None:
    meter = Meter()
    meter.record("open_stage", tokens=10, wallclock_s=0.5, model_ver="kernel")
    meter.record("propose_transition", tokens=0, model_ver="kernel")
    meter.record("spawn", tokens=1200, wallclock_s=3.1, model_ver="sonnet-x")
    assert len(meter.rows) == 3
    assert meter.total_tokens() == 1210
    assert meter.rows[2].model_ver == "sonnet-x"
    assert meter.rows[0].action == "open_stage"
    assert all(row.timestamp for row in meter.rows)


# ---- traced: one log + one meter row per action ----------------------------


def test_traced_emits_log_and_meter_row() -> None:
    stream = io.StringIO()
    configure_logging(stream)
    meter = Meter()
    with traced(
        "advance", logger=get_logger(), meter=meter, tokens=7, model_ver="kernel", goal="g1"
    ):
        pass
    lines = _lines(stream)
    assert len(lines) == 2  # start + end
    assert lines[0]["phase"] == "start"
    assert lines[1]["phase"] == "end"
    assert lines[0]["goal"] == "g1"
    assert "wallclock_s" in lines[1]
    # exactly one meter row, carrying the measured wallclock
    (row,) = meter.rows
    assert row.action == "advance"
    assert row.tokens == 7
    assert row.wallclock_s >= 0.0


def test_traced_without_meter_still_logs() -> None:
    stream = io.StringIO()
    configure_logging(stream)
    with traced("inspect", logger=get_logger()):
        pass
    assert len(_lines(stream)) == 2
