import argparse
import sys
from pathlib import Path

# Add repo root to sys.path so runtime imports work
repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.types import Role
from runtime.orchestrator import FileCourtEvidencePool

_ENV_HASH = content_hash(b"paeos-mcp-court-env")


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit evidence to the PAEOS Verification Court")
    parser.add_argument("--run-id", required=True, help="Run ID")
    parser.add_argument("--claim-id", required=True, help="Claim ID (e.g. builds, unit)")
    parser.add_argument("--command", required=True, help="Reproducible command")
    # CRITICAL-002: no fabrication defaults. Previously --artifact-hash defaulted to 64
    # zeros, --exit-code to 0, and --stdout to "100% passed" — evidence submitted without
    # these args claimed a passing run that never happened. All three are now required.
    parser.add_argument(
        "--artifact-hash",
        required=True,
        help="Hash of the artifact this evidence binds to (compute with kernel.cas.content_hash)",
    )
    parser.add_argument(
        "--exit-code", required=True, type=int, help="The REAL exit code of the command run"
    )
    parser.add_argument(
        "--stdout", required=True, help="The REAL stdout snippet of the command run"
    )
    parser.add_argument("--pool-dir", default=".paeos_state/court", help="Court evidence pool directory")

    args = parser.parse_args()

    pool_path = Path(args.pool_dir)
    if not pool_path.is_absolute():
        import os

        env_state = os.environ.get("PAEOS_STATE_DIR")
        if env_state:
            pool_dir = (Path(env_state) / "court").resolve()
        else:
            curr = Path.cwd().resolve()
            found = None
            for p in [curr] + list(curr.parents):
                if (p / ".paeos_state" / "court").is_dir():
                    found = p / ".paeos_state" / "court"
                    break
            pool_dir = found.resolve() if found else (repo_root / args.pool_dir).resolve()
    else:
        pool_dir = pool_path
    pool = FileCourtEvidencePool(pool_dir)

    ev_bytes = f"{args.claim_id}:{args.command}".encode("utf-8")
    ev_hash = content_hash(ev_bytes)

    evidence = Evidence(
        hash=ev_hash,
        kind=EvidenceKind.TEST,
        claim_id=args.claim_id,
        artifact_hash=args.artifact_hash,
        environment_hash=_ENV_HASH,
        reproducible_command=args.command,
        producer=EvidenceProducer(role=Role.BUILDER, session="cli"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": args.exit_code, "stdout": args.stdout},
        attestation="pending-kernel-sig",
    )

    pool.submit(args.run_id, evidence)
    print(f"Successfully submitted evidence {ev_hash[:12]} for claim '{args.claim_id}' (run_id: {args.run_id})")


if __name__ == "__main__":
    main()
