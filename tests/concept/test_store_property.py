from __future__ import annotations

import tempfile
import unicodedata

from concept.store import ConceptStore, NodeQuery
from hypothesis import given, settings
from hypothesis import strategies as st

from tests.concept._store_fixtures import concept_node


@settings(max_examples=20, deadline=None)
@given(
    st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=40).filter(
        lambda s: bool(s.strip())
    )
)
def test_any_valid_label_is_idempotent_and_round_trips(label: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = ConceptStore(f"{directory}/concept.db")
        node = concept_node(unicodedata.normalize("NFC", label))

        assert store.append_node(node) == store.append_node(node)
        assert list(store.iter_nodes(NodeQuery(namespace="demo"))) == [node]
        assert store.get_node(node.id.uri) == node
