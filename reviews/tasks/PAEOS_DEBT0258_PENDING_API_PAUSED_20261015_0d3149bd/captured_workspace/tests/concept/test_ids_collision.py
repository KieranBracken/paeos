from __future__ import annotations

import pytest
from concept.ids import (
    IdentityCollisionError,
    _ensure_identity_collision_free,
    canonical_json,
    content_hash,
    node_uri,
)

FORCED_URI = "concept://lab/concept/00000000000000000000000000"


def test_forced_token_collision_with_distinct_full_hashes_fails_closed() -> None:
    existing = canonical_json({"namespace": "lab", "type": "Concept", "payload": "a"})
    candidate = canonical_json({"namespace": "lab", "type": "Concept", "payload": "b"})

    with pytest.raises(IdentityCollisionError, match=FORCED_URI):
        _ensure_identity_collision_free(
            uri=FORCED_URI,
            canonical_bytes=candidate,
            full_hash=content_hash(candidate),
            existing_canonical_bytes=existing,
            existing_full_hash=content_hash(existing),
        )


def test_same_uri_and_identity_is_idempotent_at_collision_boundary() -> None:
    canonical = canonical_json({"namespace": "lab", "type": "Concept", "payload": "a"})
    digest = content_hash(canonical)

    _ensure_identity_collision_free(
        uri=FORCED_URI,
        canonical_bytes=canonical,
        full_hash=digest,
        existing_canonical_bytes=canonical,
        existing_full_hash=digest,
    )


def test_same_bytes_with_a_distinct_stored_hash_fails_closed() -> None:
    canonical = canonical_json({"namespace": "lab", "type": "Concept", "payload": "a"})

    with pytest.raises(IdentityCollisionError, match="full SHA-256"):
        _ensure_identity_collision_free(
            uri=FORCED_URI,
            canonical_bytes=canonical,
            full_hash="0" * 64,
            existing_canonical_bytes=canonical,
            existing_full_hash="f" * 64,
        )


def test_one_character_preimage_change_changes_hash_and_token() -> None:
    first = {"namespace": "lab", "type": "Concept", "payload": {"label": "alpha"}}
    second = {"namespace": "lab", "type": "Concept", "payload": {"label": "alphb"}}

    first_bytes = canonical_json(first)
    second_bytes = canonical_json(second)
    first_uri = node_uri("lab", "Concept", first)
    second_uri = node_uri("lab", "Concept", second)

    assert content_hash(first_bytes) != content_hash(second_bytes)
    assert first_uri != second_uri
    assert first_uri.rsplit("/", 1)[1] != second_uri.rsplit("/", 1)[1]
