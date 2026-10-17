from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''
import json
from concept.ids import canonical_json, content_hash, node_uri

preimage = {}
for key, value in {
    "representations": [],
    "payload": {"tags": {"gamma", "alpha", "beta"}, "label": "Cafe\u0301"},
    "type": "Concept",
    "provenance_refs": [],
    "namespace": "stable_ns",
    "schema_version": 1,
}.items():
    preimage[key] = value

canonical = canonical_json(preimage)
print(json.dumps({
    "canonical_hex": canonical.hex(),
    "content_hash": content_hash(canonical),
    "uri": node_uri("stable_ns", "Concept", preimage),
}, sort_keys=True))
'''


@pytest.mark.parametrize("hash_seed", ["random", "42", "0"])
@pytest.mark.parametrize("locale", ["C", "en_US.UTF-8"])
def test_identity_is_bit_exact_across_hash_seeds_and_locales(
    hash_seed: str, locale: str
) -> None:
    env = os.environ.copy()
    env.update({"PYTHONHASHSEED": hash_seed, "LC_ALL": locale, "LANG": locale})

    completed = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout)

    assert result == {
        "canonical_hex": (
            "7b226e616d657370616365223a22737461626c655f6e73222c227061796c6f6164223a7b"
            "226c6162656c223a22436166c3a9222c2274616773223a5b22616c706861222c22626574"
            "61222c2267616d6d61225d7d2c2270726f76656e616e63655f72656673223a5b5d2c2272"
            "6570726573656e746174696f6e73223a5b5d2c22736368656d615f76657273696f6e223a"
            "312c2274797065223a22436f6e63657074227d"
        ),
        "content_hash": "65c575f0faa701d22387fc853ef3a6f60655d45432ff86cb586ed3869ab80e57",
        "uri": "concept://stable_ns/concept/35RNTZ1YN7079271ZWGMZF79QP",
    }
