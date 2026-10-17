"""Filesystem CAS regressions for the bounded Council integrity contract."""
from dataclasses import replace
import json

import pytest

from kernel.cas import CAS, FilesystemCasStore
from runtime.critique import (
    CouncilDissensionViolationError, CouncilVote, CouncilVoteStance,
    record_council_deliberation, verify_council_deliberation_invariants,
)


@pytest.fixture
def cas(tmp_path):
    return CAS(FilesystemCasStore(tmp_path / "cas"))


def votes():
    return (
        CouncilVote("a", CouncilVoteStance.APPROVE, "family-a", "Accept"),
        CouncilVote("b", CouncilVoteStance.APPROVE, "family-b", "Accept"),
        CouncilVote("c", CouncilVoteStance.DISSENT, "family-c", "Unsafe boundary", ("risk",), ("isolate",)),
    )


def make_record(cas, supplied=None):
    return record_council_deliberation("vote", "proposal", "topic", supplied or votes(), cas)


def rebind(cas, record):
    payload = record.to_dict()
    payload["vote_cas_hash"] = ""
    return replace(record, vote_cas_hash=cas.put(json.dumps(payload, sort_keys=True).encode()))


def dissent_payload(vote):
    return {"voter_id": vote.voter_id, "stance": vote.stance.value, "argument": vote.argument,
            "risks": list(vote.risks_identified), "alternatives": list(vote.suggested_alternatives)}


def with_dissent(cas, record, dissent):
    return rebind(cas, replace(record, votes=(*record.votes[:2], dissent), dissenting_opinions=(dissent,)))


def assert_invalid(record, cas):
    assert verify_council_deliberation_invariants(record, cas)


def test_valid_record_and_filesystem_reopen(cas, tmp_path):
    record = make_record(cas)
    assert verify_council_deliberation_invariants(record, cas) == []
    reopened = CAS(FilesystemCasStore(tmp_path / "cas"))
    assert verify_council_deliberation_invariants(record, reopened) == []
    payload = json.loads(reopened.get(record.vote_cas_hash))
    assert payload["vote_cas_hash"] == ""
    assert "risks_identified" not in payload["dissenting_opinions"][0]
    supplied = make_record(reopened, record.votes)
    assert verify_council_deliberation_invariants(supplied, reopened) == []


@pytest.mark.parametrize("field,value", [
    ("voter_id", "other"), ("stance", "REJECT"), ("argument", "other argument"),
    ("risks", ["other risk"]), ("alternatives", ["other alternative"]),
    ("voter_id", 3), ("stance", ["DISSENT"]), ("argument", None),
    ("risks", "risk"), ("alternatives", [3]),
    ("risks", [""]), ("alternatives", [" "]),
])
def test_each_payload_field_is_bound_and_typed(cas, field, value):
    record = make_record(cas)
    dissent = record.votes[-1]
    payload = dissent_payload(dissent)
    payload[field] = value
    changed = replace(dissent, dissent_cas_hash=cas.put(json.dumps(payload).encode()))
    assert_invalid(with_dissent(cas, record, changed), cas)
    with pytest.raises(CouncilDissensionViolationError):
        make_record(cas, (*record.votes[:2], changed))


@pytest.mark.parametrize("raw", [b"[]", b"null", b"42", b'"text"', b"{", b"\xff", b"{}"])
def test_nonobject_malformed_or_absent_fields_rejected(cas, raw):
    record = make_record(cas)
    changed = replace(record.votes[-1], dissent_cas_hash=cas.put(raw))
    assert_invalid(with_dissent(cas, record, changed), cas)
    with pytest.raises(CouncilDissensionViolationError):
        make_record(cas, (*record.votes[:2], changed))


def test_missing_dissent_blob_rejected(cas):
    record = make_record(cas)
    changed = replace(record.votes[-1], dissent_cas_hash="0" * 64)
    assert_invalid(with_dissent(cas, record, changed), cas)
    with pytest.raises(CouncilDissensionViolationError, match="DISSENT_CAS_UNGROUNDED"):
        make_record(cas, (*record.votes[:2], changed))


@pytest.mark.parametrize("field,value", [
    ("vote_id", "altered"), ("proposal_id", "altered"), ("topic", "altered"),
    ("consensus_reached", False), ("vote_cas_hash", ""), ("vote_cas_hash", "0" * 64),
])
def test_whole_record_hash_binds_content_and_must_exist(cas, field, value):
    record = make_record(cas)
    assert_invalid(replace(record, **{field: value}), cas)


