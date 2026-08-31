"""One-shot CLI boundary for the state-root-bound Cline worker transport."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from paeos.model_router.types import ModelFamily
from runtime.integrations.bound_cline_transport import (
    BoundWorkerConfig,
    WorkerDispatchSuccess,
    dispatch_once,
)


def _absolute(value: str, label: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise argparse.ArgumentTypeError(f"{label} must be absolute")
    return path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bound-cline-worker", exit_on_error=False)
    parser.add_argument(
        "--state-root", type=lambda value: _absolute(value, "state-root"), required=True
    )
    parser.add_argument(
        "--request-path", type=lambda value: _absolute(value, "request-path"), required=True
    )
    parser.add_argument(
        "--prompt-path", type=lambda value: _absolute(value, "prompt-path"), required=True
    )
    parser.add_argument(
        "--recovery-worktree",
        type=lambda value: _absolute(value, "recovery-worktree"),
        required=True,
    )
    parser.add_argument("--branch-name", required=True)
    parser.add_argument("--candidate-head", required=True)
    parser.add_argument(
        "--node-executable", type=lambda value: _absolute(value, "node-executable"), required=True
    )
    parser.add_argument(
        "--host-module", type=lambda value: _absolute(value, "host-module"), required=True
    )
    parser.add_argument(
        "--sdk-entrypoint", type=lambda value: _absolute(value, "sdk-entrypoint"), required=True
    )
    parser.add_argument(
        "--core-entrypoint", type=lambda value: _absolute(value, "core-entrypoint"), required=True
    )
    parser.add_argument(
        "--qualification-record",
        type=lambda value: _absolute(value, "qualification-record"),
        required=True,
    )
    parser.add_argument(
        "--policy-path", type=lambda value: _absolute(value, "policy-path"), required=True
    )
    parser.add_argument("--policy-sha256", required=True)
    parser.add_argument("--provider-id", required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument(
        "--model-family",
        choices=[family.value for family in ModelFamily if family is not ModelFamily.UNKNOWN],
        required=True,
    )
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--max-model-turns", type=int, default=2)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        config = BoundWorkerConfig(
            state_root=args.state_root,
            recovery_worktree=args.recovery_worktree,
            branch_name=args.branch_name,
            candidate_head=args.candidate_head,
            node_executable=args.node_executable,
            host_module=args.host_module,
            sdk_entrypoint=args.sdk_entrypoint,
            core_entrypoint=args.core_entrypoint,
            qualification_record=args.qualification_record,
            policy_path=args.policy_path,
            policy_sha256=args.policy_sha256,
            provider_id=args.provider_id,
            model_id=args.model_id,
            model_family=ModelFamily(args.model_family),
            session_id=args.session_id,
            timeout_seconds=args.timeout_seconds,
            max_declared_model_turns=args.max_model_turns,
        )
        result = dispatch_once(args.request_path, args.prompt_path, config)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) and exc.code != 0 else 2
    except (argparse.ArgumentError, ValueError, OSError) as exc:
        print(
            json.dumps({"status": "REJECTED", "reason": str(exc)}, sort_keys=True), file=sys.stderr
        )
        return 2
    if isinstance(result, WorkerDispatchSuccess):
        print(
            json.dumps(
                {
                    "status": "COMPLETE",
                    "request_id": result.request_id,
                    "transaction_key": result.transaction_key,
                    "stdout_hash": result.stdout_hash,
                    "stderr_hash": result.stderr_hash,
                    "exit_code": result.exit_code,
                },
                sort_keys=True,
            )
        )
        return 0
    print(
        json.dumps(
            {
                "status": "REJECTED",
                "request_id": result.request_id,
                "transaction_key": result.transaction_key,
                "failure_kind": result.failure.kind.value,
                "stdout_hash": result.failure.stdout_hash,
                "stderr_hash": result.failure.stderr_hash,
            },
            sort_keys=True,
        ),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
