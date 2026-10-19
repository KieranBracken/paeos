"""Synthetic-only tests of dormant policy parsing; no host authority or providers."""

from __future__ import annotations

import base64
import copy
import hashlib
import json
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path

import paeos.model_router.disclosure_policy as implementation
import pytest
from nacl.signing import SigningKey
from paeos.model_router.disclosure_policy import (
    DisclosurePolicyError,
    ExactRouteIdentity,
    FounderTrustRootError,
    canonical_policy_bytes,
    policy_digest,
    verify_founder_policy,
)
from paeos.model_router.types import CostTier, ModelCatalogEntry, ModelFamily, ProviderId

NOW = datetime(2026, 10, 18, tzinfo=UTC)
DOMAIN = b"PAEOS-DISCLOSURE-POLICY-V1\0"


def test_import_origin_is_this_candidate():
    assert (
        Path(implementation.__file__).resolve()
        == Path(__file__).resolve().parents[2] / "paeos/model_router/disclosure_policy.py"
    )


@pytest.fixture
def key():
    return SigningKey.generate()  # Ephemeral synthetic authority, never persisted.


@pytest.fixture
def policy():
    return {
        "schema": "paeos.disclosure-policy/1",
        "policy_id": "synthetic-policy",
        "revision": 1,
        "status": "ACTIVE",
        "founder_authority": {
            "key_id": "synthetic-founder",
            "algorithm": "Ed25519",
            "signature_encoding": "base64url-no-pad",
        },
        "issued_at": "2026-10-17T00:00:00Z",
        "expires_at": "2026-10-19T00:00:00Z",
        "revocation_mode": "IMMEDIATE",
        "classes": [
            {
                "class_id": "PUBLIC_ARTIFACT",
                "data_class": "PUBLIC",
                "purpose_ids": ["synthetic-audit"],
                "scope": {
                    "repository_ids": ["synthetic-repository"],
                    "allowed_artifacts": [
                        {
                            "relative_path": "docs/synthetic.txt",
                            "sha256": hashlib.sha256(b"synthetic public text").hexdigest(),
                            "max_bytes": 100,
                        }
                    ],
                    "scope_mode": "EXACT_ARTIFACTS",
                },
                "allowed_routes": [
                    {
                        "provider_id": "google",
                        "model_id": "synthetic-model-1",
                        "model_family": "gemini",
                        "entitlement_class": "FREE",
                        "transport_profile_id": "synthetic-transport",
                        "external_operator_id": "synthetic-operator",
                    }
                ],
                "max_bundle_bytes": 1000,
                "max_artifacts": 1,
                "required_exclusions": [
                    "credentials",
                    "sentium",
                    "legacy_orca_credentials",
                    "unrelated_private_data",
                ],
                "require_builder_auditor_family_distinct": True,
                "require_a08": True,
                "max_attempts": 1,
                "capability_ttl_seconds": 60,
            }
        ],
    }


def signed(policy, key, *, domain=DOMAIN):
    value = copy.deepcopy(policy)
    value["founder_authority"].pop("signature", None)
    # Independent serializer: the verifier is not its own signing oracle.
    unsigned = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    signature = key.sign(domain + unsigned).signature
    value["founder_authority"]["signature"] = (
        base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    )
    return json.dumps(value).encode()


def verify(raw, key):
    return verify_founder_policy(raw, key.verify_key, "synthetic-founder", now=NOW)


