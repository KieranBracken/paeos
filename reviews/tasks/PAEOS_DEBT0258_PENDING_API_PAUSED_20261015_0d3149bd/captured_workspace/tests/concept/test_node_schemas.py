import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT = Path(__file__).parent / "fixtures/nodes"
SCHEMA = Path(__file__).parents[2] / "concept/schema/node.schema.json"


def schema() -> dict[str, object]:
    return json.loads(SCHEMA.read_text())


def fixtures(kind: str) -> list[Path]:
    return sorted((ROOT / kind).glob("*.json"))


def test_schema_is_valid() -> None:
    Draft202012Validator.check_schema(schema())


@pytest.mark.parametrize("path", fixtures("valid"), ids=lambda p: p.name)
def test_valid_fixture(path: Path) -> None:
    Draft202012Validator(schema()).validate(json.loads(path.read_text()))


@pytest.mark.parametrize("path", fixtures("invalid"), ids=lambda p: p.name)
def test_invalid_fixture(path: Path) -> None:
    with pytest.raises(ValidationError):
        Draft202012Validator(schema()).validate(json.loads(path.read_text()))
