from __future__ import annotations

from datetime import UTC, datetime

import pytest
from concept.ids import (
    _encode_crockford_128,
    _token_from_digest,
    canonical_json,
    content_hash,
    edge_uri,
    node_uri,
    outbox_uri,
    validate_concept_uri,
)

import concept

GOLDEN_NODE_PREIMAGE = {
    "namespace": "lab",
    "type": "Concept",
    "schema_version": 1,
    "payload": {"label": "Cafe\u0301", "score": "0.750000"},
    "representations": [],
    "provenance_refs": [],
}
GOLDEN_NODE_BYTES = (
    b'{"namespace":"lab","payload":{"label":"Caf\xc3\xa9","score":"0.750000"},'
    b'"provenance_refs":[],"representations":[],"schema_version":1,"type":"Concept"}'
)
GOLDEN_NODE_HASH = "4d096c4fea456edc89029716a1cc22929e9108c69e30df276ffe0c76e7662712"
GOLDEN_NODE_URI = "concept://lab/concept/2D15P4ZTJ5DVE8J0MQ2TGWR8MJ"


def test_concept_package_exports_the_public_identity_interface() -> None:
    expected = {
        "ConceptURI",
        "IdentityCollisionError",
        "canonical_json",
        "content_hash",
        "edge_uri",
        "node_uri",
        "outbox_uri",
        "validate_concept_uri",
    }

    assert set(concept.__all__) == expected
    assert all(getattr(concept, name) is not None for name in expected)


def test_canonical_json_sorts_keys_and_removes_whitespace() -> None:
    first = {"z": [3, 2, 1], "a": {"right": False, "left": None}}
    second = {"a": {"left": None, "right": False}, "z": [3, 2, 1]}

    expected = b'{"a":{"left":null,"right":false},"z":[3,2,1]}'
    assert canonical_json(first) == expected
    assert canonical_json(second) == expected


def test_canonical_json_normalizes_keys_and_values_to_unicode_nfc() -> None:
    decomposed = {"nai\u0308ve": "Cafe\u0301"}
    composed = {"na\u00efve": "Caf\u00e9"}

    assert canonical_json(decomposed) == canonical_json(composed)
    assert canonical_json(decomposed) == b'{"na\xc3\xafve":"Caf\xc3\xa9"}'


def test_canonical_json_sorts_sets_by_canonical_element_bytes() -> None:
    value = {"numbers": {32, 1, 2}, "tags": {"zeta", "alpha", "\u00e9clair"}}

    assert canonical_json(value) == (
        b'{"numbers":[1,2,32],"tags":["alpha","zeta","\xc3\xa9clair"]}'
    )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), -0.0])
def test_canonical_json_rejects_noncanonical_floats(value: float) -> None:
    with pytest.raises(ValueError, match="float"):
        canonical_json({"value": value})


def test_canonical_json_accepts_finite_binary64_values() -> None:
    assert canonical_json({"value": 1.5}) == b'{"value":1.5}'


def test_canonical_json_requires_explicit_datetime_strings() -> None:
    with pytest.raises(TypeError, match="datetime"):
        canonical_json({"when": datetime(2026, 9, 4, tzinfo=UTC)})


def test_canonical_json_rejects_non_string_object_keys() -> None:
    with pytest.raises(TypeError, match="object keys"):
        canonical_json({1: "not-json-object-key"})


def test_canonical_json_rejects_key_collisions_after_unicode_normalization() -> None:
    with pytest.raises(ValueError, match="same NFC key"):
        canonical_json({"Cafe\u0301": 1, "Caf\u00e9": 2})


def test_content_hash_matches_golden_sha256() -> None:
    assert content_hash(GOLDEN_NODE_BYTES) == GOLDEN_NODE_HASH


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (0, "00000000000000000000000000"),
        (1, "00000000000000000000000001"),
        (31, "0000000000000000000000000Z"),
        (32, "00000000000000000000000010"),
        (255, "0000000000000000000000007Z"),
        (256, "00000000000000000000000080"),
        (1 << 127, "40000000000000000000000000"),
        ((1 << 128) - 1, "7ZZZZZZZZZZZZZZZZZZZZZZZZZ"),
    ],
)
def test_crockford_encoder_has_fixed_width_and_correct_alignment(
    number: int, expected: str
) -> None:
    assert _encode_crockford_128(number) == expected


def test_token_uses_only_the_first_sixteen_digest_bytes() -> None:
    first_128_bits = bytes.fromhex("00000000000000000000000000000001")

    assert _token_from_digest(first_128_bits + bytes(16)) == (
        "00000000000000000000000001"
    )
    assert _token_from_digest(first_128_bits + bytes.fromhex("ff" * 16)) == (
        "00000000000000000000000001"
    )


