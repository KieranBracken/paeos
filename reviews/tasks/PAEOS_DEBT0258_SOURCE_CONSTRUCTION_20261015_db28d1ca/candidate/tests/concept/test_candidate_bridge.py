from __future__ import annotations

import importlib
import re
from pathlib import Path
from typing import Any

import pytest
from concept.model import Hypothesis, Transformation
from concept.store import ConceptStore

from tests.concept._inspiration_fixtures import (
    _node,
    analogy_node,
    append,
    concept,
    hypothesis,
    uri_text,
)

URI_RE = re.compile(r"^concept://demo/outbox/[0-7][0-9A-HJKMNP-TV-Z]{25}$")


def _transformation() -> Any:
    return _node(
        "demo",
        "Transformation",
        Transformation(
            operator_name="bounded-transform",
            operator_version="v1",
            input_signature={"kind": "Concept"},
            output_signature={"kind": "Hypothesis"},
            implementation_ref="declarative://concept-os/bounded-transform/v1",
        ),
    )


def _seeded(path: Path, *, no_falsifier: bool = False):
    source, analogy, transform = concept("source"), analogy_node(), _transformation()
    if no_falsifier:
        candidate = _node(
            "demo",
            "Hypothesis",
            Hypothesis(
                proposition="A source pattern may reduce oscillation.",
                scope="bounded systems",
                assumptions=("sampling is fixed",),
                expected_observations=("amplitude decreases",),
                falsifiers=(),
                lifecycle="candidate",
            ),
        )
    else:
        candidate = hypothesis("A source pattern may reduce oscillation.")
    with ConceptStore(path) as store:
        append(store, (source, analogy, transform, candidate))
    return source, analogy, transform, candidate


def _build(store: ConceptStore, candidate: Any, source: Any, analogy: Any, transform: Any):
    bridge = importlib.import_module("concept.bridge")
    snapshot = store.snapshot_hash("demo")
    return bridge.build_candidate_envelope(
        store,
        uri_text(candidate.id),
        "bounded_experiment",
        source_concept_uris=(uri_text(source.id),),
        source_analogy_uris=(uri_text(analogy.id),),
        source_transformation_uris=(uri_text(transform.id),),
        sakg_reference_uris=("sakg://demo/constraint/1",),
        replay_manifest={
            "query_hash": "1" * 64,
            "graph_snapshot_hash": snapshot,
            "algorithm_versions": {"traversal": "v1"},
            "seeds": {"traversal": 7},
            "why": {uri_text(candidate.id): [{"relation": "derived_from", "steps": []}]},
        },
        score_vectors={"novelty": "0.990000", "relevance": "0.700000"},
    )


def test_envelope_contains_exact_provenance_replay_and_non_evidentiary_scores(tmp_path: Path) -> None:
    source, analogy, transform, candidate = _seeded(tmp_path / "bridge.db")
    with ConceptStore(tmp_path / "bridge.db") as store:
        envelope = _build(store, candidate, source, analogy, transform)
    data = envelope.to_dict()
    assert URI_RE.fullmatch(data["envelope_id"])
    assert data["schema_version"] == 1
    assert data["hypothesis_uri"] == uri_text(candidate.id)
    assert data["proposition"] == "A source pattern may reduce oscillation."
    assert data["scope"] == "test systems"
    assert data["assumptions"] == ["bounded input"]
    assert data["expected_observations"] == ["the result is observable"]
    assert data["falsifiers"] == ["the result is absent"]
    assert set(data["source_refs"]) == {uri_text(source.id), uri_text(analogy.id), uri_text(transform.id)}
    manifest = data["replay_manifest"]
    assert manifest["graph_snapshot_hash"]
    assert manifest["algorithm_versions"]
    assert manifest["seeds"]
    assert manifest["why_paths"]
    assert manifest["sakg_reference_uris"] == ["sakg://demo/constraint/1"]
    assert data["proposal_kind"] == "candidate_proposal"
    assert data["score_vectors"]["evidentiary"] is False
    assert "confidence" not in str(data).lower()


def test_missing_falsifier_is_rejected(tmp_path: Path) -> None:
    source, analogy, transform, candidate = _seeded(tmp_path / "missing.db", no_falsifier=True)
    bridge = importlib.import_module("concept.bridge")
    with ConceptStore(tmp_path / "missing.db") as store, pytest.raises(
        bridge.MissingFalsifierError
    ):
        _build(store, candidate, source, analogy, transform)


@pytest.mark.parametrize("field", ("scope", "assumptions", "expected_observations"))
def test_required_declarations_fail_closed(tmp_path: Path, field: str) -> None:
    source, analogy, transform = concept(field), analogy_node(), _transformation()
    payload = Hypothesis(
        proposition="A bounded proposition.",
        scope="" if field == "scope" else "bounded systems",
        assumptions=() if field == "assumptions" else ("fixed sampling",),
        expected_observations=() if field == "expected_observations" else ("it changes",),
        falsifiers=("it does not change",),
        lifecycle="candidate",
    )
    candidate = _node("demo", "Hypothesis", payload)
    bridge = importlib.import_module("concept.bridge")
    with ConceptStore(tmp_path / f"{field}.db") as store:
        append(store, (source, analogy, transform, candidate))
        with pytest.raises(bridge.CandidateExportBoundaryError):
            _build(store, candidate, source, analogy, transform)


def test_evaluation_kind_is_provider_neutral_and_truth_status_is_forbidden(tmp_path: Path) -> None:
    from dataclasses import replace

    source, analogy, transform, candidate = _seeded(tmp_path / "status.db")
    bridge = importlib.import_module("concept.bridge")
    with ConceptStore(tmp_path / "status.db") as store:
        envelope = _build(store, candidate, source, analogy, transform)
        assert envelope.to_dict()["requested_evaluation_kind"] == "bounded_experiment"
        assert "provider" not in envelope.to_dict()
        with pytest.raises(bridge.TruthBearingStatusForbiddenError):
            bridge.emit_candidate(store, replace(envelope, proposal_kind="validated"))
