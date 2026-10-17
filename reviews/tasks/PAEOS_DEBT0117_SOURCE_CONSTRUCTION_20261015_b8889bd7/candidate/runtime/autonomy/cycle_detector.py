"""Deterministic topological cycle detection via Kahn's algorithm with node tie-breaking."""

from __future__ import annotations

from collections import defaultdict, deque


class CycleDetectedError(ValueError):
    """Cycle detected in dependency graph."""


def topological_sort(nodes: set[str], edges: list[tuple[str, str]]) -> list[str]:
    """Perform deterministic topological sort of nodes.

    Edges are (source, target) indicating dependency / precedence:
    source must precede target.
    Returns ordered node IDs or raises CycleDetectedError.
    """
    in_degree: dict[str, int] = {node: 0 for node in nodes}
    adj: dict[str, list[str]] = defaultdict(list)

    for src, dst in edges:
        if src in in_degree and dst in in_degree:
            adj[src].append(dst)
            in_degree[dst] += 1

    # Deterministic priority queue / sorted order for zero in-degree
    zero_in = sorted([n for n, d in in_degree.items() if d == 0])
    queue = deque(zero_in)
    order = []

    while queue:
        # Re-sort zero_in candidates if multiple to guarantee determinism
        curr = queue.popleft()
        order.append(curr)
        next_candidates = []
        for neighbor in sorted(adj[curr]):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                next_candidates.append(neighbor)
        
        # Insert in sorted order to maintain determinism
        for cand in sorted(next_candidates):
            queue.append(cand)

    if len(order) != len(nodes):
        unresolved = sorted([n for n, d in in_degree.items() if d > 0])
        raise CycleDetectedError(f"Cycle detected in graph among nodes: {unresolved}")

    return order


def would_cause_cycle(
    nodes: set[str],
    existing_edges: list[tuple[str, str]],
    proposed_edge: tuple[str, str],
) -> bool:
    """Check if adding proposed_edge (src, dst) would introduce a cycle."""
    all_nodes = set(nodes) | {proposed_edge[0], proposed_edge[1]}
    all_edges = list(existing_edges) + [proposed_edge]
    try:
        topological_sort(all_nodes, all_edges)
        return False
    except CycleDetectedError:
        return True


class CycleDetector:
    """Detects recurring/oscillating states and bounds execution in autonomous task execution."""

    def __init__(self, max_window: int = 6, max_iterations: int = 50) -> None:
        self.history: list[str] = []
        self.max_window = max_window
        self.max_iterations = max_iterations
        self.total_recorded: int = 0

    def record_state(self, state: str) -> None:
        self.total_recorded += 1
        self.history.append(state)
        if len(self.history) > self.max_window * 2:
            self.history = self.history[-self.max_window * 2 :]

    def is_cycling(self) -> bool:
        # 1. Hard bound on total execution steps (ELH-11)
        if self.total_recorded >= self.max_iterations:
            return True
        if len(self.history) < 4:
            return False
        # 2. Detect A -> B -> A -> B 2-cycles
        if (
            self.history[-4] == self.history[-2]
            and self.history[-3] == self.history[-1]
            and self.history[-4] != self.history[-3]
        ):
            return True
        # 3. Detect A -> B -> C -> A -> B -> C 3-cycles
        if len(self.history) >= 6:
            if (
                self.history[-6] == self.history[-3]
                and self.history[-5] == self.history[-2]
                and self.history[-4] == self.history[-1]
            ):
                return True
        return False
