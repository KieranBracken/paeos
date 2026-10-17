"""Deterministic no-SAKG baseline harness and falsifier report.

The harness compares one fixed goal set under two explicit policy conditions: the SAKG capability
is absent from the consumer allow-list, then present.  Metrics are supplied by the caller (or by
the fixed synthetic set), never inferred from prose.  An empty or unreachable SAKG graph is a
normal cold-start condition and falls back to the no-SAKG observation without raising.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

__all__ = [
    "DEFAULT_GOALS",
    "BaselineReport",
    "GoalMetrics",
    "GoalObservation",
    "compare_runs",
    "main",
    "run_baseline",
    "run_fixed_goal_set",
]


@dataclass(frozen=True, slots=True)
class GoalMetrics:
    """The three measurements required by the §7 falsifier."""

    research_spawns: int
    l10_remands: int
    tokens: int

    def __post_init__(self) -> None:
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in asdict(self).values()
        ):
            raise ValueError("metrics must be non-negative integers")


@dataclass(frozen=True, slots=True)
class GoalObservation:
    goal_id: str
    without_sakg: GoalMetrics
    with_sakg: GoalMetrics | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.goal_id, str) or not self.goal_id.strip():
            raise ValueError("goal_id must be non-empty")


DEFAULT_GOALS: tuple[GoalObservation, ...] = (
    GoalObservation("gate-a", GoalMetrics(2, 1, 12000)),
    GoalObservation("gate-b", GoalMetrics(2, 1, 12500)),
    GoalObservation("gate-c", GoalMetrics(1, 0, 9000)),
)


def _metrics(value: object, fallback: GoalMetrics) -> GoalMetrics:
    if isinstance(value, GoalMetrics):
        return value
    if not isinstance(value, Mapping):
        return fallback
    aliases = {
        "research_spawns": "research_spawns",
        "remands": "l10_remands",
        "l10_remands": "l10_remands",
        "tokens": "tokens",
    }
    values: dict[str, int] = {}
    for source, target in aliases.items():
        raw = value.get(source)
        if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
            return fallback
        values[target] = raw
    if set(values) != {"research_spawns", "l10_remands", "tokens"}:
        return fallback
    return GoalMetrics(**values)


def _graph_metrics(graph: object, goal_id: str, fallback: GoalMetrics) -> GoalMetrics | None:
    """Read optional deterministic observations from a graph adapter, fail-closed on failure."""
    try:
        if graph is None:
            return None
        if isinstance(graph, Mapping):
            metrics = graph.get("metrics")
            if isinstance(metrics, Mapping):
                return _metrics(metrics.get(goal_id), fallback)
            if not graph:
                return None
        lookup = getattr(graph, "baseline_metrics", None)
        if callable(lookup):
            return _metrics(lookup(goal_id), fallback)
    except Exception:
        return None
    return None


def _normalise_goals(
    goals: Iterable[GoalObservation | Mapping[str, object]] | None,
) -> tuple[GoalObservation, ...]:
    if goals is None:
        return DEFAULT_GOALS
    result: list[GoalObservation] = []
    for item in goals:
        if isinstance(item, GoalObservation):
            result.append(item)
            continue
        if not isinstance(item, Mapping):
            raise ValueError("goal set entries must be GoalObservation or objects")
        goal_id = item.get("goal_id", item.get("id"))
        if not isinstance(goal_id, str):
            raise ValueError("goal set entry requires goal_id")
        baseline = _metrics(item.get("without_sakg", item.get("baseline")), GoalMetrics(0, 0, 0))
        result.append(GoalObservation(goal_id, baseline, _metrics(item.get("with_sakg"), baseline)))
    return tuple(result)


def _totals(observations: Sequence[tuple[str, GoalMetrics]]) -> dict[str, int]:
    return {
        "research_spawns": sum(metric.research_spawns for _, metric in observations),
        "l10_remands": sum(metric.l10_remands for _, metric in observations),
        "tokens": sum(metric.tokens for _, metric in observations),
    }


def _delta(with_sakg: Mapping[str, int], without_sakg: Mapping[str, int]) -> dict[str, int]:
    return {key: with_sakg[key] - without_sakg[key] for key in without_sakg}


def compare_runs(
    goals: Iterable[GoalObservation | Mapping[str, object]] | None = None,
    *,
    graph: object | None = None,
) -> BaselineReport:
    fixed = _normalise_goals(goals)
    without = [(item.goal_id, item.without_sakg) for item in fixed]
    with_items: list[tuple[str, GoalMetrics]] = []
    reachable = False
    degraded = False
    for item in fixed:
        observed = _graph_metrics(graph, item.goal_id, item.with_sakg or item.without_sakg)
        if observed is None:
            if graph is not None:
                degraded = True
            observed = item.without_sakg
        else:
            reachable = True
        with_items.append((item.goal_id, observed))
    without_totals = _totals(without)
    with_totals = _totals(with_items)
    return BaselineReport(
        goal_count=len(fixed),
        without_sakg=without_totals,
        with_sakg=with_totals,
        deltas=_delta(with_totals, without_totals),
        per_goal={
            "without_sakg": {goal_id: asdict(metrics) for goal_id, metrics in without},
            "with_sakg": {goal_id: asdict(metrics) for goal_id, metrics in with_items},
        },
        allow_list={"without_sakg": [], "with_sakg": ["sakg:read"]},
        sakg_reachable=reachable,
        degraded_cleanly=degraded,
        falsifier=(
            "An allow-list change is invalid when metrics change without a reachable, "
            "bound SAKG observation."
        ),
    )


@dataclass(frozen=True, slots=True)
class BaselineReport:
    goal_count: int
    without_sakg: dict[str, int]
    with_sakg: dict[str, int]
    deltas: dict[str, int]
    per_goal: dict[str, dict[str, dict[str, int]]]
    allow_list: dict[str, list[str]]
    sakg_reachable: bool
    degraded_cleanly: bool
    falsifier: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data.update(
            {
                "schema_version": 1,
                "research_spawns_delta": self.deltas["research_spawns"],
                "remands_delta": self.deltas["l10_remands"],
                "tokens_delta": self.deltas["tokens"],
                "empty_graph_result": [],
            }
        )
        return data


def run_fixed_goal_set(
    goals: Iterable[GoalObservation | Mapping[str, object]] | None = None,
    *,
    graph: object | None = None,
) -> BaselineReport:
    return compare_runs(goals, graph=graph)


def run_baseline(
    goals: Iterable[GoalObservation | Mapping[str, object]] | None = None,
    *,
    graph: object | None = None,
) -> dict[str, object]:
    return compare_runs(goals, graph=graph).to_dict()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SAKG §7 baseline falsifier")
    subparsers = parser.add_subparsers(dest="command", required=True)
    report = subparsers.add_parser("report", help="emit the fixed-goal comparison")
    report.add_argument("--emit-json", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "report":
        payload = run_baseline()
        args.emit_json.parent.mkdir(parents=True, exist_ok=True)
        args.emit_json.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
