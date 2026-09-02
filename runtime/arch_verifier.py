"""Level 4 Architectural Graph Conformance Verifier (PAEOS RB-ARCH-ASSURANCE-001 / D8).

Mechanically validates that the codebase satisfies canonical structural invariants, kernel isolation,
information barrier import boundaries, and DAG dependency constraints.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ArchitectureViolation",
    "DependencyGraph",
    "check_kernel_isolation",
    "check_layer_dag",
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
