"""KAE and LOF Acquisition & Evidence Federation Adapter (Migration Wave 6 / W6).

Under the Controlling Target Architecture (FOUNDER_ECOSYSTEM_TARGET_ARCHITECTURE_v0.2.md)
and the Authoritative Migration DAG (07_MIGRATION_DEPENDENCY_DAG.yaml):
- KAE (Knowledge Acquisition Engine) is the canonical logical acquisition owner.
- LOF (Inspiration Engine / Laboratory of the Future) is the consumer of normalized
  artifact and evidence references, retaining its rich research domain state.
- Table splitting is strictly prohibited; existing LOF and KAE systems remain independently
  functional. Rollback boundary is achieved by disabling federation adapters.
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

from contracts.envelopes import (
    ArtifactRef,
    Criticality,
    DataClass,
    DomainOwner,
    EntityRef,
    EvidenceRef,
    TrustLabel,
)
from contracts.serialization import canonical_json_bytes, compute_canonical_hash

_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_CITATION_PATTERN = re.compile(
    rb"(?m)^[ \t]*(?:\[\d+\]|(?:CITATION|REFERENCE)[ \t]*[:#])[ \t]*(?P<body>[^\r\n]+?)[ \t]*(?:\r?\n|$)"
)


class FederationError(Exception):
    """Base error for KAE/LOF federation boundary."""


class AdapterDisabledError(FederationError):
    """Raised when an operation is attempted on a disabled federation adapter."""


class RevokedSourceAccessError(FederationError):
    """Raised when attempting to access raw content or derive unredacted knowledge from a revoked source."""


class MalformedSourcePayloadError(FederationError):
    """Raised when an incoming source payload violates schema or integrity rules."""


class SourceType(StrEnum):
    RESEARCH_PAPER = "RESEARCH_PAPER"
    PDF = "PDF"
    HTML_ARTICLE = "HTML_ARTICLE"
    GITHUB_REPO = "GITHUB_REPO"
    LOCAL_NOTE = "LOCAL_NOTE"
    TECHNICAL_DOC = "TECHNICAL_DOC"
    YOUTUBE_VIDEO = "YOUTUBE_VIDEO"
    OTHER = "OTHER"


class IngestionStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    REGISTERED = "REGISTERED"
    FETCHED = "FETCHED"
    HASHED = "HASHED"
    STORED = "STORED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    FAILED = "FAILED"
    REVOKED = "REVOKED"


class VenueType(StrEnum):
    PEER_REVIEWED_JOURNAL = "PEER_REVIEWED_JOURNAL"
    TOP_CONFERENCE = "TOP_CONFERENCE"
    PREPRINT = "PREPRINT"
    TEXTBOOK = "TEXTBOOK"
    TECHNICAL_BLOG = "TECHNICAL_BLOG"
    REPO = "REPO"
    OTHER = "OTHER"


@dataclass(frozen=True, slots=True)
class RightsPolicy:
    can_train_on_raw_text: bool = False
    can_train_on_features: bool = True
    retention_days: int = 365
    is_public_domain: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "can_train_on_raw_text": self.can_train_on_raw_text,
            "can_train_on_features": self.can_train_on_features,
            "retention_days": self.retention_days,
            "is_public_domain": self.is_public_domain,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RightsPolicy:
        return cls(
            can_train_on_raw_text=bool(data.get("can_train_on_raw_text", False)),
            can_train_on_features=bool(data.get("can_train_on_features", True)),
            retention_days=int(data.get("retention_days", 365)),
            is_public_domain=bool(data.get("is_public_domain", False)),
        )


@dataclass(frozen=True, slots=True)
class BibliographicMetadata:
    authors: str | None = None
    publisher: str | None = None
    venue: str | None = None
    publication_date: str | None = None
    doi: str | None = None
    arxiv_id: str | None = None
    isbn: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "authors": self.authors,
            "publisher": self.publisher,
            "venue": self.venue,
            "publication_date": self.publication_date,
            "doi": self.doi,
            "arxiv_id": self.arxiv_id,
            "isbn": self.isbn,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> BibliographicMetadata:
        return cls(
            authors=data.get("authors"),
            publisher=data.get("publisher"),
            venue=data.get("venue"),
            publication_date=data.get("publication_date"),
            doi=data.get("doi"),
            arxiv_id=data.get("arxiv_id"),
            isbn=data.get("isbn"),
        )


@dataclass(frozen=True, slots=True)
class CitationSpanRecord:
    cas_hash: str
    uri: str
    byte_start: int
    byte_end: int
    line_start: int
    line_end: int
    citation_hash: str
    text: str
    redacted: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cas_hash": self.cas_hash,
            "uri": self.uri,
            "byte_start": self.byte_start,
            "byte_end": self.byte_end,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "citation_hash": self.citation_hash,
            "text": self.text,
            "redacted": self.redacted,
        }


@dataclass(frozen=True, slots=True)
class FederatedEvidencePackage:
    source_id: str
    canonical_uri: str
    content_hash: str
    source_type: SourceType
    ingestion_status: IngestionStatus
    venue_type: VenueType
    credibility_score: float
    rights_policy: RightsPolicy
    bibliographic_meta: BibliographicMetadata
    artifact_ref: ArtifactRef
    evidence_ref: EvidenceRef
    citations: tuple[CitationSpanRecord, ...]
    revoked: bool = False
    raw_content_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "canonical_uri": self.canonical_uri,
            "content_hash": self.content_hash,
            "source_type": self.source_type.value,
            "ingestion_status": self.ingestion_status.value,
            "venue_type": self.venue_type.value,
            "credibility_score": self.credibility_score,
            "rights_policy": self.rights_policy.to_dict(),
            "bibliographic_meta": self.bibliographic_meta.to_dict(),
            "artifact_ref": self.artifact_ref.to_dict(),
            "evidence_ref": self.evidence_ref.to_dict(),
            "citations": [c.to_dict() for c in self.citations],
            "revoked": self.revoked,
            "raw_content_available": self.raw_content_available,
        }


@dataclass(frozen=True, slots=True)
class BatchFederationReport:
    total_processed: int
    federated_count: int
    deduplicated_count: int
    revoked_count: int
    quarantined_count: int
    quarantined_errors: tuple[str, ...]


class KaeLofFederationAdapter:
    """Production Federation Adapter bridging KAE acquisition and LOF research models."""

    def __init__(
        self,
        *,
        cas_store: dict[str, bytes] | None = None,
        enabled: bool = True,
    ) -> None:
        self._enabled = enabled
        self._cas_store: dict[str, bytes] = {} if cas_store is None else dict(cas_store)
        self._registry_by_hash: dict[str, FederatedEvidencePackage] = {}
        self._registry_by_id: dict[str, FederatedEvidencePackage] = {}
        self._registry_by_uri: dict[str, str] = {}  # uri -> content_hash
        self._dedup_count: int = 0

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def enable(self) -> None:
        self._enabled = True

    def disable(self) -> None:
        """Rollback boundary: disable federation adapter."""
        self._enabled = False

    def _check_enabled(self) -> None:
        if not self._enabled:
            raise AdapterDisabledError("KaeLofFederationAdapter is disabled (Rollback Boundary Active)")

    def put_cas(self, content: bytes) -> str:
        """Store bytes in KAE CAS and return SHA-256 digest."""
        digest = hashlib.sha256(content).hexdigest()
        self._cas_store[digest] = content
        return digest

    def get_cas(self, digest: str) -> bytes:
        self._check_enabled()
        if digest not in self._cas_store:
            raise KeyError(f"CAS blob not found: {digest}")
        return self._cas_store[digest]

    def federate_source(
        self,
        payload: Mapping[str, Any],
        *,
        raw_bytes: bytes | None = None,
    ) -> FederatedEvidencePackage:
        """Federate a single LOF source record into normalized KAE envelopes.
        
        Enforces:
        - Source-rights preservation and round-trip
        - Content hash and citation parity
        - Idempotent deduplication by hash or URI
        - Revoked source fail-closed isolation
        - Zero raw-content leakage when train_on_raw_text is False
        """
        self._check_enabled()

        source_id = str(payload.get("source_id", "")).strip()
        if not source_id:
            raise MalformedSourcePayloadError("source_id is required")

        raw_uri = str(payload.get("url") or payload.get("canonical_uri") or f"urn:lof:source:{source_id}").strip()
        canonical_uri = raw_uri

        # 1. Content and Hash Resolution
        content = raw_bytes
        content_hash = payload.get("content_hash") or payload.get("source_hash")
        if content is not None:
            calc_hash = hashlib.sha256(content).hexdigest()
            if content_hash and content_hash.lower() != calc_hash:
                raise MalformedSourcePayloadError(
                    f"Payload content_hash ({content_hash}) does not match raw bytes digest ({calc_hash})"
                )
            content_hash = calc_hash
            self._cas_store[content_hash] = content
        elif content_hash:
            content_hash = str(content_hash).lower().strip()
            if _HEX_64.fullmatch(content_hash) is None:
                raise MalformedSourcePayloadError(f"Invalid SHA-256 hash format: {content_hash}")
            if content_hash in self._cas_store:
                content = self._cas_store[content_hash]
        else:
            raise MalformedSourcePayloadError("Either raw_bytes or valid content_hash must be provided")

        # 2. Deduplication Gate
        if content_hash in self._registry_by_hash:
            self._dedup_count += 1
            existing = self._registry_by_hash[content_hash]
            return existing

        if canonical_uri in self._registry_by_uri:
            existing_hash = self._registry_by_uri[canonical_uri]
            if existing_hash in self._registry_by_hash:
                self._dedup_count += 1
                return self._registry_by_hash[existing_hash]

        # 3. Status and Revocation Evaluation
        status_raw = str(payload.get("ingestion_status", IngestionStatus.REGISTERED)).upper()
        is_revoked = bool(
            payload.get("revoked", False)
            or status_raw in (IngestionStatus.REJECTED, IngestionStatus.QUARANTINED, IngestionStatus.FAILED, IngestionStatus.REVOKED)
        )
        ingestion_status = IngestionStatus.REVOKED if is_revoked else IngestionStatus(status_raw)

        # 4. Rights Policy Resolution
        rights_raw = payload.get("rights_policy")
        if isinstance(rights_raw, RightsPolicy):
            rights_policy = rights_raw
        elif isinstance(rights_raw, Mapping):
            rights_policy = RightsPolicy.from_dict(rights_raw)
        else:
            rights_policy = RightsPolicy()

        # 5. Bibliographic Metadata Resolution
        meta_raw = payload.get("bibliographic_meta")
        if isinstance(meta_raw, BibliographicMetadata):
            bib_meta = meta_raw
        elif isinstance(meta_raw, Mapping):
            bib_meta = BibliographicMetadata.from_dict(meta_raw)
        else:
            bib_meta = BibliographicMetadata()

        # 6. Source Type and Venue
        try:
            stype_str = str(payload.get("source_type", SourceType.OTHER)).upper()
            source_type = SourceType(stype_str)
        except ValueError:
            source_type = SourceType.OTHER

        try:
            venue_str = str(payload.get("venue_type", VenueType.OTHER)).upper()
            venue_type = VenueType(venue_str)
        except ValueError:
            venue_type = VenueType.OTHER

        credibility = float(payload.get("credibility_score", 0.5))
        credibility = max(0.0, min(1.0, credibility))

        # 7. Mint Canonical ArtifactRef.v1
        artifact_ref = ArtifactRef(
            algorithm="sha256",
            digest=content_hash,
            media_type="text/plain",
            byte_length=len(content) if content is not None else int(payload.get("byte_length", 0)),
            owner=DomainOwner.KAE.value,
            locator=f"cas://{content_hash}",
            schema_ref="contracts/fixtures/golden_vectors.json#ArtifactRef",
        )
        artifact_ref.validate()

        # 8. Mint Canonical EvidenceRef.v1
        trust_label = (
            TrustLabel.TAINTED.value
            if is_revoked
            else (TrustLabel.PROBATIVE.value if credibility >= 0.7 else TrustLabel.CANDIDATE.value)
        )
        evidence_ref = EvidenceRef(
            artifact=artifact_ref,
            claim=f"Acquisition evidence for {source_id} ({source_type.value})",
            producer=EntityRef(
                kind="kae.citation_pipeline",
                owner=DomainOwner.KAE.value,
                local_id=f"kae:adapter:{source_id}",
                uri=canonical_uri,
            ),
            observed_at=datetime.now(timezone.utc).isoformat(),
            derivation="kae.federation.adapter.v1",
            reverification_recipe="re-read verified SHA-256 CAS address and verify byte-anchors",
            trust_label=trust_label,
        )
        evidence_ref.validate()

        # 9. Extract and Filter Citations (Rights Enforcement)
        citations_list: list[CitationSpanRecord] = []
        if content is not None and not is_revoked:
            try:
                for match in _CITATION_PATTERN.finditer(content):
                    start, end = match.span("body")
                    raw_span = content[start:end]
                    span_hash = hashlib.sha256(raw_span).hexdigest()
                    l_start = content.count(b"\n", 0, start) + 1
                    l_end = content.count(b"\n", 0, max(start, end - 1)) + 1

                    if rights_policy.can_train_on_raw_text or rights_policy.is_public_domain:
                        span_text = raw_span.decode("utf-8", errors="replace")
                        is_redacted = False
                    else:
                        span_text = f"[REDACTED: RIGHTS_RESTRICTED SHA256:{span_hash[:16]}]"
                        is_redacted = True

                    citations_list.append(
                        CitationSpanRecord(
                            cas_hash=content_hash,
                            uri=canonical_uri,
                            byte_start=start,
                            byte_end=end,
                            line_start=l_start,
                            line_end=l_end,
                            citation_hash=span_hash,
                            text=span_text,
                            redacted=is_redacted,
                        )
                    )
            except Exception:
                pass

        package = FederatedEvidencePackage(
            source_id=source_id,
            canonical_uri=canonical_uri,
            content_hash=content_hash,
            source_type=source_type,
            ingestion_status=ingestion_status,
            venue_type=venue_type,
            credibility_score=credibility,
            rights_policy=rights_policy,
            bibliographic_meta=bib_meta,
            artifact_ref=artifact_ref,
            evidence_ref=evidence_ref,
            citations=tuple(citations_list),
            revoked=is_revoked,
            raw_content_available=(content is not None and not is_revoked and rights_policy.can_train_on_raw_text),
        )

        # Register in indexes
        self._registry_by_hash[content_hash] = package
        self._registry_by_id[source_id] = package
        self._registry_by_uri[canonical_uri] = content_hash

        return package

    def access_raw_content(self, source_id_or_hash: str) -> bytes:
        """Secure accessor for raw content; enforces rights and revocation gates."""
        self._check_enabled()
        pkg = self._registry_by_id.get(source_id_or_hash) or self._registry_by_hash.get(source_id_or_hash)
        if pkg is None:
            raise KeyError(f"Source not registered: {source_id_or_hash}")

        if pkg.revoked:
            raise RevokedSourceAccessError(f"Access denied: source {pkg.source_id} has been revoked or quarantined")

        if not pkg.rights_policy.can_train_on_raw_text and not pkg.rights_policy.is_public_domain:
            raise PermissionError(f"Access denied: rights policy prohibits raw text extraction for {pkg.source_id}")

        return self.get_cas(pkg.content_hash)

    def batch_federate(
        self,
        records: Sequence[Mapping[str, Any]],
    ) -> tuple[tuple[FederatedEvidencePackage, ...], BatchFederationReport]:
        """Batch ingestion with isolated error containment (failure in one record does not abort batch)."""
        self._check_enabled()
        federated: list[FederatedEvidencePackage] = []
        quarantined_errors: list[str] = []
        initial_dedup = self._dedup_count
        revoked_count = 0

        for idx, rec in enumerate(records):
            try:
                pkg = self.federate_source(rec)
                federated.append(pkg)
                if pkg.revoked:
                    revoked_count += 1
            except Exception as exc:
                quarantined_errors.append(f"Record {idx} (id={rec.get('source_id', 'unknown')}): {type(exc).__name__}: {str(exc)}")

        batch_dedup = self._dedup_count - initial_dedup
        report = BatchFederationReport(
            total_processed=len(records),
            federated_count=len(federated),
            deduplicated_count=batch_dedup,
            revoked_count=revoked_count,
            quarantined_count=len(quarantined_errors),
            quarantined_errors=tuple(quarantined_errors),
        )
        return tuple(federated), report

    def query_corpus(
        self,
        *,
        source_type: SourceType | str | None = None,
        min_credibility: float | None = None,
        include_revoked: bool = False,
        venue_type: VenueType | str | None = None,
    ) -> list[FederatedEvidencePackage]:
        """Corpus query equivalence: returns matching records from federated store."""
        self._check_enabled()
        results: list[FederatedEvidencePackage] = []
        for pkg in self._registry_by_hash.values():
            if not include_revoked and pkg.revoked:
                continue
            if source_type and pkg.source_type != source_type:
                continue
            if venue_type and pkg.venue_type != venue_type:
                continue
            if min_credibility is not None and pkg.credibility_score < min_credibility:
                continue
            results.append(pkg)
        return sorted(results, key=lambda p: p.source_id)

    def get_by_id(self, source_id: str) -> FederatedEvidencePackage | None:
        self._check_enabled()
        return self._registry_by_id.get(source_id)

    def get_by_hash(self, content_hash: str) -> FederatedEvidencePackage | None:
        self._check_enabled()
        return self._registry_by_hash.get(content_hash)


__all__ = [
    "AdapterDisabledError",
    "BatchFederationReport",
    "BibliographicMetadata",
    "CitationSpanRecord",
    "FederatedEvidencePackage",
    "FederationError",
    "IngestionStatus",
    "KaeLofFederationAdapter",
    "MalformedSourcePayloadError",
    "RevokedSourceAccessError",
    "RightsPolicy",
    "SourceType",
    "VenueType",
]
