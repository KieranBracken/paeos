"""Machine-readable, lossless SAKG bundle round-trip reporting."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "RoundTripError",
    "RoundTripReport",
    "canonical_roundtrip",
    "discover_bundle_paths",
    "roundtrip_bundle",
    "roundtrip_paths",
]


class RoundTripError(ValueError):
    """A bundle cannot be decoded or does not have the required shape."""


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise RoundTripError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _decode(raw: bytes) -> object:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RoundTripError("bundle is not valid UTF-8 JSON") from exc


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RoundTripError("bundle is not canonical JSON") from exc


def canonical_roundtrip(value: object) -> tuple[object, bytes, bytes]:
    """Decode and canonicalize once, then decode/canonicalize again."""
    first_bytes = _canonical(value)
    first_value = _decode(first_bytes)
    second_bytes = _canonical(first_value)
    second_value = _decode(second_bytes)
    return second_value, first_bytes, second_bytes


def _flatten(value: object, prefix: str = "$") -> Iterator[tuple[str, object]]:
    if isinstance(value, Mapping):
        if not value:
            yield prefix, value
        for key in sorted(value):
            yield from _flatten(value[key], f"{prefix}.{key}")
    elif isinstance(value, list):
        if not value:
            yield prefix, value
        for index, item in enumerate(value):
            yield from _flatten(item, f"{prefix}[{index}]")
    else:
        yield prefix, value


def _shape(value: object) -> None:
    if not isinstance(value, Mapping):
        raise RoundTripError("bundle root must be an object")
    nodes = value.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise RoundTripError("bundle must contain a non-empty nodes array")


@dataclass(frozen=True, slots=True)
class BundleRoundTrip:
    source: str
    input_sha256: str
    canonical_sha256: str
    fields_evaluated: int
    fields_lost: int

    @property
    def loss_ratio(self) -> float:
        return self.fields_lost / self.fields_evaluated if self.fields_evaluated else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "source": self.source,
            "input_sha256": self.input_sha256,
            "canonical_sha256": self.canonical_sha256,
            "fields_evaluated": self.fields_evaluated,
            "fields_lost": self.fields_lost,
            "loss_ratio": self.loss_ratio,
            "lossless": self.fields_lost == 0,
        }


@dataclass(frozen=True, slots=True)
class RoundTripReport:
    bundles: tuple[BundleRoundTrip, ...]

    @property
    def fields_evaluated(self) -> int:
        return sum(item.fields_evaluated for item in self.bundles)

    @property
    def fields_lost(self) -> int:
        return sum(item.fields_lost for item in self.bundles)

    @property
    def loss_ratio(self) -> float:
        return self.fields_lost / self.fields_evaluated if self.fields_evaluated else 0.0

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "paeos.sakg.roundtrip-report/v1",
            "bundles_evaluated": len(self.bundles),
            "fields_evaluated": self.fields_evaluated,
            "fields_lost": self.fields_lost,
            "loss_ratio": self.loss_ratio,
            "lossless": self.fields_lost == 0,
            "cases": [item.to_dict() for item in self.bundles],
        }


def roundtrip_bundle(raw: bytes, *, source: str = "<memory>") -> BundleRoundTrip:
    value = _decode(raw)
    _shape(value)
    roundtripped, _first_bytes, second_bytes = canonical_roundtrip(value)
    before = dict(_flatten(value))
    after = dict(_flatten(roundtripped))
    lost = sum(1 for path, item in before.items() if after.get(path, object()) != item)
    return BundleRoundTrip(
        source=source,
        input_sha256=hashlib.sha256(raw).hexdigest(),
        canonical_sha256=hashlib.sha256(second_bytes).hexdigest(),
        fields_evaluated=max(1, len(before)),
        fields_lost=lost,
    )


def discover_bundle_paths(root: Path | None = None) -> tuple[Path, ...]:
    base = root or Path(__file__).resolve().parents[1]
    patterns = (
        "tests/sakg/fixtures/bundle/valid/*.json",
        "tests/sakg/fixtures/extract/*/expected_bundle.json",
    )
    paths = {path for pattern in patterns for path in base.glob(pattern)}
    return tuple(sorted(paths))


def roundtrip_paths(paths: Sequence[Path]) -> RoundTripReport:
    if not paths:
        raise RoundTripError("no sealed bundle fixtures were found")
    return RoundTripReport(
        tuple(
            roundtrip_bundle(path.read_bytes(), source=str(path.relative_to(path.parents[3])))
            for path in paths
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m sakg.report")
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("roundtrip", help="report lossless bundle round-trips")
    command.add_argument("--fixture-root", type=Path)
    command.add_argument("--assert-loss-ratio", type=float)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "roundtrip":
        return 2
    try:
        paths = discover_bundle_paths(args.fixture_root)
        report = roundtrip_paths(paths)
    except (OSError, RoundTripError) as exc:
        print(json.dumps({"error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2
    print(json.dumps(report.to_dict(), sort_keys=True, separators=(",", ":")))
    if args.assert_loss_ratio is not None and report.loss_ratio > args.assert_loss_ratio:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