def test_valid_signature_has_immutable_parsed_content_and_canonical_digest(policy, key):
    raw = signed(policy, key)
    result = verify(raw, key)
    canonical = json.dumps(
        json.loads(raw), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    assert policy_digest(result) == hashlib.sha256(canonical).hexdigest()
    assert result.policy_id == "synthetic-policy"
    assert result.classes[0].scope.allowed_artifacts[0].relative_path == "docs/synthetic.txt"
    assert isinstance(result.classes, tuple)
    with pytest.raises(FrozenInstanceError):
        result.classes[0].data_class = "SECRET"
    assert not hasattr(result, "egress_permitted")


def test_canonical_encoding_is_utf8_and_independent_of_mapping_order():
    assert canonical_policy_bytes({"z": "é", "a": 1}) == b'{"a":1,"z":"\xc3\xa9"}'
    assert canonical_policy_bytes({"a": 1, "z": "é"}) == canonical_policy_bytes({"z": "é", "a": 1})


@pytest.mark.parametrize(
    "value", [{"x": float("nan")}, {"x": 1.5}, {1: "not a string"}, {"x": "\ud800"}]
)
def test_canonical_encoding_rejects_ambiguous_or_non_json_values(value):
    with pytest.raises(DisclosurePolicyError):
        canonical_policy_bytes(value)


@pytest.mark.parametrize("domain", [b"", b"PAEOS-KERNEL-CAPABILITY\0"])
def test_domain_separation(policy, key, domain):
    with pytest.raises(FounderTrustRootError):
        verify(signed(policy, key, domain=domain), key)


def test_wrong_or_missing_independently_selected_key_is_denied(policy, key):
    raw = signed(policy, key)
    with pytest.raises(FounderTrustRootError):
        verify(raw, SigningKey.generate())
    for public_key, identity in [
        (None, "synthetic-founder"),
        (key.verify_key, ""),
        (key.verify_key, "worker-root"),
    ]:
        with pytest.raises(FounderTrustRootError):
            verify_founder_policy(raw, public_key, identity, now=NOW)


@pytest.mark.parametrize("field", ["algorithm", "signature_encoding", "key_id"])
def test_authority_metadata_is_exact(policy, key, field):
    policy["founder_authority"][field] = "worker-supplied"
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


def test_embedded_public_key_cannot_select_trust_root(policy, key):
    policy["founder_authority"]["public_key"] = key.verify_key.encode().hex()
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


@pytest.mark.parametrize("signature", ["", "AA", "@" * 86, "A" * 88 + "="])
def test_malformed_signature_encoding(policy, key, signature):
    value = json.loads(signed(policy, key))
    value["founder_authority"]["signature"] = signature
    with pytest.raises(DisclosurePolicyError):
        verify(json.dumps(value).encode(), key)


@pytest.mark.parametrize("location", ["root", "class", "scope", "artifact", "route"])
def test_unknown_fields_reject_even_with_valid_signature(policy, key, location):
    cls = policy["classes"][0]
    target = {
        "root": policy,
        "class": cls,
        "scope": cls["scope"],
        "artifact": cls["scope"]["allowed_artifacts"][0],
        "route": cls["allowed_routes"][0],
    }[location]
    target["unbound"] = "synthetic"
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


@pytest.mark.parametrize(
    "field", ["schema", "revision", "founder_authority", "classes", "expires_at"]
)
def test_missing_fields(policy, key, field):
    raw = json.loads(signed(policy, key))
    del raw[field]
    with pytest.raises(DisclosurePolicyError):
        verify(json.dumps(raw).encode(), key)


def test_duplicate_keys_reject_even_when_last_value_has_valid_signature(policy, key):
    raw = signed(policy, key)
    raw = raw.replace(b"{", b'{"revision":9,', 1)
    with pytest.raises(DisclosurePolicyError):
        verify(raw, key)


@pytest.mark.parametrize("value", [True, False, 0, -1, 1.0, "1", 2**64])
@pytest.mark.parametrize(
    "field",
    ["revision", "max_attempts", "max_artifacts", "max_bundle_bytes", "capability_ttl_seconds"],
)
def test_positive_integer_bounds(policy, key, field, value):
    target = policy if field == "revision" else policy["classes"][0]
    target[field] = value
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


@pytest.mark.parametrize(
    "field,value",
    [
        ("data_class", "SECRET"),
        ("data_class", "UNKNOWN"),
        ("data_class", "CONFIDENTIAL"),
        ("data_class", "INTERNAL"),
        ("class_id", "SECRET"),
        ("required_exclusions", []),
        ("require_a08", False),
        ("require_a08", 1),
        ("require_builder_auditor_family_distinct", False),
        ("purpose_ids", []),
        ("purpose_ids", ["synthetic-audit", "synthetic-audit"]),
    ],
)
def test_unsupported_or_weakened_class(policy, key, field, value):
    policy["classes"][0][field] = value
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


def test_supported_internal_class_is_verified_but_does_not_activate(policy, key):
    policy["classes"][0].update(
        class_id="REDACTED_INTERNAL_ENGINEERING_SOURCE", data_class="INTERNAL"
    )
    assert verify(signed(policy, key), key).classes[0].data_class == "INTERNAL"


@pytest.mark.parametrize(
    "path",
    [
        "/outside",
        "../outside",
        "docs/../outside",
        "docs//x",
        "./x",
        "x/",
        "a\\b",
        "*.txt",
        "x\x00y",
        "a?b",
        "<path>",
    ],
)
def test_non_exact_artifact_paths(policy, key, path):
    policy["classes"][0]["scope"]["allowed_artifacts"][0]["relative_path"] = path
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


@pytest.mark.parametrize(
    "field,value",
    [("sha256", "A" * 64), ("sha256", "a" * 63), ("max_bytes", True), ("max_bytes", 0)],
)
def test_artifact_hash_and_size(policy, key, field, value):
    policy["classes"][0]["scope"]["allowed_artifacts"][0][field] = value
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


@pytest.mark.parametrize(
    "field,value",
    [
        ("provider_id", "Google"),
        ("provider_id", "*"),
        ("model_id", "openrouter/free"),
        ("model_id", "openrouter/auto"),
        ("model_id", "model-latest"),
        ("model_id", "<model>"),
        ("model_family", "unknown"),
        ("entitlement_class", "PAID"),
        ("entitlement_class", "SUBSCRIPTION_INCLUDED"),
        ("transport_profile_id", ""),
        ("external_operator_id", "*"),
    ],
)
def test_dynamic_or_inexact_route_rejects(policy, key, field, value):
    policy["classes"][0]["allowed_routes"][0][field] = value
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


def test_exact_route_identity_matches_all_six_components(policy):
    route = ExactRouteIdentity.from_mapping(policy["classes"][0]["allowed_routes"][0])
    entry = ModelCatalogEntry("synthetic-model-1", ProviderId.GOOGLE, ModelFamily.GEMINI)
    assert route.matches_catalog(entry, "synthetic-transport", "synthetic-operator")
    for changed in [
        replace(entry, provider_id=ProviderId.NVIDIA),
        replace(entry, model_id="other-1"),
        replace(entry, family=ModelFamily.GPT),
        replace(entry, cost_tier=CostTier.PAID),
    ]:
        assert not route.matches_catalog(changed, "synthetic-transport", "synthetic-operator")
    assert not route.matches_catalog(entry, "other", "synthetic-operator")
    assert not route.matches_catalog(entry, "synthetic-transport", "other")


def test_exact_free_variant_is_not_confused_with_auto_router(policy, key):
    policy["classes"][0]["allowed_routes"][0]["model_id"] = "synthetic/model-1:free"
    assert (
        verify(signed(policy, key), key).classes[0].allowed_routes[0].model_id
        == "synthetic/model-1:free"
    )


def test_every_signed_leaf_is_bound(policy, key):
    envelope = json.loads(signed(policy, key))

    def leaves(value, path=()):
        if isinstance(value, dict):
            for name, child in value.items():
                if name != "signature":
                    yield from leaves(child, (*path, name))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from leaves(child, (*path, index))
        else:
            yield path

    for path in leaves(envelope):
        changed = copy.deepcopy(envelope)
        target = changed
        for part in path[:-1]:
            target = target[part]
        old = target[path[-1]]
        target[path[-1]] = (
            not old
            if isinstance(old, bool)
            else old + 1
            if isinstance(old, int)
            else old + "-changed"
        )
        with pytest.raises(DisclosurePolicyError):
            verify(json.dumps(changed).encode(), key)


@pytest.mark.parametrize("location", ["classes", "routes", "artifacts", "repositories"])
def test_ambiguous_duplicate_collections(policy, key, location):
    cls = policy["classes"][0]
    values = {
        "classes": policy["classes"],
        "routes": cls["allowed_routes"],
        "artifacts": cls["scope"]["allowed_artifacts"],
        "repositories": cls["scope"]["repository_ids"],
    }[location]
    values.append(copy.deepcopy(values[0]))
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


def test_errors_do_not_echo_untrusted_payload(policy, key):
    policy["policy_id"] = "SYNTHETIC_PRIVATE_SENTINEL / invalid"
    with pytest.raises(DisclosurePolicyError) as error:
        verify(signed(policy, key), key)
    assert "SYNTHETIC_PRIVATE_SENTINEL" not in str(error.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("expires_at", "2026-10-18T00:00:00Z"),
        ("issued_at", "2026-10-18T00:00:01Z"),
        ("issued_at", "2026-10-20T00:00:00Z"),
        ("expires_at", "2026-10-19"),
        ("expires_at", "2026-10-19T00:00:00+01:00"),
        ("status", "REVOKED"),
        ("revocation_mode", "LAZY"),
        ("schema", "paeos.disclosure-policy/2"),
    ],
)
def test_invalid_or_inactive_temporal_policy(policy, key, field, value):
    policy[field] = value
    with pytest.raises(DisclosurePolicyError):
        verify(signed(policy, key), key)


