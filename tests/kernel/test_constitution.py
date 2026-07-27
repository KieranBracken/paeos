"""B0.3 acceptance tests for the Constitution accessor (PAEOS-8 §10).

Covers: queries return expected clauses; FR-1 write-absence is a *compile-time* fact
(no write API exists — verified by introspection + source grep, not by catching a runtime
error); the Adversary (T4) cannot mutate Z0 through the accessor. Proven against an in-repo
fixture; the real constitution/PAEOS-0..6.md population is deferred (DEBT-0004).
"""

from __future__ import annotations

import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import kernel.constitution as constitution_module
import pytest
from kernel.constitution import (
    Clause,
    ClauseNotFound,
    Constitution,
    DuplicateClause,
    clause_hash,
)

# ---- fixture corpus -------------------------------------------------------

_DOC_A = """---
supersedes: derivation-A0, derivation-A1
---
# Doc A

[c1] Generation is cheap; verification is scarce. Route by verifiability.
[c2] Artifacts are durable; context is ephemeral. Everything load-bearing is a file.
"""

_DOC_B = """# Doc B (no frontmatter)

[c1] A kernel change requires a human ratifier and a passing Adversary review.
[c2] Deny by default: absence of authority is denial.
"""

FIXTURE = {"DOC-A": _DOC_A, "DOC-B": _DOC_B}


def _fixture() -> Constitution:
    return Constitution(FIXTURE)


# ---- get_clause / query / lineage -----------------------------------------


def test_get_clause_returns_expected_clause() -> None:
    c = _fixture().get_clause("DOC-A#c1")
    assert c.document == "DOC-A"
    assert c.ordinal == 1
    assert "verification is scarce" in c.text
    assert c.content_hash == clause_hash(c.text)


def test_get_clause_missing_raises() -> None:
    with pytest.raises(ClauseNotFound):
        _fixture().get_clause("DOC-A#c99")


def test_clauses_are_scoped_per_document() -> None:
    con = _fixture()
    assert con.get_clause("DOC-A#c1").text != con.get_clause("DOC-B#c1").text
    assert set(con.clause_ids()) == {"DOC-A#c1", "DOC-A#c2", "DOC-B#c1", "DOC-B#c2"}
    assert con.documents() == ["DOC-A", "DOC-B"]
    assert len(con) == 4
    assert "DOC-B#c2" in con


def test_query_returns_matching_clauses_sorted() -> None:
    con = _fixture()
    hits = con.query("deny")  # case-insensitive regex
    assert [c.id for c in hits] == ["DOC-B#c2"]
    hits2 = con.query(r"verif\w+")
    assert [c.id for c in hits2] == ["DOC-A#c1"]
    assert con.query("nothing matches this") == []


def test_lineage_resolves_hash_to_clause_and_provenance() -> None:
    con = _fixture()
    clause = con.get_clause("DOC-A#c1")
    lin = con.lineage(clause.content_hash)
    assert lin.clause == clause
    assert lin.document == "DOC-A"
    assert lin.supersedes == ("derivation-A0", "derivation-A1")  # from frontmatter
    assert con.lineage(con.get_clause("DOC-B#c1").content_hash).supersedes == ()


def test_lineage_unknown_hash_raises() -> None:
    with pytest.raises(ClauseNotFound):
        _fixture().lineage("0" * 64)


def test_duplicate_clause_id_rejected() -> None:
    with pytest.raises(DuplicateClause):
        Constitution({"D": "[c1] first\n[c1] second again"})


# ---- from_dir loading -----------------------------------------------------


def test_from_dir_loads_md_excluding_readme(tmp_path: Path) -> None:
    (tmp_path / "PAEOS-0.md").write_text("[c1] axiom one\n[c2] axiom two", encoding="utf-8")
    (tmp_path / "PAEOS-1.md").write_text("[c1] architecture clause", encoding="utf-8")
    (tmp_path / "README.md").write_text("[c1] not a clause — README is excluded", encoding="utf-8")
    con = Constitution.from_dir(tmp_path)
    assert con.documents() == ["PAEOS-0", "PAEOS-1"]
    assert con.get_clause("PAEOS-0#c2").text == "axiom two"
    assert con.query("README") == []  # README not loaded


def test_from_dir_on_empty_constitution_is_empty(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Z0; population deferred to genesis", encoding="utf-8")
    con = Constitution.from_dir(tmp_path)
    assert len(con) == 0
    with pytest.raises(ClauseNotFound):
        con.get_clause("anything#c1")


# ---- FR-1: write-absence is COMPILE-TIME, not a runtime guard --------------

_FORBIDDEN_VERBS = (
    "write", "put", "set", "update", "delete", "save", "store",
    "insert", "remove", "add", "edit", "mutate", "append",
)


def test_no_write_method_exists_on_accessor() -> None:
    # FR-1: mutation is impossible because there is no API for it — not because a guard
    # rejects it at runtime. Introspect the public surface for any write-shaped method.
    public = {name for name in dir(Constitution) if not name.startswith("_")}
    offenders = {name for name in public if any(v in name.lower() for v in _FORBIDDEN_VERBS)}
    assert offenders == set(), f"accessor exposes write-shaped methods: {offenders}"


def test_module_source_defines_no_write_path() -> None:
    # Verifier greps for any write path (PAEOS-8 §10 B0.3): the module must not define a
    # write-verb method nor open any file for writing.
    src = Path(constitution_module.__file__).read_text(encoding="utf-8")
    method_defs = set(re.findall(r"def\s+(\w+)", src))
    write_defs = {m for m in method_defs if any(m.lower().startswith(v) for v in _FORBIDDEN_VERBS)}
    assert write_defs == set(), f"module defines write-verb methods: {write_defs}"
    assert "open(" not in src  # no file handles at all → no write-mode handle possible


# ---- Adversary T4: cannot mutate Z0 via the accessor ----------------------


def test_returned_clause_is_frozen(tmp_path: Path) -> None:
    clause = _fixture().get_clause("DOC-A#c1")
    with pytest.raises(FrozenInstanceError):
        clause.text = "rewritten"  # type: ignore[misc]


def test_mutating_a_query_result_does_not_alter_corpus() -> None:
    con = _fixture()
    hits = con.query("kernel change")
    hits.clear()  # mutate the returned list
    assert [c.id for c in con.query("kernel change")] == ["DOC-B#c1"]  # corpus unchanged


def test_clause_object_replacement_does_not_persist() -> None:
    # Even holding a Clause, an Adversary has no path to write it back: get_clause always
    # returns the loaded instance, and there is no setter to install a forged one.
    con = _fixture()
    original = con.get_clause("DOC-A#c2")
    forged = Clause(id=original.id, document=original.document, ordinal=original.ordinal,
                    text="FORGED", content_hash=clause_hash("FORGED"))
    assert forged.text == "FORGED"
    assert con.get_clause("DOC-A#c2").text == original.text  # no write path exists
