"""Constitution accessor — read-only view over the Z0 constitutional corpus.

Task B0.3 (PAEOS-8 §10; interface PAEOS-7.6 §… `constitution` server). Z0 is the immutable
constitution. This module *serves* it and nothing more:

    get_clause(id)          → the clause with that id
    query(pattern)          → clauses whose text matches a regex
    lineage(content_hash)   → resolve a content hash back to its clause + document origin

**FR-1 is enforced by absence, not by a runtime guard.** There is no `write`/`put`/`set`/
`update`/`delete`/`save` method anywhere in this module — mutating Z0 through the accessor is
a *compile-time impossibility*, not a check that could be bypassed. `Clause` is frozen and
the internal maps are never exposed for mutation. This is the constitutional analogue of the
CAS's on-read verification: the constitution can be read and searched, never altered.

Scope note (founder-ratified 2026-07-27): this is the **accessor only**. Populating
`constitution/PAEOS-0..6.md` and ratifying the canonical clause-id scheme is a separate
founder-legislated genesis act (see DEBT-0004). The accessor serves whatever Z0 contains and
is proven here against an in-repo fixture. The clause syntax it parses — `[cN]` markers, id
`"<document>#c<n>"` — mirrors SC-05's clause tagging and ClauseRef `"<parent>#c<n>"` shape,
and is provisional until that genesis act ratifies the real corpus.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "Clause",
    "ClauseLineage",
    "Constitution",
    "ConstitutionError",
    "DuplicateClause",
    "clause_hash",
]

# A clause marker: [c1], [c2], … (SC-05). The integer is the clause ordinal within its doc.
_CLAUSE_MARKER = re.compile(r"\[c(\d+)\]")
_README = "README.md"


# ---- errors ---------------------------------------------------------------


class ConstitutionError(Exception):
    """Base for constitution-accessor faults."""


class ClauseNotFound(ConstitutionError, KeyError):
    """A requested clause id or content hash is not in the corpus."""


class DuplicateClause(ConstitutionError):
    """Two clauses resolved to the same id — the corpus is malformed."""


# ---- value types (immutable) ---------------------------------------------


@dataclass(frozen=True, slots=True)
class Clause:
    """One addressable unit of constitutional text. Frozen: the accessor never mutates it."""

    id: str  # "<document>#c<ordinal>", e.g. "PAEOS-4-v1.1#c12"
    document: str  # the source document's identity (file stem)
    ordinal: int  # the N in [cN]
    text: str  # the clause body, stripped
    content_hash: str  # sha256 of `text` — ties the clause into PAEOS's content-addressing


@dataclass(frozen=True, slots=True)
class ClauseLineage:
    """Where a clause comes from: the clause itself, its document, and that document's
    declared predecessors (from optional `supersedes:` frontmatter). Amendment ancestry
    populates once the amendment machinery exists; at bootstrap Z0 is flat and immutable."""

    clause: Clause
    document: str
    supersedes: tuple[str, ...]


def clause_hash(text: str) -> str:
    """The content address of a clause body (matches `kernel.cas.content_hash` semantics)."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


# ---- frontmatter + clause parsing ----------------------------------------


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Return ({key: value}, body). Supports an optional leading `---`…`---` block with
    simple `key: value` lines. No YAML dependency; unknown structure is left in the body."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    block = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    meta: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, body


def _parse_clauses(document: str, body: str) -> list[Clause]:
    """Split `body` into clauses at each `[cN]` marker; a clause runs to the next marker."""
    markers = list(_CLAUSE_MARKER.finditer(body))
    clauses: list[Clause] = []
    for i, m in enumerate(markers):
        ordinal = int(m.group(1))
        start = m.end()
        stop = markers[i + 1].start() if i + 1 < len(markers) else len(body)
        text = body[start:stop].strip()
        clauses.append(
            Clause(
                id=f"{document}#c{ordinal}",
                document=document,
                ordinal=ordinal,
                text=text,
                content_hash=clause_hash(text),
            )
        )
    return clauses


