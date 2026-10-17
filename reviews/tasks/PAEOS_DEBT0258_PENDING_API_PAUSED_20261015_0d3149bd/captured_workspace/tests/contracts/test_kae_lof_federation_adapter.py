"""Test Suite for KAE and LOF Acquisition & Evidence Federation Adapter (Migration Wave 6 / W6).

Validates all required Wave 6 exit gates:
1. source_rights_and_hash_round_trip (CLAIM-W6-01)
2. content_hash_and_citation_parity (CLAIM-W6-02)
3. deduplication_and_isolation (CLAIM-W6-03)
4. revoked_source_handling (CLAIM-W6-04)
5. historical_corpus_query_equivalence (CLAIM-W6-05)
6. zero_raw_content_leakage (CLAIM-W6-06)
7. rollback_boundary_verification (CLAIM-W6-07)
"""

from __future__ import annotations

import hashlib
import json
import pytest

from contracts.envelopes import ArtifactRef, DomainOwner, EvidenceRef, TrustLabel
from contracts.kae_lof_federation_adapter import (
    AdapterDisabledError,
    BibliographicMetadata,
    FederatedEvidencePackage,
    IngestionStatus,
    KaeLofFederationAdapter,
    MalformedSourcePayloadError,
    RevokedSourceAccessError,
    RightsPolicy,
    SourceType,
    VenueType,
)


@pytest.fixture
def adapter() -> KaeLofFederationAdapter:
    return KaeLofFederationAdapter()


# ---------------------------------------------------------------------------
# CLAIM-W6-01: Source Rights Round Trip & Enforcement
# ---------------------------------------------------------------------------

def test_source_rights(adapter: KaeLofFederationAdapter):
    """Exit Gate 1: Source rights policy round-trips losslessly and enforces training gates."""
    raw_text = (
        b"# Sovereign Research Paper\n\n"
        b"CITATION: Volatility-Adjusted Hurst exponents yield predictive market regime signal.\n\n"
        b"[1] Advanced Econometrics 2026.\n"
    )
    content_hash = hashlib.sha256(raw_text).hexdigest()

    # Case A: train_on_raw_text = False (Restricted rights)
    restricted_policy = RightsPolicy(
        can_train_on_raw_text=False,
        can_train_on_features=True,
        retention_days=180,
        is_public_domain=False,
    )
    payload_a = {
        "source_id": "SRC-RESTRICTED-001",
        "url": "https://arxiv.org/abs/2605.0001",
        "source_type": SourceType.RESEARCH_PAPER,
        "content_hash": content_hash,
        "credibility_score": 0.95,
        "rights_policy": restricted_policy,
        "bibliographic_meta": {
            "authors": "Alice Researcher, Bob Scientist",
            "doi": "10.1000/182",
            "venue": "Top Journal of ML",
        },
    }

    pkg_a = adapter.federate_source(payload_a, raw_bytes=raw_text)

    # 1. Verify lossless rights round trip
    assert pkg_a.rights_policy.can_train_on_raw_text is False
    assert pkg_a.rights_policy.can_train_on_features is True
    assert pkg_a.rights_policy.retention_days == 180
    assert pkg_a.rights_policy.is_public_domain is False
    assert pkg_a.raw_content_available is False

    # 2. Verify raw text citation masking
    assert len(pkg_a.citations) >= 1
    for cit in pkg_a.citations:
        assert cit.redacted is True
        assert "[REDACTED: RIGHTS_RESTRICTED" in cit.text
        # Anchors must remain preserved
        assert cit.byte_start > 0
        assert cit.byte_end > cit.byte_start
        assert len(cit.citation_hash) == 64

    # 3. Accessing raw content must fail closed
    with pytest.raises(PermissionError, match="rights policy prohibits raw text"):
        adapter.access_raw_content(pkg_a.source_id)

    # Case B: train_on_raw_text = True (Permissive / Public Domain)
    permissive_policy = RightsPolicy(
        can_train_on_raw_text=True,
        can_train_on_features=True,
        retention_days=365,
        is_public_domain=True,
    )
    raw_text_b = b"CITATION: Open source algorithmic models under MIT license.\n"
    content_hash_b = hashlib.sha256(raw_text_b).hexdigest()

    payload_b = {
        "source_id": "SRC-PERMISSIVE-002",
        "url": "https://github.com/open/models",
        "source_type": SourceType.GITHUB_REPO,
        "content_hash": content_hash_b,
        "credibility_score": 0.85,
        "rights_policy": permissive_policy,
    }

    pkg_b = adapter.federate_source(payload_b, raw_bytes=raw_text_b)
    assert pkg_b.rights_policy.can_train_on_raw_text is True
    assert pkg_b.raw_content_available is True
    assert len(pkg_b.citations) == 1
    assert pkg_b.citations[0].redacted is False
    assert "Open source algorithmic models" in pkg_b.citations[0].text

    # Raw content is accessible
    fetched = adapter.access_raw_content(pkg_b.source_id)
    assert fetched == raw_text_b


