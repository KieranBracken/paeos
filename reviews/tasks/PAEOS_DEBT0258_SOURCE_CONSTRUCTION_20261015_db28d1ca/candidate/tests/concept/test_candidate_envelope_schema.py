import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

SCHEMA = Path(__file__).parents[2] / "concept/schema/candidate_hypothesis.schema.json"


def candidate() -> dict[str, object]:
    return {"envelope_id":"concept://demo/outbox/00000000000000000000000000","schema_version":1,"proposal_kind":"exploratory_hypothesis","authority":"exploratory","trust":"untrusted_candidate","hypothesis_uri":"concept://demo/hypothesis/00000000000000000000000000","proposition":"A rule reduces oscillation.","scope":"toy systems","assumptions":["fixed sampling"],"expected_observations":["amplitude decreases"],"falsifiers":["amplitude increases"],"source_refs":["concept://demo/concept/00000000000000000000000000"],"replay_manifest":{"query_hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","graph_snapshot_hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb","algorithms":[{"name":"bfs","version":"1"}],"seeds":{"bfs":7},"budgets":{"max_results":2},"generator_trace":[{"step":1,"action":"propose"}]},"score_vectors":{"evidentiary":False,"components":{"novelty":"0.80"}},"graph_snapshot_hash":"cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc","content_hashes":["dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"],"requested_evaluation_kind":"bounded_experiment"}


def test_candidate_schema() -> None:
    schema = json.loads(SCHEMA.read_text())
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(candidate())


def test_candidate_scores_are_non_evidentiary() -> None:
    value = candidate()
    value["score_vectors"] = {"evidentiary":True,"components":{}}
    with pytest.raises(ValidationError):
        Draft202012Validator(json.loads(SCHEMA.read_text())).validate(value)


def test_candidate_requires_falsifier() -> None:
    value = candidate()
    value["falsifiers"] = []
    with pytest.raises(ValidationError):
        Draft202012Validator(json.loads(SCHEMA.read_text())).validate(value)
