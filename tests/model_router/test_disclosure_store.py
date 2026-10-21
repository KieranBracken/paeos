"""Real temporary filesystem and synthetic identities; no host authority."""

import hashlib
import importlib
import json
import os
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from test_disclosure_policy import NOW, _derivative_policy, signed
from test_disclosure_policy import key as synthetic_key  # noqa: F401
from test_disclosure_policy import policy as synthetic_policy  # noqa: F401


@pytest.fixture
def loader():
    class LazyModule:
        def __getattr__(self, name):
            try:
                module = importlib.import_module("paeos.model_router.disclosure_store")
            except ModuleNotFoundError:
                pytest.fail("pinned public-policy input loader is not implemented")
            return getattr(module, name)

    return LazyModule()


@pytest.fixture
def inputs(tmp_path, synthetic_key, synthetic_policy):  # noqa: F811 - imported pytest fixtures
    key, policy = synthetic_key, synthetic_policy
    root = tmp_path.resolve() / "root"
    root.mkdir()
    (root / "public").mkdir()
    public = {
        "schema": "paeos.founder-public-key/1",
        "key_id": "synthetic-founder",
        "algorithm": "Ed25519",
        "public_key_hex": bytes(key.verify_key).hex(),
    }
    (root / "public/key.json").write_text(json.dumps(public))
    raw = signed(policy, key)
    (root / "policy.json").write_bytes(raw)
    canonical = json.dumps(
        json.loads(raw), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return {
        "root": root,
        "public_key_relative_path": "public/key.json",
        "policy_relative_path": "policy.json",
        "expected_key_id": "synthetic-founder",
        "expected_public_key_sha256": hashlib.sha256(bytes(key.verify_key)).hexdigest(),
        "expected_policy_sha256": hashlib.sha256(canonical).hexdigest(),
        "now": NOW,
    }


def _write_signed_policy(inputs, policy, key, *, domain):
    raw = signed(policy, key, domain=domain)
    (inputs["root"] / "policy.json").write_bytes(raw)
    canonical = json.dumps(
        json.loads(raw), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    inputs["expected_policy_sha256"] = hashlib.sha256(canonical).hexdigest()


@pytest.fixture
def derivative_policy(synthetic_policy):  # noqa: F811 - imported pytest fixture
    return _derivative_policy(synthetic_policy)


@pytest.fixture
def v2_inputs(inputs, derivative_policy, synthetic_key):  # noqa: F811
    _write_signed_policy(
        inputs, derivative_policy, synthetic_key, domain=b"PAEOS-DISCLOSURE-POLICY-V2\0"
    )
    return {**inputs, "expected_policy_version": 2}


def test_explicit_v2_loads_signed_derivative_snapshot_without_authority(loader, v2_inputs):
    result = loader.load_pinned_disclosure_policy(**v2_inputs)
    assert result.policy_id == "synthetic-policy"
    assert result.derivative_rules[0].input_data_class == "PUBLIC"
    assert result.derivative_rules[0].output_data_class == "PUBLIC"
    assert not any(hasattr(result, field) for field in ("enrolled", "current", "egress_permitted"))
    with pytest.raises(FrozenInstanceError):
        result.revision = 2


@pytest.mark.parametrize("selection", ["omitted", 1])
def test_v2_document_cannot_select_its_own_verifier(loader, v2_inputs, selection):
    if selection == "omitted":
        del v2_inputs["expected_policy_version"]
    else:
        v2_inputs["expected_policy_version"] = selection
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**v2_inputs)


def test_v1_document_rejected_when_independent_version_is_two(loader, inputs):
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**inputs, expected_policy_version=2)
    assert loader.load_pinned_disclosure_policy(**inputs, expected_policy_version=1).revision == 1


@pytest.mark.parametrize("version", [None, True, False, 0, -1, 3, 2.0, "2", {}, []])
def test_invalid_expected_version_denies_before_input_read(loader, inputs, monkeypatch, version):
    def forbidden(*args, **kwargs):
        pytest.fail("invalid expected version reached filesystem")

    monkeypatch.setattr(os, "open", forbidden)
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**inputs, expected_policy_version=version)


@pytest.mark.parametrize("field", ["expected_public_key_sha256", "expected_policy_sha256"])
def test_v2_rejects_wrong_independent_pins(loader, v2_inputs, field):
    v2_inputs[field] = "0" * 64
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**v2_inputs)


