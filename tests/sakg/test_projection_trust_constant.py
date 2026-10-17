from __future__ import annotations

import copy

from test_projection_schema import _errors, _response, _schema


def test_response_trust_is_structurally_constant() -> None:
    schema = _schema()
    response = _response()
    assert _errors(schema, response) == []
    forged = copy.deepcopy(response)
    forged["trust"] = "trusted"
    assert _errors(schema, forged)


def test_response_provenance_requires_all_reproducibility_hashes() -> None:
    schema = _schema()
    forged = copy.deepcopy(_response())
    del forged["provenance"]["query_hash"]
    assert _errors(schema, forged)
