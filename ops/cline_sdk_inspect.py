"""Read-only CLI for qualifying an installed public Cline SDK surface."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from runtime.integrations.cline_sdk_qualification import (
    QualificationError,
    qualify_cline_sdk,
    write_qualification_record,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cline-package-root", type=Path, required=True)
    parser.add_argument("--node-executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _error(reason: str, gaps: tuple[str, ...] = ()) -> int:
    print(
        json.dumps(
            {"gaps": list(gaps), "reason": reason, "status": "UNQUALIFIED"},
            sort_keys=True,
            separators=(",", ":"),
        ),
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.output.is_absolute():
        return _error("OUTPUT_NOT_ABSOLUTE")
    if args.output.exists():
        return _error("OUTPUT_EXISTS")
    if not args.output.parent.is_dir():
        return _error("OUTPUT_PARENT_MISSING")
    try:
        record = qualify_cline_sdk(args.cline_package_root, args.node_executable)
        write_qualification_record(record, args.output)
    except QualificationError as exc:
        return _error("ADAPTER_VERSION_UNQUALIFIED", tuple(gap.value for gap in exc.gaps))
    except FileExistsError:
        return _error("OUTPUT_EXISTS")
    except OSError:
        return _error("OUTPUT_WRITE_FAILED")
    print(
        json.dumps(
            {
                "record_sha256": record.record_sha256,
                "status": "QUALIFIED_PUBLIC_SURFACE",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