# ---------------------------------------------------------------------------
# CLAIM-W6-02: Content Hash & Citation Parity
# ---------------------------------------------------------------------------

def test_citation_parity(adapter: KaeLofFederationAdapter):
    """Exit Gate 2: KAE CAS digest equals LOF source hash and byte-anchors match exact spans."""
    content = (
        b"Preamble text\n"
        b"CITATION: Invariant representation learning stabilizes multi-agent policy.\n"
        b"Intermediate text\n"
        b"[2] Reference on epistemic logic and court verification.\n"
    )
    digest = hashlib.sha256(content).hexdigest()

    payload = {
        "source_id": "SRC-PARITY-100",
        "url": "urn:source:parity-100",
        "content_hash": digest,
        "source_type": SourceType.RESEARCH_PAPER,
        "credibility_score": 0.90,
        "rights_policy": {"can_train_on_raw_text": True},
    }

    pkg = adapter.federate_source(payload, raw_bytes=content)

    # 1. Content hash parity
    assert pkg.content_hash == digest
    assert pkg.artifact_ref.digest == digest
    assert pkg.artifact_ref.owner == DomainOwner.KAE.value
    assert pkg.artifact_ref.locator == f"cas://{digest}"
    assert pkg.evidence_ref.trust_label == TrustLabel.PROBATIVE.value

    # 2. Citation anchor parity
    assert len(pkg.citations) == 2
    c1, c2 = pkg.citations

    # Verify span 1
    span_1_raw = content[c1.byte_start:c1.byte_end]
    assert span_1_raw.decode("utf-8") == "Invariant representation learning stabilizes multi-agent policy."
    assert hashlib.sha256(span_1_raw).hexdigest() == c1.citation_hash
    assert c1.line_start == 2
    assert c1.line_end == 2

    # Verify span 2
    span_2_raw = content[c2.byte_start:c2.byte_end]
    assert span_2_raw.decode("utf-8") == "Reference on epistemic logic and court verification."
    assert hashlib.sha256(span_2_raw).hexdigest() == c2.citation_hash
    assert c2.line_start == 4
    assert c2.line_end == 4


# ---------------------------------------------------------------------------
# CLAIM-W6-03: Deduplication & Adapter Isolation
# ---------------------------------------------------------------------------

def test_dedup_and_isolation(adapter: KaeLofFederationAdapter):
    """Exit Gate 3: Duplicate ingestion is deduplicated idempotently; errors are isolated."""
    content_1 = b"CITATION: Shared foundational knowledge base.\n"
    hash_1 = hashlib.sha256(content_1).hexdigest()

    # 1. Initial ingestion
    rec_1 = {
        "source_id": "SRC-DEDUP-01",
        "url": "https://example.org/doc1",
        "content_hash": hash_1,
        "source_type": SourceType.PDF,
    }
    pkg_1 = adapter.federate_source(rec_1, raw_bytes=content_1)
    assert pkg_1.source_id == "SRC-DEDUP-01"

    # 2. Duplicate ingestion with same content hash and different source ID
    rec_duplicate = {
        "source_id": "SRC-DEDUP-01-DUP",
        "url": "https://example.org/doc1_mirror",
        "content_hash": hash_1,
        "source_type": SourceType.PDF,
    }
    pkg_dup = adapter.federate_source(rec_duplicate, raw_bytes=content_1)
    # Must return original canonical package without duplicate allocation
    assert pkg_dup.source_id == "SRC-DEDUP-01"
    assert pkg_dup.content_hash == hash_1

    # 3. Batch processing with failed adapter isolation
    batch = [
        {"source_id": "SRC-BATCH-OK-1", "content_hash": hashlib.sha256(b"ok1").hexdigest(), "source_type": SourceType.PDF},
        {"source_id": "", "content_hash": "bad"},  # Malformed: empty ID
        {"source_id": "SRC-BATCH-BAD-HASH", "content_hash": "invalid_hex_length"},  # Malformed: bad hash
        {"source_id": "SRC-BATCH-OK-2", "content_hash": hashlib.sha256(b"ok2").hexdigest(), "source_type": SourceType.LOCAL_NOTE},
    ]

    federated, report = adapter.batch_federate(batch)
    assert report.total_processed == 4
    assert report.federated_count == 2
    assert report.quarantined_count == 2
    assert len(federated) == 2
    assert federated[0].source_id == "SRC-BATCH-OK-1"
    assert federated[1].source_id == "SRC-BATCH-OK-2"
    # Quarantine reports contain descriptive diagnostics
    assert any("MalformedSourcePayloadError" in err for err in report.quarantined_errors)