@pytest.mark.parametrize("number", [-1, 1 << 128])
def test_crockford_encoder_rejects_values_outside_unsigned_128_bit_range(number: int) -> None:
    with pytest.raises(ValueError, match="128-bit"):
        _encode_crockford_128(number)


def test_golden_node_identity_matches_exact_bytes_hash_and_uri() -> None:
    assert canonical_json(GOLDEN_NODE_PREIMAGE) == GOLDEN_NODE_BYTES
    assert content_hash(canonical_json(GOLDEN_NODE_PREIMAGE)) == GOLDEN_NODE_HASH
    assert node_uri("lab", "Concept", GOLDEN_NODE_PREIMAGE) == GOLDEN_NODE_URI


def test_node_type_is_normalized_to_lowercase_kebab_case() -> None:
    preimage = {"namespace": "lab", "type": "SemanticTransformation"}
    uri = node_uri("lab", "SemanticTransformation", preimage)

    assert validate_concept_uri(uri).kind == "semantic-transformation"


def test_edge_and_outbox_uri_kinds_validate() -> None:
    edge = edge_uri("lab", {"namespace": "lab", "relation": "related-to"})
    outbox = outbox_uri("lab", {"namespace": "lab", "event_type": "EMITTED"})

    assert validate_concept_uri(edge).kind == "edge"
    assert validate_concept_uri(outbox).kind == "outbox"


def test_validate_concept_uri_returns_typed_components() -> None:
    parsed = validate_concept_uri(GOLDEN_NODE_URI)

    assert parsed.uri == GOLDEN_NODE_URI
    assert parsed.namespace == "lab"
    assert parsed.kind == "concept"
    assert parsed.token == "2D15P4ZTJ5DVE8J0MQ2TGWR8MJ"


@pytest.mark.parametrize(
    "namespace",
    ["", "Upper", "-leading", "has.dot", "a" * 64],
)
def test_uri_constructors_reject_invalid_namespaces(namespace: str) -> None:
    with pytest.raises(ValueError, match="namespace"):
        edge_uri(namespace, {"namespace": namespace})


@pytest.mark.parametrize("node_type", ["", "bad/kind", "-leading", "x" * 64])
def test_node_uri_rejects_invalid_normalized_kinds(node_type: str) -> None:
    with pytest.raises(ValueError, match="node kind"):
        node_uri("lab", node_type, {"namespace": "lab", "type": node_type})


def test_node_uri_requires_the_envelope_type_field() -> None:
    with pytest.raises(ValueError, match=r"type.*node_type"):
        node_uri("lab", "Concept", {"namespace": "lab", "node_type": "Concept"})


def test_node_uri_rejects_a_type_that_differs_from_the_preimage() -> None:
    with pytest.raises(ValueError, match="must match"):
        node_uri("lab", "Concept", {"namespace": "lab", "type": "Pattern"})


def test_uri_constructors_reject_a_mismatched_preimage_namespace() -> None:
    with pytest.raises(ValueError, match="preimage namespace"):
        outbox_uri("lab", {"namespace": "other", "event_type": "EMITTED"})


@pytest.mark.parametrize("namespace", ["Upper", "-leading", "has.dot", "a" * 64])
def test_validate_concept_uri_rejects_invalid_namespaces(namespace: str) -> None:
    uri = f"concept://{namespace}/concept/00000000000000000000000000"
    with pytest.raises(ValueError, match="namespace"):
        validate_concept_uri(uri)


@pytest.mark.parametrize("kind", ["Bad_kind", "-leading", "has/slash", "x" * 64])
def test_validate_concept_uri_rejects_invalid_kinds(kind: str) -> None:
    uri = f"concept://lab/{kind}/00000000000000000000000000"
    with pytest.raises(ValueError, match=r"kind|segments"):
        validate_concept_uri(uri)


@pytest.mark.parametrize("forbidden", ["I", "L", "O", "U"])
def test_validate_concept_uri_rejects_forbidden_crockford_characters(forbidden: str) -> None:
    token = "0" * 25 + forbidden
    with pytest.raises(ValueError, match="Crockford"):
        validate_concept_uri(f"concept://lab/concept/{token}")


def test_validate_concept_uri_rejects_lowercase_token_characters() -> None:
    with pytest.raises(ValueError, match="uppercase"):
        validate_concept_uri("concept://lab/concept/0000000000000000000000000a")


@pytest.mark.parametrize("token", ["0" * 25, "0" * 27, "8" + "0" * 25])
def test_validate_concept_uri_rejects_bad_token_length_or_top_bits(token: str) -> None:
    with pytest.raises(ValueError, match=r"26-character|Crockford"):
        validate_concept_uri(f"concept://lab/concept/{token}")


def test_validate_concept_uri_rejects_the_wrong_scheme() -> None:
    with pytest.raises(ValueError, match="scheme"):
        validate_concept_uri("https://lab/concept/00000000000000000000000000")