def test_clock_without_timezone_is_not_authoritative(policy, key):
    with pytest.raises(DisclosurePolicyError):
        verify_founder_policy(
            signed(policy, key), key.verify_key, "synthetic-founder", now=NOW.replace(tzinfo=None)
        )


@pytest.mark.parametrize(
    "raw", [b"[]", b"null", b"NaN", b"\xff", b"{" + b" " * 1_048_576, b"[" * 2000]
)
def test_malformed_and_resource_bounded_input(raw, key):
    with pytest.raises(DisclosurePolicyError):
        verify(raw, key)


# V2 is an explicit signed derivative contract; it cannot widen the V1 parser.
def _derivative_policy(policy):
    value = copy.deepcopy(policy)
    value["schema"] = "paeos.disclosure-policy/2"
    value["derivative_rules"] = [
        {
            "rule_id": "synthetic-derivative",
            "class_id": "PUBLIC_ARTIFACT",
            "input_artifact_sha256s": [
                value["classes"][0]["scope"]["allowed_artifacts"][0]["sha256"]
            ],
            "input_data_class": "PUBLIC",
            "output_data_class": "PUBLIC",
            "tool_envelope_sha256": "a" * 64,
            "transformation_ids": ["READ_APPROVED_ARTIFACT", "SCOPED_PATCH", "NAMED_TEST_OUTPUT"],
            "max_output_bytes": 100,
        }
    ]
    return value


