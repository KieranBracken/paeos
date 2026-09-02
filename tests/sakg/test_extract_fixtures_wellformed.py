"""Well-formedness checks for the five F-EXTRACT-FIX cases."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests/sakg/fixtures/extract"
SCHEMA = ROOT / "sakg/schema/bundle.schema.json"
MANIFEST = ROOT / "sakg/extract/fixture_manifest.json"
REQUIRED = {"bundle_id", "schema_version", "goal_id", "sealed_at", "namespace", "producer", "nodes"}
NODE_REQUIRED = {"id", "type", "status", "label", "summary", "facets", "evidence", "provenance"}
NODE_TYPES = {"Decision", "TradeOff", "Option", "Constraint", "Component", "Scar", "EvidenceRef"}
SHA = re.compile(r"^[0-9a-f]{64}$")
ID = re.compile(r"^sakg://[^/]+/(?:Decision|TradeOff|Option|Constraint|Component|Scar|EvidenceRef)/[0-9A-HJKMNP-TV-Z]{26}$")


def _date(value: object) -> bool:
    if not isinstance(value, str): return False
    try: datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError: return False
    return True


def _validate(bundle: object) -> list[str]:
    if not isinstance(bundle, dict): return ["bundle"]
    errors = [f"missing:{k}" for k in sorted(REQUIRED - set(bundle))]
    errors += [f"unknown:{k}" for k in sorted(set(bundle) - REQUIRED)]
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
        errors += [f"node-missing:{k}" for k in sorted(NODE_REQUIRED - set(node))]
        errors += [f"node-unknown:{k}" for k in sorted(set(node) - NODE_REQUIRED)]
        if node.get("type") not in NODE_TYPES: errors.append("node-type")
        if node.get("status") != "candidate": errors.append("node-status")
        if not isinstance(node.get("id"), str) or not ID.fullmatch(node.get("id", "")): errors.append("node-id")
        if not isinstance(node.get("summary"), str) or len(node.get("summary", "")) > 280: errors.append("summary")
        if not isinstance(node.get("facets"), dict): errors.append("facets")
        evidence = node.get("evidence")
        if not isinstance(evidence, list) or not evidence: errors.append("evidence")
        else:
            for ref in evidence:
                if not isinstance(ref, dict) or set(ref) != {"hash", "uri", "kind", "reverification"}: errors.append("evidence-ref"); continue
                if not isinstance(ref.get("hash"), str) or not SHA.fullmatch(ref["hash"]): errors.append("evidence-hash")
        provenance = node.get("provenance")
        if not isinstance(provenance, dict) or set(provenance) != {"origin", "source_hash"}: errors.append("provenance"); continue
        origin = provenance.get("origin")
        if not isinstance(origin, dict) or set(origin) != {"system", "run_id"}: errors.append("origin")
        if not isinstance(provenance.get("source_hash"), str) or not SHA.fullmatch(provenance["source_hash"]): errors.append("source-hash")
    return errors


def test_five_goal_fixture_directories_and_schema_valid_expected_bundles() -> None:
    directories = sorted(path for path in FIXTURES.iterdir() if path.is_dir())
    assert len(directories) >= 5
    assert json.loads(SCHEMA.read_text())["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    manifest = json.loads(MANIFEST.read_text())
    assert set(manifest["cases"]) == {path.name for path in directories}
    for directory in directories:
        inputs = [path for path in (directory / "input").iterdir() if path.is_file()]
        expected = directory / "expected_bundle.json"
        assert inputs, directory
        assert expected.is_file(), directory
        bundle = json.loads(expected.read_text())
        assert not _validate(bundle), (directory, _validate(bundle))
        source_hash = hashlib.sha256(inputs[0].read_bytes()).hexdigest()
        assert bundle["nodes"][0]["provenance"]["source_hash"] == source_hash
        assert manifest["cases"][directory.name]["input_sha256"] == source_hash
        assert manifest["cases"][directory.name]["expected_bundle_sha256"] == hashlib.sha256(expected.read_bytes()).hexdigest()


def test_adversarial_cases_preserve_uncertainty() -> None:
    remanded = json.loads((FIXTURES / "adversarial-remanded/expected_bundle.json").read_text())
    missing = json.loads((FIXTURES / "adversarial-missing-l06/expected_bundle.json").read_text())
    assert remanded["nodes"][0]["facets"]["emission_policy"] == "suppressed-until-sealed"
    assert missing["nodes"][0]["facets"]["l06_matrix"] == "absent"
    assert missing["nodes"][0]["facets"]["lossless_claim"] is False
