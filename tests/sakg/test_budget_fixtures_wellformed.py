"""Structural validation for golden drop-and-count budget fixtures."""
from __future__ import annotations

import json
from numbers import Real
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/sakg/fixtures/budget"
SCHEMA = ROOT / "sakg/schema/budget-fixture.schema.json"
TOP_REQUIRED = {"schema_version", "case", "request", "candidates", "expected"}
BUDGET_REQUIRED = {"max_tokens", "max_nodes", "tier"}
CANDIDATE_REQUIRED = {"id", "node_summary", "score", "why", "estimated_tokens"}
SUMMARY_REQUIRED = {"id", "type", "namespace", "status", "label", "summary"}
EXPECTED_REQUIRED = {"retained_ids", "retained_tokens", "omitted", "truncated"}


def _positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _errors(value: object) -> list[str]:
    if not isinstance(value, dict):
        return ["fixture-not-object"]
    errors: list[str] = []
    if set(value) != TOP_REQUIRED:
        errors.append("top-level-keys")
    if value.get("schema_version") != "paeos.sakg.budget-fixture/v1":
        errors.append("schema-version")
    if not isinstance(value.get("case"), str) or not value["case"]:
        errors.append("case")
    request = value.get("request")
    budget = request.get("budget") if isinstance(request, dict) else None
    if not isinstance(request, dict) or set(request) != {"budget"}:
        errors.append("request")
    if not isinstance(budget, dict) or set(budget) != BUDGET_REQUIRED:
        errors.append("budget-keys")
    elif not _positive_int(budget.get("max_tokens")) or not _positive_int(budget.get("max_nodes")):
        errors.append("budget-positive")
    elif not isinstance(budget.get("tier"), str) or budget["tier"] == "FULL":
        errors.append("budget-tier")

    candidates = value.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        errors.append("candidates")
        candidates = []
    ids: list[str] = []
    costs: dict[str, int] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != CANDIDATE_REQUIRED:
            errors.append("candidate-keys")
            continue
        node = candidate.get("node_summary")
        if not isinstance(node, dict) or set(node) != SUMMARY_REQUIRED:
            errors.append("node-summary")
        elif node.get("id") != candidate.get("id"):
            errors.append("id-binding")
        candidate_id = candidate.get("id")
        if not isinstance(candidate_id, str) or not candidate_id or candidate_id in ids:
            errors.append("candidate-id")
        else:
            ids.append(candidate_id)
        if not isinstance(candidate.get("score"), Real) or isinstance(candidate.get("score"), bool) or not 0 <= candidate["score"] <= 1:
            errors.append("score")
        if not isinstance(candidate.get("why"), str) or not candidate["why"]:
            errors.append("why")
        if not _positive_int(candidate.get("estimated_tokens")):
            errors.append("estimated-tokens")
        elif isinstance(candidate_id, str):
            costs[candidate_id] = candidate["estimated_tokens"]

    expected = value.get("expected")
    if not isinstance(expected, dict) or set(expected) != EXPECTED_REQUIRED:
        errors.append("expected-keys")
        return errors
    retained = expected.get("retained_ids")
    if not isinstance(retained, list) or len(retained) != len(set(retained)):
        errors.append("retained-ids")
        retained = []
    if any(item not in ids for item in retained):
        errors.append("retained-subset")
    if [item for item in ids if item in retained] != retained:
        errors.append("retained-order")
    if not _positive_int(expected.get("retained_tokens")) and expected.get("retained_tokens") != 0:
        errors.append("retained-tokens")
    elif expected.get("retained_tokens") != sum(costs.get(item, 0) for item in retained):
        errors.append("retained-token-sum")
    if not isinstance(expected.get("omitted"), int) or isinstance(expected.get("omitted"), bool) or expected["omitted"] != len(ids) - len(retained):
        errors.append("omitted-count")
    if not isinstance(expected.get("truncated"), bool) or expected["truncated"] != (expected.get("omitted") != 0):
        errors.append("truncated-flag")
    if isinstance(budget, dict) and _positive_int(budget.get("max_nodes")) and len(retained) > budget["max_nodes"]:
        errors.append("max-nodes")
    if isinstance(budget, dict) and _positive_int(budget.get("max_tokens")) and expected.get("retained_tokens", 0) > budget["max_tokens"]:
        errors.append("max-tokens")
    return errors


def test_budget_fixture_catalog_is_complete_and_well_formed() -> None:
    files = sorted(FIXTURES.glob("*.json"))
    assert len(files) >= 6
    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    cases = [json.loads(path.read_text()) for path in files]
    validator = Draft202012Validator(schema)
    assert all(not list(validator.iter_errors(case)) for case in cases)
    assert all(not _errors(case) for case in cases), [(path.name, _errors(case)) for path, case in zip(files, cases) if _errors(case)]
    assert {case["case"] for case in cases} == {path.stem for path in files}
    assert {case["case"] for case in cases} >= {
        "max-nodes-overflow",
        "max-tokens-overflow",
        "both-limits-overflow",
        "exact-boundary",
        "single-result-too-large",
        "skip-oversized-then-fit",
    }


def test_budget_fixtures_prove_drop_and_count_without_truncation() -> None:
    cases = [json.loads(path.read_text()) for path in sorted(FIXTURES.glob("*.json"))]
    by_case = {case["case"]: case for case in cases}
    for case in cases:
        expected = case["expected"]
        if expected["omitted"]:
            assert expected["truncated"] is True
        else:
            assert expected["truncated"] is False
    pathological = by_case["single-result-too-large"]
    assert pathological["expected"] == {"retained_ids": [], "retained_tokens": 0, "omitted": 1, "truncated": True}
    skip = by_case["skip-oversized-then-fit"]
    assert skip["expected"]["retained_ids"] == [skip["candidates"][1]["id"], skip["candidates"][2]["id"]]
