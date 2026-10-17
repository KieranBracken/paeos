from __future__ import annotations

import asyncio
import importlib
import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from concept.inspiration import propose_analogies, propose_recombinations
from concept.model import SearchRequest
from concept.search import SearchOrchestra
from concept.store import ConceptStore

from tests.concept._inspiration_fixtures import append, concept, edge, uri_text


def test_seed_two_arm_inspiration_replay_mcp_and_outbox(tmp_path: Path) -> None:
    source, target, anchor = concept("source", domain_tags=("fluid",)), concept("target", domain_tags=("network",)), concept("anchor")
    database = tmp_path / "e2e.db"
    bridge = importlib.import_module("concept.bridge")
    with ConceptStore(database) as store:
        append(store, (source, target, anchor), (edge(source, anchor), edge(target, anchor)))
        analogy_result = propose_analogies(store, {"namespace": "demo", "source_uris": [uri_text(source.id)], "target_uris": [uri_text(target.id)]}, budget=4, seed=11)
        assert analogy_result.proposals
        analogy = analogy_result.proposals[0]
        append(store, (analogy.node,), analogy.edges)
        recombination_result = propose_recombinations(store, {"namespace": "demo", "source_uris": [uri_text(source.id), uri_text(target.id)], "scope": "bounded simulations"}, budget=4, seed=13)
        assert recombination_result.proposals
        recombination = recombination_result.proposals[0]
        append(store, (recombination.node,), recombination.edges)
        request = SearchRequest(
            namespace="demo", query_text="source target may combine", anchor_uris=(uri_text(source.id),), seed=19,
            desired_output_kinds=("Hypothesis",), algorithm_allow_list=(("traversal", "v1"), ("seeded-random-walk", "v1")),
            budgets={"max_expansions": 12, "max_results": 4, "max_hops": 3, "max_tokens": 500},
        )
        search_result = SearchOrchestra(store).search(request)
        assert set(search_result.algorithm_versions) == {"traversal", "seeded-random-walk"}
        assert search_result.replay_manifest["why"]
        assert any(item.candidate_uri == uri_text(recombination.node.id) for item in search_result.results)
        server = importlib.import_module("concept.mcp_server").build_concept_mcp_server(database)
        try:
            response = asyncio.run(server.call_tool("concept_hypothesis_get", {"uri": uri_text(recombination.node.id)}))
            payload = cast(dict[str, Any], response.structured_content)
            assert payload["results"][0]["hypothesis"]["type"] == "Hypothesis"
            assert payload["results"][0]["export_observations"] == []
        finally:
            server.close()
        envelope = bridge.build_candidate_envelope(
            store, uri_text(recombination.node.id), "bounded_experiment",
            source_concept_uris=(uri_text(source.id), uri_text(target.id)), source_analogy_uris=(uri_text(analogy.node.id),),
            sakg_reference_uris=("sakg://demo/constraint/network",), search_result=search_result,
            generator_trace={"analogy": analogy.trace, "recombination": recombination.trace},
        )
        event_uri = bridge.emit_candidate(store, envelope)
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            rows = connection.execute("SELECT uri, event_type, canonical_json FROM candidate_outbox WHERE hypothesis_uri = ?", (uri_text(recombination.node.id),)).fetchall()
        finally:
            connection.close()
    assert event_uri == rows[0][0]
    assert rows[0][1] == "EMITTED"
    assert json.loads(rows[0][2])["candidate"]["proposal_kind"] == "candidate_proposal"