def test_existing_unrelated_whole_record_blob_rejected(cas):
    record = make_record(cas)
    assert_invalid(replace(record, vote_cas_hash=cas.put(b"{}")), cas)


@pytest.mark.parametrize("field,value", [
    ("argument", "altered"), ("model_family", "altered"),
    ("risks_identified", ("altered",)), ("suggested_alternatives", ("altered",)),
    ("stance", CouncilVoteStance.REJECT), ("dissent_cas_hash", "0" * 64),
])
def test_dissent_view_compares_all_dataclass_fields(cas, field, value):
    record = make_record(cas)
    changed = replace(record.dissenting_opinions[0], **{field: value})
    assert_invalid(rebind(cas, replace(record, dissenting_opinions=(changed,))), cas)


@pytest.mark.parametrize("mode", ["omitted", "extra", "duplicate", "duplicate_voter"])
def test_dissent_view_and_voter_uniqueness(cas, mode):
    record = make_record(cas)
    if mode == "omitted":
        changed = replace(record, dissenting_opinions=())
    elif mode == "extra":
        changed = replace(record, dissenting_opinions=(*record.dissenting_opinions, record.votes[0]))
    elif mode == "duplicate":
        changed = replace(record, dissenting_opinions=record.dissenting_opinions * 2)
    else:
        changed = replace(record, votes=(record.votes[0], record.votes[0], record.votes[-1]))
    assert_invalid(rebind(cas, changed), cas)


def test_duplicate_voter_rejected_at_creation(cas):
    original = votes()
    with pytest.raises(CouncilDissensionViolationError):
        make_record(cas, (original[0], original[0], original[-1]))


def test_missing_cas_cannot_verify_grounding(cas):
    assert_invalid(make_record(cas), None)
    record = make_record(cas, tuple(replace(v, stance=CouncilVoteStance.APPROVE) for v in votes()))
    assert_invalid(record, None)


def test_original_constitutional_controls(cas):
    record = make_record(cas)
    assert any("COUNCIL_QUORUM_VIOLATION" in v for v in verify_council_deliberation_invariants(replace(record, votes=record.votes[:2]), cas))
    empty = replace(record.votes[-1], argument=" ")
    assert any("DISSENT_EMPTY_ARGUMENT" in v for v in verify_council_deliberation_invariants(with_dissent(cas, record, empty), cas))
    assert any("CONSENSUS_AS_EVIDENCE_FORBIDDEN" in v for v in verify_council_deliberation_invariants(replace(record, is_consensus_used_as_evidence=True), cas))
    with pytest.raises(CouncilDissensionViolationError, match="CONSENSUS_AS_EVIDENCE_FORBIDDEN"):
        record_council_deliberation("v", "p", "t", votes(), cas, substitute_as_test_evidence=True)
    with pytest.raises(CouncilDissensionViolationError, match="DISSENT_CAS_STORAGE_REQUIRED"):
        record_council_deliberation("v", "p", "t", votes())


@pytest.mark.parametrize("stance", [CouncilVoteStance.DISSENT, CouncilVoteStance.REJECT, CouncilVoteStance.APPROVE])
def test_valid_empty_risk_lists_and_all_approve(cas, stance):
    original = votes()
    dissent = replace(original[-1], stance=stance, risks_identified=(), suggested_alternatives=())
    record = make_record(cas, (*original[:2], dissent))
    assert verify_council_deliberation_invariants(record, cas) == []


@pytest.mark.parametrize("field,value", [("risks_identified", "risk"), ("suggested_alternatives", (3,)), ("argument", None)])
def test_invalid_vote_field_types_rejected_at_creation(cas, field, value):
    original = votes()
    changed = replace(original[-1], **{field: value})
    with pytest.raises(CouncilDissensionViolationError):
        make_record(cas, (*original[:2], changed))


@pytest.mark.parametrize("blob", ["dissent", "record"])
def test_filesystem_corruption_fails_closed(cas, tmp_path, blob):
    record = make_record(cas)
    key = record.vote_cas_hash if blob == "record" else record.votes[-1].dissent_cas_hash
    (tmp_path / "cas" / key[:2] / key[2:]).write_bytes(b"tampered")
    reopened = CAS(FilesystemCasStore(tmp_path / "cas"))
    assert_invalid(record, reopened)
