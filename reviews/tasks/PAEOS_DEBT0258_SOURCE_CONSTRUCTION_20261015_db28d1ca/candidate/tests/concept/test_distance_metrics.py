from __future__ import annotations

import math

from concept.inspiration import distance
from concept.store import ConceptStore

from ._inspiration_fixtures import append, concept, edge


def test_graph_distance_uses_shortest_hops_and_exponential_normalization(tmp_path):
    left = concept("left")
    middle = concept("middle")
    right = concept("right")
    with ConceptStore(tmp_path / "graph.db") as store:
        append(store, (left, middle, right), (edge(left, middle), edge(middle, right)))
        result = distance(left, right, store, {"weights": {"graph": 1.0}})
    assert result.graph_distance == round(1.0 - math.exp(-2.0 / 3.0), 6)
    assert result.aggregate_distance == result.graph_distance
    assert result.graph_unreachable is False
    assert result.weights_used == {"graph": 1.0}


def test_unreachable_graph_is_maximal_but_zero_vector_is_unavailable(tmp_path):
    left = concept("left", vector=(0.0, 0.0))
    right = concept("right", vector=(1.0, 0.0))
    with ConceptStore(tmp_path / "graph.db") as store:
        append(store, (left, right))
        result = distance(left, right, store)
    assert result.graph_distance == 1.0
    assert result.graph_unreachable is True
    assert result.vector_distance is None
    assert result.structural_distance is None
    assert result.missing_components == ("vector", "structural")
    assert result.weights_used == {"graph": 1.0}
    assert result.unscorable is False


def test_vector_distance_is_half_for_orthogonal_vectors(tmp_path):
    left = concept("left", vector=(1.0, 0.0))
    right = concept("right", vector=(0.0, 1.0))
    with ConceptStore(tmp_path / "vector.db") as store:
        append(store, (left, right))
        result = distance(left, right, store, {"weights": {"vector": 1.0}})
    assert result.vector_distance == 0.5
    assert result.aggregate_distance == 0.5


def test_structural_distance_uses_weighted_typed_neighbor_jaccard(tmp_path):
    left = concept("left")
    right = concept("right")
    left_target = concept("left-target")
    right_target = concept("right-target")
    edges = (
        edge(left, left_target, family="derivation", relation="derived_from"),
        edge(left, right_target, family="recombination", relation="contributes_to"),
        edge(right, right_target, family="derivation", relation="derived_from"),
    )
    with ConceptStore(tmp_path / "structure.db") as store:
        append(store, (left, right, left_target, right_target), edges)
        result = distance(left, right, store, {"weights": {"structural": 1.0}})
    assert result.structural_distance == 0.5
    assert result.aggregate_distance == 0.5


def test_no_available_component_is_explicitly_unscorable(tmp_path):
    left = {"label": "left"}
    right = {"label": "right"}
    with ConceptStore(tmp_path / "empty.db") as store:
        result = distance(left, right, store)
    assert result.aggregate_distance is None
    assert result.unscorable is True
    assert result.missing_components == ("graph", "vector", "structural")