def _parse_supersedes(meta: Mapping[str, str]) -> tuple[str, ...]:
    raw = meta.get("supersedes", "")
    parts = [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip()]
    return tuple(parts)


# ---- the accessor ---------------------------------------------------------


class Constitution:
    """Read-only, in-memory index of the constitutional corpus.

    Construct from a mapping of {document: markdown} or from a directory of `.md` files.
    Loads once; thereafter it only answers queries. No method mutates the corpus.

    **Ordering invariant (binding on every conformant implementation).** Any method that
    returns a sequence of clauses or ids — `query`, `clause_ids` — MUST return them in the
    canonical order **`(document, ordinal)`**, ascending, with `ordinal` compared as an
    integer (so `c2` precedes `c10`). `documents` returns identities sorted ascending. This
    order is *total and unique*: duplicate clause ids are rejected at construction
    (`DuplicateClause`), so `(document, ordinal)` is a unique key and the result is fully
    determined by the *set* of clauses — never by load order, dict iteration, or backend.
    Two conformant accessors over byte-identical corpora therefore return byte-identical
    sequences. This is a conformance requirement, not an implementation detail; the tests in
    `test_constitution.py` pin it.
    """

    def __init__(self, documents: Mapping[str, str]) -> None:
        clauses: dict[str, Clause] = {}
        by_hash: dict[str, Clause] = {}
        supersedes: dict[str, tuple[str, ...]] = {}
        for name in sorted(documents):
            meta, body = _split_frontmatter(documents[name])
            supersedes[name] = _parse_supersedes(meta)
            for clause in _parse_clauses(name, body):
                if clause.id in clauses:
                    raise DuplicateClause(f"duplicate clause id: {clause.id}")
                clauses[clause.id] = clause
                by_hash[clause.content_hash] = clause  # collision ⇒ identical text, fine
        self._clauses = clauses
        self._by_hash = by_hash
        self._supersedes = supersedes

    @classmethod
    def from_dir(cls, path: str | Path) -> Constitution:
        """Load every `*.md` in `path` (except README) as a document, keyed by file stem."""
        root = Path(path)
        docs = {
            p.stem: p.read_text(encoding="utf-8")
            for p in sorted(root.glob("*.md"))
            if p.name != _README
        }
        return cls(docs)

    def get_clause(self, clause_id: str) -> Clause:
        """Return the clause with `clause_id`. Raise ClauseNotFound if absent."""
        try:
            return self._clauses[clause_id]
        except KeyError:
            raise ClauseNotFound(f"no clause {clause_id!r}") from None

    def query(self, pattern: str) -> list[Clause]:
        """Return clauses whose text matches `pattern` (regex, case-insensitive).

        Ordering is the binding canonical `(document, ordinal)` — see the class-level
        ordering invariant. Deterministic and backend-independent."""
        rx = re.compile(pattern, re.IGNORECASE)
        hits = [c for c in self._clauses.values() if rx.search(c.text)]
        return sorted(hits, key=lambda c: (c.document, c.ordinal))

    def lineage(self, content_hash: str) -> ClauseLineage:
        """Resolve a content hash to its clause and document origin. Raise ClauseNotFound."""
        clause = self._by_hash.get(content_hash)
        if clause is None:
            raise ClauseNotFound(f"no clause with content hash {content_hash!r}")
        return ClauseLineage(
            clause=clause,
            document=clause.document,
            supersedes=self._supersedes.get(clause.document, ()),
        )

    def clause_ids(self) -> list[str]:
        """All clause ids in the canonical `(document, ordinal)` order (ordinal as int)."""
        return [
            c.id for c in sorted(self._clauses.values(), key=lambda c: (c.document, c.ordinal))
        ]

    def documents(self) -> list[str]:
        """All loaded document identities, sorted."""
        return sorted(self._supersedes)

    def __len__(self) -> int:
        return len(self._clauses)

    def __contains__(self, clause_id: object) -> bool:
        return clause_id in self._clauses