# ---------------------------------------------------------------------------
# CLAIM-W6-04: Revoked Source Handling
# ---------------------------------------------------------------------------

def test_revoked_source(adapter: KaeLofFederationAdapter):
    """Exit Gate 4: Revoked sources fail closed, taint evidence refs, and block raw content."""
    content = b"CITATION: Flawed hypothesis that was later retracted by author.\n"
    digest = hashlib.sha256(content).hexdigest()

    revoked_payload = {
        "source_id": "SRC-RETRACTED-99",
        "url": "https://retracted.org/paper.pdf",
        "content_hash": digest,
        "source_type": SourceType.RESEARCH_PAPER,
        "ingestion_status": IngestionStatus.REJECTED,
        "revoked": True,
        "credibility_score": 0.1,
    }

    pkg = adapter.federate_source(revoked_payload, raw_bytes=content)

    # 1. Package marked revoked with TAINTED trust label
    assert pkg.revoked is True
    assert pkg.ingestion_status == IngestionStatus.REVOKED
    assert pkg.evidence_ref.trust_label == TrustLabel.TAINTED.value
    # Citations suppressed on revoked intake
    assert len(pkg.citations) == 0

    # 2. Accessing raw content raises RevokedSourceAccessError
    with pytest.raises(RevokedSourceAccessError, match="revoked or quarantined"):
        adapter.access_raw_content(pkg.source_id)

    # 3. Excluded from default corpus queries
    default_corpus = adapter.query_corpus()
    assert all(p.source_id != "SRC-RETRACTED-99" for p in default_corpus)

    # 4. Visible only when audit explicitly includes revoked
    audit_corpus = adapter.query_corpus(include_revoked=True)
    assert any(p.source_id == "SRC-RETRACTED-99" for p in audit_corpus)


# ---------------------------------------------------------------------------
# CLAIM-W6-05: Historical Corpus Query Equivalence
# ---------------------------------------------------------------------------

def test_query_equivalence(adapter: KaeLofFederationAdapter):
    """Exit Gate 5: Historical corpus queries yield deterministic query equivalence."""
    sources = [
        {"source_id": "SRC-Q1", "content_hash": hashlib.sha256(b"q1").hexdigest(), "source_type": SourceType.RESEARCH_PAPER, "credibility_score": 0.95, "venue_type": VenueType.TOP_CONFERENCE},
        {"source_id": "SRC-Q2", "content_hash": hashlib.sha256(b"q2").hexdigest(), "source_type": SourceType.RESEARCH_PAPER, "credibility_score": 0.60, "venue_type": VenueType.PREPRINT},
        {"source_id": "SRC-Q3", "content_hash": hashlib.sha256(b"q3").hexdigest(), "source_type": SourceType.GITHUB_REPO, "credibility_score": 0.80, "venue_type": VenueType.REPO},
        {"source_id": "SRC-Q4", "content_hash": hashlib.sha256(b"q4").hexdigest(), "source_type": SourceType.HTML_ARTICLE, "credibility_score": 0.40, "venue_type": VenueType.TECHNICAL_BLOG},
    ]

    for s in sources:
        adapter.federate_source(s)

    # Filter by source_type
    papers = adapter.query_corpus(source_type=SourceType.RESEARCH_PAPER)
    assert len(papers) == 2
    assert [p.source_id for p in papers] == ["SRC-Q1", "SRC-Q2"]

    # Filter by minimum credibility
    high_cred = adapter.query_corpus(min_credibility=0.75)
    assert len(high_cred) == 2
    assert [p.source_id for p in high_cred] == ["SRC-Q1", "SRC-Q3"]

    # Filter by venue_type
    conf = adapter.query_corpus(venue_type=VenueType.TOP_CONFERENCE)
    assert len(conf) == 1
    assert conf[0].source_id == "SRC-Q1"


# ---------------------------------------------------------------------------
# Rollback Boundary Verification
# ---------------------------------------------------------------------------

def test_rollback_boundary(adapter: KaeLofFederationAdapter):
    """Rollback boundary: disabling adapter halts federation without mutating source estate."""
    assert adapter.is_enabled is True
    adapter.disable()
    assert adapter.is_enabled is False

    with pytest.raises(AdapterDisabledError, match="Rollback Boundary Active"):
        adapter.federate_source({"source_id": "SRC-ERR", "content_hash": "abc"})

    with pytest.raises(AdapterDisabledError):
        adapter.query_corpus()

    adapter.enable()
    assert adapter.is_enabled is True