def test_v2_rejects_invalid_signature_even_when_repinned(loader, v2_inputs):
    path = v2_inputs["root"] / "policy.json"
    document = json.loads(path.read_bytes())
    document["revision"] = 2
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    path.write_bytes(raw)
    v2_inputs["expected_policy_sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**v2_inputs)


def test_v2_rejects_v1_signature_domain(loader, v2_inputs, derivative_policy, synthetic_key):  # noqa: F811
    _write_signed_policy(
        v2_inputs, derivative_policy, synthetic_key, domain=b"PAEOS-DISCLOSURE-POLICY-V1\0"
    )
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**v2_inputs)


@pytest.mark.parametrize(
    "clock",
    [
        datetime(2026, 10, 18),
        datetime(2026, 10, 16, tzinfo=UTC),
        datetime(2026, 10, 20, tzinfo=UTC),
    ],
)
def test_v2_rejects_invalid_future_or_expired_time(loader, v2_inputs, clock):
    v2_inputs["now"] = clock
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**v2_inputs)


@pytest.mark.parametrize(
    "mutation", ["class_secret", "input_secret", "output_secret", "declassification", "schema"]
)
def test_v2_rejects_secret_declassification_and_unexpected_schema(
    loader,
    v2_inputs,
    derivative_policy,
    synthetic_key,  # noqa: F811 - imported pytest fixture
    mutation,
):
    rule = derivative_policy["derivative_rules"][0]
    if mutation == "class_secret":
        derivative_policy["classes"][0]["data_class"] = "SECRET"
    elif mutation == "input_secret":
        rule["input_data_class"] = "SECRET"
    elif mutation == "output_secret":
        rule["output_data_class"] = "SECRET"
    elif mutation == "declassification":
        derivative_policy["classes"][0].update(
            class_id="REDACTED_INTERNAL_ENGINEERING_SOURCE", data_class="INTERNAL"
        )
        rule.update(
            class_id="REDACTED_INTERNAL_ENGINEERING_SOURCE",
            input_data_class="INTERNAL",
            output_data_class="PUBLIC",
        )
    else:
        derivative_policy["schema"] = "paeos.disclosure-policy/999"
    _write_signed_policy(
        v2_inputs, derivative_policy, synthetic_key, domain=b"PAEOS-DISCLOSURE-POLICY-V2\0"
    )
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**v2_inputs)


@pytest.mark.parametrize("relative", ["public/key.json", "policy.json"])
def test_v2_keeps_no_follow_reads(loader, v2_inputs, tmp_path, relative):
    path = v2_inputs["root"] / relative
    outside = tmp_path / "synthetic-outside-sentinel"
    path.rename(outside)
    before = outside.read_bytes()
    path.symlink_to(outside)
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**v2_inputs)
    assert outside.read_bytes() == before


def test_v2_reads_only_public_inputs_without_key_generation(loader, v2_inputs, monkeypatch):
    from nacl.signing import SigningKey

    original_open = os.open

    def readonly_open(path, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        return original_open(path, flags, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("loader attempted signing-key generation")

    monkeypatch.setattr(os, "open", readonly_open)
    monkeypatch.setattr(SigningKey, "generate", forbidden)
    assert len(loader.load_pinned_disclosure_policy(**v2_inputs).derivative_rules) == 1


def test_loads_exact_signed_policy_without_granting_authority(loader, inputs):
    result = loader.load_pinned_disclosure_policy(**inputs)
    assert result.policy_id == "synthetic-policy"
    assert result.founder_key_id == "synthetic-founder"
    assert result.revision == 1
    assert not any(hasattr(result, field) for field in ("enrolled", "current", "egress_permitted"))
    with pytest.raises(FrozenInstanceError):
        result.revision = 2


@pytest.mark.parametrize("field", ["expected_public_key_sha256", "expected_policy_sha256"])
def test_wrong_independent_pin_rejected(loader, inputs, field):
    inputs[field] = "0" * 64
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**inputs)


@pytest.mark.parametrize(
    "field,value",
    [
        ("expected_key_id", "worker-substituted-root"),
        ("expected_key_id", None),
        ("expected_public_key_sha256", None),
        ("expected_policy_sha256", "A" * 64),
        ("now", None),
        ("now", datetime(2026, 10, 18)),
    ],
)
def test_invalid_independent_inputs_reject_before_read(loader, inputs, field, value, monkeypatch):
    inputs[field] = value
    if field == "expected_key_id" and value:
        with pytest.raises(loader.DisclosureInputError):
            loader.load_pinned_disclosure_policy(**inputs)
        return

    def forbidden(*args, **kwargs):
        pytest.fail("invalid trusted inputs reached filesystem")

    monkeypatch.setattr(os, "open", forbidden)
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**inputs)


