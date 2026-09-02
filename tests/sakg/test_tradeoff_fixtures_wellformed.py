"""Well-formedness checks for golden tradeoff precedent fixtures."""

from __future__ import annotations

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/sakg/fixtures/tradeoff"
SCHEMA = ROOT / "sakg/schema/tradeoff-fixture.schema.json"
REQUIRED = {"schema_version", "case", "source", "query", "expected"}
RESULT_REQUIRED = {"decision_id", "score", "why", "outcome"}
AXIS = re.compile(r"^[a-z][a-z ]+$")


def _errors(fixture: object) -> list[str]:
    if not isinstance(fixture, dict):
        return ["not-object"]
    errors: list[str] = []
    if set(fixture) != REQUIRED:
        errors.append("top-level-keys")
    if fixture.get("schema_version") != "paeos.sakg.tradeoff-fixture/v1":
        errors.append("schema-version")
    source = fixture.get("source")
    if (
        not isinstance(source, dict)
        or not source.get("path")
        or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("sha256")))
    ):
        errors.append("source")
    query = fixture.get("query")
    if not isinstance(query, dict) or query.get("method") != "tradeoff_precedents":
        errors.append("query-method")
    axes = query.get("axes") if isinstance(query, dict) else None
    if (
        not isinstance(axes, list)
        or len(axes) < 2
        or len(axes) != len(set(axes))
        or not all(isinstance(axis, str) and AXIS.fullmatch(axis) for axis in axes)
    ):
        errors.append("axes")
    expected = fixture.get("expected")
    results = expected.get("results") if isinstance(expected, dict) else None
    if not isinstance(results, list) or not results:
        errors.append("results")
        results = []
    scores: list[float] = []
    for result in results:
        if not isinstance(result, dict) or set(result) != RESULT_REQUIRED:
            errors.append("result-keys")
            continue
        score = result.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= 1:
            errors.append("score")
        else:
            scores.append(float(score))
        why = result.get("why")
        if (
            not isinstance(why, list)
            or len(why) < 3
            or not all(isinstance(step, str) and step for step in why)
        ):
            errors.append("why-path")
        elif "TradeOff" not in why[0] or "Decision" not in why[1] or "Outcome" not in why[-1]:
            errors.append("why-join")
        outcome = result.get("outcome")
        if (
            not isinstance(outcome, dict)
            or set(outcome) != {"id", "status", "summary"}
            or outcome.get("status") != "realized"
            or not outcome.get("summary")
        ):
            errors.append("outcome")
    if scores != sorted(scores, reverse=True):
        errors.append("ranking")
    return errors


def test_tradeoff_fixture_catalog_is_well_formed_and_ranked() -> None:
    files = sorted(FIXTURES.glob("*.json"))
    assert len(files) >= 5
    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    fixtures = [json.loads(path.read_text()) for path in files]
    assert all(not list(validator.iter_errors(item)) for item in fixtures)
    assert all(not _errors(item) for item in fixtures), [
        (path.name, _errors(item))
        for path, item in zip(files, fixtures, strict=True)
        if _errors(item)
    ]
    assert {item["case"] for item in fixtures} == {path.stem for path in files}


def test_every_result_has_explicit_decision_to_outcome_path() -> None:
    fixtures = [json.loads(path.read_text()) for path in sorted(FIXTURES.glob("*.json"))]
    for fixture in fixtures:
        for result in fixture["expected"]["results"]:
            assert result["why"] == [
                result["why"][0],
                "TradeOff resolves_to Decision",
                "Decision realized_as Outcome",
            ]
            assert result["outcome"]["id"].startswith("sakg://")
