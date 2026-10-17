import json
from pathlib import Path


def test_closed_edge_families() -> None:
    schema = json.loads((Path(__file__).parents[2] / "concept/schema/edge.schema.json").read_text())
    assert schema["$defs"]["edgeFamily"]["enum"] == ["derivation", "analogy", "recombination", "abstraction", "exemplification", "neighborhood"]


def test_valid_fixtures_cover_closed_families() -> None:
    paths = (Path(__file__).parent / "fixtures/edges/valid").glob("*.json")
    assert {json.loads(p.read_text())["family"] for p in paths} == {"derivation", "analogy", "recombination", "abstraction", "exemplification", "neighborhood"}
