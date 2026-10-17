#!/usr/bin/env python3
"""Append-only deterministic AST/taxonomy projection for SAEOS-1 Task 23."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Iterable

from sakg.store import Edge, GraphStore

NAMESPACE = "paeos-history"
INGESTED_AT = "2026-09-04T00:00:00Z"
ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _id(namespace: str, kind: str, key: str) -> str:
    number = int.from_bytes(hashlib.sha256(f"{namespace}:{kind}:{key}".encode()).digest()[:16], "big")
    chars = ["0"] * 26
    for index in range(25, -1, -1):
        number, remainder = divmod(number, 32)
        chars[index] = ALPHABET[remainder]
    return f"sakg://{namespace}/{kind}/{''.join(chars)}"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _node(namespace: str, kind: str, key: str, label: str, summary: str,
          facets: dict[str, object], source_hash: str, uri: str,
          coordinates: dict[str, list[str]]) -> dict[str, object]:
    return {
        "id": _id(namespace, kind, key), "type": kind, "namespace": namespace,
        "facets": facets, "label": label[:160], "summary": summary[:280],
        "provenance": {"origin": {"system": "sakg-live-index", "run_id": "task-23-live-graph-index"},
                       "author_kind": "ingest", "ingested_at": INGESTED_AT, "source_hash": source_hash},
        "evidence": [{"hash": source_hash, "uri": uri, "kind": "source",
                       "reverification": "rerun scripts/sakg_live_graph_index.py against the source tree"}],
        "status": "candidate", "confidence": 0.6, "valid_from": INGESTED_AT,
        "valid_until": None, "falsifier": None, "coordinates": coordinates,
    }


def _edge(namespace: str, source: str, target: str, family: str, relation: str, key: str) -> Edge:
    edge_key = hashlib.sha256(f"{family}:{relation}:{key}".encode()).hexdigest()[:26].upper()
    return Edge(edge_id=f"edge:{family}:{edge_key}", namespace=namespace, source=source, target=target,
                family=family, relation=relation,
                properties={"origin": "task-23-live-graph-index", "deterministic": True},
                evidence=(), created_at=INGESTED_AT)


def _files(root: Path) -> list[Path]:
    files: list[Path] = []
    for top in ("paeos", "kernel"):
        directory = root / top
        if directory.is_dir():
            files.extend(path for path in directory.rglob("*.py") if path.is_file())
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _imports(tree: ast.AST) -> set[str]:
    result: set[str] = set()
    for item in ast.walk(tree):
        if isinstance(item, ast.Import):
            result.update(alias.name.split(".", 1)[0] for alias in item.names)
        elif isinstance(item, ast.ImportFrom) and item.module:
            result.add(item.module.split(".", 1)[0])
    return result


def _patterns(tree: ast.AST) -> list[str]:
    dump = ast.dump(tree, include_attributes=False)
    result = {"module_boundary"}
    if "ClassDef" in dump:
        result.add("typed_object")
    if "Try" in dump or "ExceptHandler" in dump:
        result.add("fail_closed_boundary")
    if "dataclass" in dump:
        result.add("immutable_record")
    if "Await" in dump or "AsyncFunctionDef" in dump:
        result.add("async_execution")
    return sorted(result)


def _taxonomies(namespace: str, paths: Iterable[str], source_hash: str) -> list[dict[str, object]]:
    keys = {"paeos", "kernel"}
    for path in paths:
        parts = path.split("/")
        keys.update("/".join(parts[:index]) for index in range(1, len(parts)))
    return [_node(namespace, "TaxonomyNode", key, f"taxonomy:{key}",
                  f"Deterministic source taxonomy node for {key}.",
                  {"path": {"value": key}, "kind": {"value": "source_taxonomy"}}, source_hash,
                  f"source://{key}", {"domain": ["source", key.split("/", 1)[0]]}) for key in sorted(keys)]


def index_repository(root: str | Path, db_path: str | Path = "sakg.db",
                     namespace: str = NAMESPACE) -> dict[str, object]:
    repository = Path(root).resolve()
    paths = _files(repository)
    if not paths:
        raise FileNotFoundError(f"no Python modules found below {repository}/paeos or kernel")
    records: list[tuple[str, ast.Module, str]] = []
    for path in paths:
        raw = path.read_bytes()
        try:
            tree = ast.parse(raw.decode("utf-8"), filename=str(path))
        except (UnicodeDecodeError, SyntaxError) as exc:
            raise ValueError(f"cannot parse {path.relative_to(repository)}") from exc
        records.append((path.relative_to(repository).as_posix(), tree, _sha(raw)))
    source_hash = _sha("\n".join(f"{path}:{digest}" for path, _tree, digest in records).encode())

    with GraphStore(db_path, namespace) as store:
        taxonomy = _taxonomies(namespace, (path for path, _tree, _digest in records), source_hash)
        for node in taxonomy:
            store.append_node(node)
        taxonomy_ids = {node["facets"]["path"]["value"]: node["id"] for node in taxonomy}
        component_ids: dict[str, str] = {}
        mechanisms_by_module: dict[str, list[str]] = {}
        for path, tree, digest in records:
            module = path[:-3].replace("/", ".")
            component = _node(namespace, "Component", path, f"component:{module}",
                              f"Python module indexed from {path}.",
                              {"module_path": {"value": path}, "qualname": {"value": module}}, digest,
                              f"source://{path}", {"domain": [path.split("/", 1)[0]], "language": ["python"]})
            store.append_node(component)
            component_ids[module] = str(component["id"])
            parent_key = path.rsplit("/", 1)[0] if "/" in path else path.split("/", 1)[0]
            parent = taxonomy_ids.get(parent_key) or taxonomy_ids[path.split("/", 1)[0]]
            store.append_edge(_edge(namespace, str(component["id"]), str(parent), "structural", "part_of", path))
            for pattern in _patterns(tree):
                key = f"{path}:pattern:{pattern}"
                node = _node(namespace, "Pattern", key, f"pattern:{pattern}:{module}",
                             f"AST pattern {pattern} observed in {path}.",
                             {"name": {"value": pattern}, "module": {"value": path}}, digest,
                             f"source://{path}", {"domain": [path.split("/", 1)[0]], "evidence": ["ast"]})
                store.append_node(node)
                store.append_edge(_edge(namespace, str(node["id"]), str(component["id"]), "structural", "part_of", key))
            symbols = [item for item in tree.body if isinstance(item, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))] or [None]
            mechanisms_by_module[module] = []
            for ordinal, symbol in enumerate(symbols):
                name, line = getattr(symbol, "name", "module_init"), getattr(symbol, "lineno", 0)
                key = f"{path}:mechanism:{name}:{line}:{ordinal}"
                node = _node(namespace, "Mechanism", key, f"mechanism:{module}.{name}",
                             f"AST symbol {name} provides an executable mechanism in {path}.",
                             {"symbol": {"value": name}, "kind": {"value": type(symbol).__name__ if symbol else "module"}, "line": {"value": line}}, digest,
                             f"source://{path}#L{line}", {"domain": [path.split("/", 1)[0]], "language": ["python"]})
                store.append_node(node)
                mechanisms_by_module[module].append(str(node["id"]))
                store.append_edge(_edge(namespace, str(node["id"]), str(component["id"]), "structural", "part_of", key))

        module_names = sorted(component_ids)
        for path, tree, _digest in records:
            module = path[:-3].replace("/", ".")
            for imported in sorted(_imports(tree)):
                candidates = [name for name in module_names if name == imported or name.startswith(imported + ".")]
                if candidates and module < candidates[0]:
                    store.append_edge(_edge(namespace, component_ids[module], component_ids[candidates[0]], "dependency", "depends_on", f"{module}:{candidates[0]}"))
            for mechanism_id in mechanisms_by_module[module]:
                store.append_edge(_edge(namespace, component_ids[module], mechanism_id, "dependency", "provides", f"{module}:{mechanism_id}"))

        decisions = sorted((node for node in store.nodes() if node["type"] == "Decision"), key=lambda node: str(node["id"]))
        constraints = sorted((node for node in store.nodes() if node["type"] == "Constraint"), key=lambda node: str(node["id"]))
        for module, component_id in sorted(component_ids.items()):
            if decisions:
                store.append_edge(_edge(namespace, component_id, str(decisions[0]["id"]), "dependency", "calls", f"{module}:decision"))
            if constraints:
                store.append_edge(_edge(namespace, component_id, str(constraints[0]["id"]), "constraint", "constrained_by", f"{module}:constraint"))
        nodes, edges = store.nodes(), store.edges()
        return {"root": str(repository), "namespace": namespace, "source_digest": source_hash,
                "files": len(records), "nodes": len(nodes), "edges": len(edges),
                "indexed_types": {kind: sum(node["type"] == kind for node in nodes) for kind in ("Component", "Pattern", "Mechanism", "TaxonomyNode")}}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--db", type=Path, default=Path("sakg.db"))
    parser.add_argument("--namespace", default=NAMESPACE)
    args = parser.parse_args(argv)
    print(json.dumps(index_repository(args.root, args.db, args.namespace), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
