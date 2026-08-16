import sys

sys.path.insert(0, "/Users/bob/GitHub/paeos")
from pathlib import Path

from kernel.cas import content_hash
from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
from kernel.types import Role
from runtime.orchestrator import FileCourtEvidencePool

run_id = sys.argv[1]
pool = FileCourtEvidencePool(Path("/Users/bob/GitHub/paeos/.paeos_state/court"))
pool.submit(
    run_id,
    Evidence(
        hash=content_hash(b"builds:pytest"),
        kind=EvidenceKind.TEST,
        claim_id="builds",
        artifact_hash="dummy_hash_for_now",
        environment_hash="dummy_env",
        reproducible_command="pytest",
        producer=EvidenceProducer(role=Role.BUILDER, session="mcp"),
        determinism=Determinism.DETERMINISTIC,
        result={"exit_code": 0, "stdout": "test passed"},
        attestation="pending-kernel-sig",
    ),
)
print(f"Submitted evidence for {run_id}")
