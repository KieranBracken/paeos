"""Contract tests for the SAEOS-1 §4.2 universal SAKG envelope."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "sakg/schema/envelope.schema.json"
VALID = ROOT / "tests/sakg/fixtures/envelope/valid"
INVALID = ROOT / "tests/sakg/fixtures/envelope/invalid"
NODE_TYPES = {"Decision", "Problem", "Option", "Constraint", "Objective", "TradeOff", "Mechanism", "Pattern", "Component", "Outcome", "Scar", "EvidenceRef"}
STATUSES = {"candidate", "canonical", "superseded", "refuted"}
REQUIRED = {"id", "type", "namespace", "facets", "label", "summary", "provenance", "evidence", "status", "confidence", "valid_from", "valid_until", "falsifier", "coordinates"}
SHA = re.compile(r"^[0-9a-f]{64}$")
ID = re.compile(r"^sakg://[^/]+/(?:Decision|Problem|Option|Constraint|Objective|TradeOff|Mechanism|Pattern|Component|Outcome|Scar|EvidenceRef)/[0-9A-HJKMNP-TV-Z]{26}$")


def _date(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _errors(node: object) -> list[str]:
    if not isinstance(node, dict):
        return ["node is not an object"]
    errors: list[str] = []
    missing = REQUIRED - set(node)
    errors.extend(f"missing:{key}" for key in sorted(missing))
    errors.extend(f"unknown:{key}" for key in sorted(set(node) - REQUIRED))
    if not isinstance(node.get("id"), str) or not ID.fullmatch(str(node.get("id"))):
        errors.append("id")
    if node.get("type") not in NODE_TYPES:
        errors.append("type")
    if not isinstance(node.get("namespace"), str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", str(node.get("namespace"))):
        errors.append("namespace")
    if not isinstance(node.get("facets"), dict) or any(not isinstance(v, dict) for v in node.get("facets", {}).values()):
        errors.append("facets")
    if not isinstance(node.get("label"), str) or not 1 <= len(node.get("label", "")) <= 160:
        errors.append("label")
    if not isinstance(node.get("summary"), str) or len(node.get("summary", "")) > 280:
        errors.append("summary")
    provenance = node.get("provenance")
    if not isinstance(provenance, dict) or set(provenance) != {"origin", "author_kind", "ingested_at", "source_hash"}:
        errors.append("provenance")
    else:
        origin = provenance.get("origin")
        if not isinstance(origin, dict) or set(origin) != {"system", "run_id"} or not all(isinstance(origin.get(k), str) and origin.get(k) for k in ("system", "run_id")):
            errors.append("origin")
        if provenance.get("author_kind") not in {"human", "agent", "ingest", "inferred"}:
            errors.append("author_kind")
        if not _date(provenance.get("ingested_at")) or not isinstance(provenance.get("source_hash"), str) or not SHA.fullmatch(provenance.get("source_hash", "")):
            errors.append("provenance_value")
    evidence = node.get("evidence")
    if not isinstance(evidence, list):
        errors.append("evidence")
    else:
        for ref in evidence:
            if not isinstance(ref, dict) or set(ref) != {"hash", "uri", "kind", "reverification"}:
                errors.append("evidence_ref")
                continue
            if not isinstance(ref["hash"], str) or not SHA.fullmatch(ref["hash"]): errors.append("evidence_hash")
            if not all(isinstance(ref[key], str) and ref[key] for key in ("uri", "reverification")): errors.append("evidence_text")
            if ref["kind"] not in {"artifact", "test", "report", "observation", "decision", "source"}: errors.append("evidence_kind")
    if node.get("status") not in STATUSES:
        errors.append("status")
    if not isinstance(node.get("confidence"), (int, float)) or isinstance(node.get("confidence"), bool) or not 0 <= node.get("confidence", -1) <= 1:
        errors.append("confidence")
    if not _date(node.get("valid_from")):
        errors.append("valid_from")
    if node.get("valid_until") is not None and not _date(node.get("valid_until")):
        errors.append("valid_until")
    if node.get("falsifier") is not None and (not isinstance(node.get("falsifier"), str) or not node.get("falsifier")):
        errors.append("falsifier")
    if node.get("status") == "refuted" and not isinstance(node.get("falsifier"), str):
        errors.append("refuted_without_falsifier")
    if node.get("status") == "canonical" and not evidence:
        errors.append("canonical_without_evidence")
    coordinates = node.get("coordinates")
    if not isinstance(coordinates, dict) or any(not isinstance(v, list) or any(not isinstance(x, str) or not x for x in v) for v in coordinates.values()):
        errors.append("coordinates")
    return errors


def test_schema_is_draft_2020_12_and_declares_every_field() -> None:
    schema = json.loads(SCHEMA.read_text())
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert set(schema["required"]) == REQUIRED
    assert schema["properties"]["confidence"]["readOnly"] is True
    assert set(schema["properties"]["status"]["enum"]) == STATUSES


def test_valid_fixture_corpus_covers_all_fields_and_statuses() -> None:
    files = sorted(VALID.glob("*.json"))
    assert len(files) >= 12
    nodes = [json.loads(path.read_text()) for path in files]
    assert {node["status"] for node in nodes} == STATUSES
    assert all(set(node) == REQUIRED and not _errors(node) for node in nodes)


def test_invalid_fixture_corpus_is_rejected() -> None:
    files = sorted(INVALID.glob("*.json"))
    assert len(files) >= 8
    assert all(_errors(json.loads(path.read_text())) for path in files)


def test_explicit_invariant_violations_are_present() -> None:
    names = {path.stem for path in INVALID.glob("*.json")}
    assert {"authored-confidence", "frequency-promotion", "deleted-node"} <= names
    by_name = {path.stem: json.loads(path.read_text()) for path in INVALID.glob("*.json")}
    assert "unknown:confidence_source" in _errors(by_name["authored-confidence"])
    assert "canonical_without_evidence" in _errors(by_name["frequency-promotion"])
    assert "status" in _errors(by_name["deleted-node"])


def test_refuted_nodes_retain_falsifier_and_canonical_nodes_retain_evidence() -> None:
    for path in VALID.glob("*.json"):
        node = json.loads(path.read_text())
        if node["status"] == "refuted":
            assert node["falsifier"]
        if node["status"] == "canonical":
            assert node["evidence"]
