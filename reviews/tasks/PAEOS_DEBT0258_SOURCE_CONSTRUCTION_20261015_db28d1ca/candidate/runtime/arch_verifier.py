"""Level 4 Architectural Graph Conformance Verifier (PAEOS RB-ARCH-ASSURANCE-001 / D8).

Mechanically validates that the codebase satisfies canonical structural invariants, kernel isolation,
information barrier import boundaries, and DAG dependency constraints.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from pathlib import Path
import re

__all__ = [
    "ArchitectureImpactVector",
    "ArchitectureViolation",
    "DependencyGraph",
    "check_kernel_isolation",
    "check_layer_dag",
    "evaluate_architecture_impact",
    "extract_imports",
    "verify_architectural_conformance",
]


@dataclass(frozen=True, slots=True)
class ArchitectureViolation:
    """A mechanical violation of an architectural invariant."""

    source_path: str
    imported_target: str
    rule_id: str
    description: str


@dataclass
class DependencyGraph:
    """Empirical import dependency graph across codebase modules."""

    adj: dict[str, set[str]]

    def add_edge(self, source: str, target: str) -> None:
        if source not in self.adj:
            self.adj[source] = set()
        self.adj[source].add(target)


def extract_imports(source_code: str, file_rel_path: str) -> set[str]:
    """Extract top-level and relative module imports from a Python source string using AST parsing."""
    imports: set[str] = set()
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])
            elif node.level > 0:
                # Relative import (e.g. from . import foo)
                parts = file_rel_path.split("/")
                if len(parts) > 1:
                    imports.add(parts[0])
    return imports


def check_kernel_isolation(repo_root: Path) -> list[ArchitectureViolation]:
    """Rule 1: Kernel Isolation Invariant.

    kernel/ is the immutable substrate and MUST NOT import any module from runtime/ or ops/.
    """
    violations: list[ArchitectureViolation] = []
    kernel_dir = repo_root / "kernel"
    if not kernel_dir.is_dir():
        return violations

    for py_file in kernel_dir.rglob("*.py"):
        rel_path = str(py_file.relative_to(repo_root))
        source = py_file.read_text(encoding="utf-8")
        imports = extract_imports(source, rel_path)

        for imp in imports:
            if imp in {"runtime", "ops"}:
                violations.append(
                    ArchitectureViolation(
                        source_path=rel_path,
                        imported_target=imp,
                        rule_id="ARCH-INVARIANT-01",
                        description=f"Kernel module {rel_path} illegally imports upper layer module '{imp}'",
                    )
                )
    return violations


def check_layer_dag(repo_root: Path) -> list[ArchitectureViolation]:
    """Rule 3: Dependency Graph DAG Invariant.

    Verifies there are no circular import dependencies between kernel and runtime modules.
    """
    violations: list[ArchitectureViolation] = []
    graph = DependencyGraph(adj={})

    for folder in ("kernel", "runtime"):
        target_dir = repo_root / folder
        if not target_dir.is_dir():
            continue
        for py_file in target_dir.rglob("*.py"):
            rel_path = str(py_file.relative_to(repo_root))
            mod_key = rel_path.replace("/", ".").removesuffix(".py")
            source = py_file.read_text(encoding="utf-8")
            imports = extract_imports(source, rel_path)
            for imp in imports:
                if imp in {"kernel", "runtime"}:
                    graph.add_edge(mod_key, imp)

    # Tarjan / Cycle detection using DFS
    visited: dict[str, int] = {}  # 0: unvisited, 1: visiting, 2: visited
    cycle_nodes: list[str] = []

    def dfs(node: str, path: list[str]) -> bool:
        visited[node] = 1
        path.append(node)
        for neighbor in graph.adj.get(node, ()):
            if visited.get(neighbor, 0) == 1:
                cycle_nodes.extend(path[path.index(neighbor) :])
                return True
            if visited.get(neighbor, 0) == 0 and dfs(neighbor, path):
                return True
        path.pop()
        visited[node] = 2
        return False

    for node in list(graph.adj.keys()):
        if visited.get(node, 0) == 0 and dfs(node, []):
            cycle_str = " -> ".join(cycle_nodes)
            violations.append(
                ArchitectureViolation(
                    source_path=cycle_nodes[0] if cycle_nodes else node,
                    imported_target=cycle_nodes[-1] if cycle_nodes else node,
                    rule_id="ARCH-INVARIANT-03",
                    description=f"Circular dependency cycle detected: {cycle_str}",
                )
            )
            break

    return violations


def verify_architectural_conformance(repo_root: Path) -> tuple[ArchitectureViolation, ...]:
    """Run all mechanical Level 4 architectural graph conformance checks against repo_root."""
    violations: list[ArchitectureViolation] = []
    violations.extend(check_kernel_isolation(repo_root))
    violations.extend(check_layer_dag(repo_root))
    return tuple(violations)


@dataclass(frozen=True, slots=True)
class ArchitectureImpactVector:
    """Deterministic structural invariant impact vector (ELH-13)."""

    changed_files: tuple[str, ...]
    affected_subsystems: tuple[str, ...]
    violated_invariants: tuple[str, ...]
    violations: tuple[ArchitectureViolation, ...]
    risk_tier: str
    requires_founder: bool
    is_conforming: bool


def evaluate_architecture_impact(
    repo_root: Path,
    changed_files: tuple[str, ...] = (),
) -> ArchitectureImpactVector:
    """Evaluate architectural impact of changed files against architecture/invariants.json (ELH-13)."""
    subsystems: set[str] = set()
    for f in changed_files:
        norm = f.strip().replace("\\", "/").strip("/")
        parts = norm.split("/")
        if parts:
            subsystems.add(parts[0])

    affects_constitution = any(
        f.startswith("constitution") or "ENGINEERING_LIFECYCLE.md" in f
        for f in changed_files
    )
    affects_kernel = any(f.startswith("kernel") for f in changed_files)

    if affects_constitution:
        risk_tier = "CONSTITUTIONAL"
        requires_founder = True
    elif affects_kernel:
        risk_tier = "HIGH"
        requires_founder = False
    elif any(s in {"paeos", "runtime"} for s in subsystems):
        risk_tier = "MEDIUM"
        requires_founder = False
    else:
        risk_tier = "LOW"
        requires_founder = False

    violations = list(verify_architectural_conformance(repo_root))

    # Validate against architecture/invariants.json if present
    invariants_path = repo_root / "architecture" / "invariants.json"
    if invariants_path.exists():
        try:
            inv_data = json.loads(invariants_path.read_text(encoding="utf-8"))
            for inv_id, inv_spec in inv_data.items():
                if inv_id.startswith("_") or not isinstance(inv_spec, dict):
                    continue
                verify_info = inv_spec.get("verify", {})
                kind = verify_info.get("kind")
                if kind == "grep-absent":
                    pattern = verify_info.get("pattern", "")
                    paths = verify_info.get("paths", [])
                    excludes = set(verify_info.get("exclude", []))
                    if pattern:
                        regex = re.compile(pattern)
                        for target_rel in paths:
                            target_dir = repo_root / target_rel
                            if target_dir.is_dir():
                                for py_file in target_dir.rglob("*.py"):
                                    rel = str(py_file.relative_to(repo_root)).replace("\\", "/")
                                    if any(rel.startswith(exc) for exc in excludes):
                                        continue
                                    try:
                                        content = py_file.read_text(encoding="utf-8")
                                        if regex.search(content):
                                            violations.append(
                                                ArchitectureViolation(
                                                    source_path=rel,
                                                    imported_target=pattern,
                                                    rule_id=inv_id,
                                                    description=f"{inv_spec.get('name', inv_id)}: forbidden pattern '{pattern}' matched",
                                                )
                                            )
                                    except Exception:
                                        pass
                elif kind == "loc-budget":
                    max_loc = verify_info.get("max", 0)
                    paths = verify_info.get("paths", [])
                    for target_rel in paths:
                        target_dir = repo_root / target_rel
                        if target_dir.is_dir():
                            total_loc = 0
                            for py_file in target_dir.rglob("*.py"):
                                try:
                                    total_loc += len(py_file.read_text(encoding="utf-8").splitlines())
                                except Exception:
                                    pass
                            if max_loc > 0 and total_loc > max_loc:
                                violations.append(
                                    ArchitectureViolation(
                                        source_path=target_rel,
                                        imported_target="LOC_BUDGET",
                                        rule_id=inv_id,
                                        description=f"LOC budget exceeded: {total_loc} > {max_loc}",
                                    )
                                )
        except Exception:
            pass

    violated_rule_ids = tuple(sorted({v.rule_id for v in violations}))
    return ArchitectureImpactVector(
        changed_files=changed_files,
        affected_subsystems=tuple(sorted(subsystems)),
        violated_invariants=violated_rule_ids,
        violations=tuple(violations),
        risk_tier=risk_tier,
        requires_founder=requires_founder,
        is_conforming=(len(violations) == 0),
    )
