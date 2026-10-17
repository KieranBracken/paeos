"""Shared fixtures for the read-only Concept OS MCP tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from concept.store import ConceptStore

from tests.concept._store_fixtures import hypothesis_node, outbox_event
from tests.concept._traverse_fixtures import append_graph, concept, edge


@dataclass(frozen=True, slots=True)
class SeededGraph:
    database: Path
    root_uri: str
    child_uri: str
    edge_uri: str
    hypothesis_uri: str


def seed_graph(path: Path) -> SeededGraph:
    root = concept("root concept")
    child = concept("child concept")
    hypothesis = hypothesis_node("A bounded read-only query remains exploratory.")
    graph_edge = edge(root, child, "derivation", "derived_from")
    with ConceptStore(path) as store:
        append_graph(store, (root, child, hypothesis), (graph_edge,))
        store.append_outbox_event(
            outbox_event(
                hypothesis,
                candidate={"observation": "query result remains untrusted"},
            )
        )
    return SeededGraph(
        database=path,
        root_uri=root.id.uri,
        child_uri=child.id.uri,
        edge_uri=graph_edge.id.uri,
        hypothesis_uri=hypothesis.id.uri,
    )


def seed_empty(path: Path) -> Path:
    with ConceptStore(path):
        pass
    return path
