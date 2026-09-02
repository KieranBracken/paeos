"""Contract tests for the SAKG post-seal emission bundle schema."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "sakg/schema/bundle.schema.json"
VALID = ROOT / "tests/sakg/fixtures/bundle/valid"
NODE_TYPES = {"Decision", "TradeOff", "Option", "Constraint", "Component", "Scar", "EvidenceRef"}
REQUIRED = {"bundle_id", "schema_version", "goal_id", "sealed_at", "namespace", "producer", "nodes"}
NODE_REQUIRED = {"id", "type", "status", "label", "summary", "facets", "evidence", "provenance"}
SHA = re.compile(r"^[0-9a-f]{64}$")


def _date(value: object) -> bool:
    if not isinstance(value, str): return False
    try: datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: return False
    return True


def _forbidden_keys(value: object) -> list[str]:
    bad = {"content", "payload", "evidence_payload", "inline_evidence", "raw_evidence"}
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower() in bad: found.append(key)
            found.extend(_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value: found.extend(_forbidden_keys(child))
    return found


def _errors(bundle: object) -> list[str]:
    if not isinstance(bundle, dict): return ["bundle"]
    errors = [f"missing:{k}" for k in sorted(REQUIRED - set(bundle))]
    errors.extend(f"unknown:{k}" for k in sorted(set(bundle) - REQUIRED))
    if bundle.get("schema_version") != "paeos.sakg.emission-bundle/v1": errors.append("schema_version")
    if not isinstance(bundle.get("bundle_id"), str) or not re.fullmatch(r"sakg-bundle:[a-z0-9-]+", str(bundle.get("bundle_id"))): errors.append("bundle_id")
    if not isinstance(bundle.get("goal_id"), str) or not re.fullmatch(r"g-[a-z0-9-]+", str(bundle.get("goal_id"))): errors.append("goal_id")
    if not _date(bundle.get("sealed_at")): errors.append("sealed_at")
    if not isinstance(bundle.get("namespace"), str) or not bundle.get("namespace"): errors.append("namespace")
    producer = bundle.get("producer")
    if not isinstance(producer, dict) or set(producer) != {"system", "version"}: errors.append("producer")
    nodes = bundle.get("nodes")
    if not isinstance(nodes, list) or not nodes: return errors + ["nodes"]
    for node in nodes:
        if not isinstance(node, dict): errors.append("node"); continue
        errors.extend(f"node:{x}" for x in sorted(NODE_REQUIRED - set(node)))
        errors.extend(f"node-unknown:{x}" for x in sorted(set(node) - NODE_REQUIRED))
        if node.get("type") not in NODE_TYPES: errors.append("node-type")
        if node.get("status") != "candidate": errors.append("node-status")
        if not isinstance(node.get("facets"), dict): errors.append("facets")
        if not isinstance(node.get("summary"), str) or len(node.get("summary", "")) > 280: errors.append("summary")
        evidence = node.get("evidence")
        if not isinstance(evidence, list): errors.append("evidence")
        else:
            for ref in evidence:
                if not isinstance(ref, dict) or set(ref) != {"hash", "uri", "kind", "reverification"}: errors.append("evidence-ref"); continue
                if not isinstance(ref.get("hash"), str) or not SHA.fullmatch(ref["hash"]): errors.append("evidence-hash")
        provenance = node.get("provenance")
        if not isinstance(provenance, dict) or set(provenance) != {"origin", "source_hash"}: errors.append("provenance")
        if _forbidden_keys(node): errors.append("inline-evidence")
    if _forbidden_keys(bundle): errors.append("inline-evidence")
    return errors


def test_schema_declares_append_only_bundle_and_allowed_types() -> None:
    schema = json.loads(SCHEMA.read_text())
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == REQUIRED
    assert set(schema["properties"]["nodes"]["items"]["properties"]["type"]["enum"]) == NODE_TYPES


def test_valid_bundle_fixtures_cover_all_emission_types() -> None:
    files = sorted(VALID.glob("*.json"))
    assert len(files) >= 7
    bundles = [json.loads(path.read_text()) for path in files]
    assert {bundle["nodes"][0]["type"] for bundle in bundles} == NODE_TYPES
    assert any(bundle["nodes"][0]["facets"].get("decision_state") == "rejected" for bundle in bundles)
    assert all(not _errors(bundle) for bundle in bundles)