def _verify_derivative(policy, key, domain=b"PAEOS-DISCLOSURE-POLICY-V2\0"):
    assert hasattr(implementation, "verify_founder_derivative_policy"), (
        "versioned derivative verifier missing"
    )
    return implementation.verify_founder_derivative_policy(
        signed(policy, key, domain=domain), key.verify_key, "synthetic-founder", now=NOW
    )


def test_versioned_derivative_policy_keeps_v1_exact_artifact_semantics(policy, key):
    v2 = _derivative_policy(policy)
    result = _verify_derivative(v2, key)
    rule = result.derivative_rules[0]
    assert rule.output_data_class == rule.input_data_class == "PUBLIC"
    assert rule.tool_envelope_sha256 == "a" * 64
    assert not hasattr(rule, "authorized")
    with pytest.raises(DisclosurePolicyError):
        verify(signed(v2, key, domain=b"PAEOS-DISCLOSURE-POLICY-V2\0"), key)
    with pytest.raises(DisclosurePolicyError):
        _verify_derivative(v2, key, domain=DOMAIN)
    with pytest.raises(DisclosurePolicyError):
        _verify_derivative(policy, key)


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_data_class", "SECRET"),
        ("output_data_class", "SECRET"),
        ("input_data_class", "UNKNOWN"),
        ("output_data_class", "UNKNOWN"),
        ("input_data_class", "INTERNAL"),
        ("class_id", "unclassified"),
        ("input_artifact_sha256s", ["b" * 64]),
        ("input_artifact_sha256s", []),
        ("tool_envelope_sha256", "worker-label"),
        ("tool_envelope_sha256", "A" * 64),
        ("transformation_ids", ["UNRESTRICTED_SHELL"]),
        ("transformation_ids", []),
        ("max_output_bytes", 0),
        ("max_output_bytes", True),
        ("max_output_bytes", 1000000000),
    ],
)
def test_derivative_rules_require_bound_inputs_tools_and_nonsecret_class(policy, key, field, value):
    v2 = _derivative_policy(policy)
    v2["derivative_rules"][0][field] = value
    with pytest.raises(DisclosurePolicyError):
        _verify_derivative(v2, key)


def test_internal_derivative_cannot_be_downgraded_to_public(policy, key):
    v2 = _derivative_policy(policy)
    v2["classes"][0].update(class_id="REDACTED_INTERNAL_ENGINEERING_SOURCE", data_class="INTERNAL")
    v2["derivative_rules"][0].update(
        class_id="REDACTED_INTERNAL_ENGINEERING_SOURCE",
        input_data_class="INTERNAL",
        output_data_class="INTERNAL",
    )
    assert _verify_derivative(v2, key).derivative_rules[0].output_data_class == "INTERNAL"
    v2["derivative_rules"][0]["output_data_class"] = "PUBLIC"
    with pytest.raises(DisclosurePolicyError):
        _verify_derivative(v2, key)


def test_derivative_unknown_fields_duplicates_and_embedded_keys_reject(policy, key):
    v2 = _derivative_policy(policy)
    for field in ["verify_key", "classification_authority", "worker_callback", "unknown"]:
        mutated = copy.deepcopy(v2)
        mutated["derivative_rules"][0][field] = "synthetic untrusted value"
        with pytest.raises(DisclosurePolicyError):
            _verify_derivative(mutated, key)
    v2["derivative_rules"].append(copy.deepcopy(v2["derivative_rules"][0]))
    with pytest.raises(DisclosurePolicyError):
        _verify_derivative(v2, key)