@pytest.mark.parametrize("mutation", ["private", "duplicate", "encoding", "size", "algorithm"])
def test_public_document_rejects_nonpublic_or_ambiguous_fields(loader, inputs, mutation):
    p = inputs["root"] / "public/key.json"
    obj = json.loads(p.read_text())
    if mutation == "private":
        obj["private_key"] = "synthetic-do-not-echo"
    elif mutation == "encoding":
        obj["public_key_hex"] = obj["public_key_hex"].upper()
    elif mutation == "algorithm":
        obj["algorithm"] = "RSA"
    raw = json.dumps(obj)
    if mutation == "duplicate":
        raw = raw[:-1] + ',"key_id":"synthetic-founder"}'
    elif mutation == "size":
        raw = " " * 4097
    p.write_text(raw)
    with pytest.raises(loader.DisclosureInputError) as exc:
        loader.load_pinned_disclosure_policy(**inputs)
    assert "synthetic-do-not-echo" not in str(exc.value)
    assert exc.value.__cause__ is None


@pytest.mark.parametrize(
    "path",
    ["../outside", "/outside", "public/../key.json", "public//key.json", "./policy.json", ""],
)
def test_relative_path_escape_rejected(loader, inputs, path):
    inputs["policy_relative_path"] = path
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**inputs)


@pytest.mark.parametrize("location", ["root", "ancestor", "public", "policy"])
def test_symlinks_are_not_followed(loader, inputs, tmp_path, location):
    root = inputs["root"]
    if location == "root":
        link = tmp_path / "root-link"
        link.symlink_to(root, target_is_directory=True)
        inputs["root"] = link
    elif location == "ancestor":
        link = tmp_path / "ancestor-link"
        link.symlink_to(tmp_path.resolve(), target_is_directory=True)
        inputs["root"] = link / "root"
    else:
        p = root / ("public/key.json" if location == "public" else "policy.json")
        outside = tmp_path / "outside-sentinel"
        p.rename(outside)
        p.symlink_to(outside)
        before = outside.read_bytes()
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**inputs)
    if location in ("public", "policy"):
        assert outside.read_bytes() == before


@pytest.mark.parametrize("kind", ["missing", "directory", "fifo", "oversize"])
def test_policy_file_bounds_and_type(loader, inputs, kind):
    p = inputs["root"] / "policy.json"
    p.unlink()
    if kind == "directory":
        p.mkdir()
    elif kind == "fifo":
        os.mkfifo(p)
    elif kind == "oversize":
        p.write_bytes(b"x" * (1024 * 1024 + 1))
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**inputs)


def test_invalid_signature_rejected_even_when_policy_pin_updated(loader, inputs):
    p = inputs["root"] / "policy.json"
    obj = json.loads(p.read_bytes())
    obj["revision"] = 2
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    p.write_bytes(canonical)
    inputs["expected_policy_sha256"] = hashlib.sha256(canonical).hexdigest()
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**inputs)


def test_expired_policy_rejected(loader, inputs):
    inputs["now"] = datetime(2026, 10, 20, tzinfo=UTC)
    with pytest.raises(loader.DisclosureInputError):
        loader.load_pinned_disclosure_policy(**inputs)


def test_descriptor_binding_survives_parent_path_replacement(loader, inputs, monkeypatch, tmp_path):
    root = inputs["root"]
    original_open = os.open
    moved = tmp_path / "moved"
    switched = False

    def replace_after_root_open(path, flags, *args, **kwargs):
        nonlocal switched
        fd = original_open(path, flags, *args, **kwargs)
        if path == "root" and flags & os.O_DIRECTORY and not switched:
            switched = True
            root.rename(moved)
            root.mkdir()
            (root / "policy.json").write_text("outside-sentinel-do-not-echo")
        return fd

    monkeypatch.setattr(os, "open", replace_after_root_open)
    result = loader.load_pinned_disclosure_policy(**inputs)
    assert switched and result.policy_id == "synthetic-policy"
    assert (root / "policy.json").read_text() == "outside-sentinel-do-not-echo"


def test_no_writes_or_ambient_key_generation(loader, inputs, monkeypatch):
    from nacl.signing import SigningKey

    original_open = os.open

    def readonly_open(path, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        return original_open(path, flags, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("loader attempted signing-key generation")

    monkeypatch.setattr(os, "open", readonly_open)
    monkeypatch.setattr(SigningKey, "generate", forbidden)
    assert loader.load_pinned_disclosure_policy(**inputs).revision == 1
