from __future__ import annotations

from concept.ids import canonical_json, content_hash, outbox_uri, validate_concept_uri

GOLDEN_OUTBOX_PREIMAGE = {
    "namespace": "lab",
    "hypothesis_uri": "concept://lab/hypothesis/0123456789ABCDEFGHJKMNPQRS",
    "event_type": "EMITTED",
    "schema_version": 1,
    "candidate": {"proposal": True, "score": "0.125000"},
}
GOLDEN_OUTBOX_BYTES = (
    b'{"candidate":{"proposal":true,"score":"0.125000"},"event_type":"EMITTED",'
    b'"hypothesis_uri":"concept://lab/hypothesis/0123456789ABCDEFGHJKMNPQRS",'
    b'"namespace":"lab","schema_version":1}'
)
GOLDEN_OUTBOX_HASH = "1ee8222532cdf70822673a1d64736a134bc52b91db6f2300b6cc015058a5adf1"
GOLDEN_OUTBOX_URI = "concept://lab/outbox/0YX0H2ACPDYW424SST3NJ76TGK"


def test_candidate_outbox_event_matches_golden_identity() -> None:
    canonical = canonical_json(GOLDEN_OUTBOX_PREIMAGE)

    assert canonical == GOLDEN_OUTBOX_BYTES
    assert content_hash(canonical) == GOLDEN_OUTBOX_HASH
    assert outbox_uri("lab", GOLDEN_OUTBOX_PREIMAGE) == GOLDEN_OUTBOX_URI
    assert validate_concept_uri(GOLDEN_OUTBOX_URI).kind == "outbox"


def test_outbox_identity_is_independent_of_insertion_order() -> None:
    reordered = {
        "candidate": {"score": "0.125000", "proposal": True},
        "schema_version": 1,
        "event_type": "EMITTED",
        "hypothesis_uri": "concept://lab/hypothesis/0123456789ABCDEFGHJKMNPQRS",
        "namespace": "lab",
    }

    assert outbox_uri("lab", reordered) == GOLDEN_OUTBOX_URI


def test_outbox_identity_is_scoped_to_namespace() -> None:
    other = dict(GOLDEN_OUTBOX_PREIMAGE)
    other["namespace"] = "other"
    other["hypothesis_uri"] = "concept://other/hypothesis/0123456789ABCDEFGHJKMNPQRS"

    assert outbox_uri("other", other) != GOLDEN_OUTBOX_URI


def test_outbox_identity_is_scoped_to_hypothesis_uri() -> None:
    other = dict(GOLDEN_OUTBOX_PREIMAGE)
    other["hypothesis_uri"] = "concept://lab/hypothesis/1123456789ABCDEFGHJKMNPQRS"

    assert outbox_uri("lab", other) != GOLDEN_OUTBOX_URI
