import json
from pathlib import Path


def test_closed_node_types() -> None:
    schema = json.loads((Path(__file__).parents[2] / "concept/schema/node.schema.json").read_text())
    assert schema["$defs"]["nodeType"]["enum"] == ["Concept", "Analogy", "Transformation", "SemanticNeighborhood", "InspirationHeuristic", "Hypothesis"]


def test_valid_fixtures_cover_closed_types() -> None:
    paths = (Path(__file__).parent / "fixtures/nodes/valid").glob("*.json")
    assert {json.loads(p.read_text())["type"] for p in paths} == {"Concept", "Analogy", "Transformation", "SemanticNeighborhood", "InspirationHeuristic", "Hypothesis"}
