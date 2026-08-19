# PAEOS Task: g-test (r-5678)
**Stage:** ADVERSARIAL_REVIEW | **Role:** ADVERSARY

## Objective
Test objective

## Strict Workspace Binding
You MUST execute all work inside the isolated sandboxed workspace at:
`/private/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/pytest-of-bob/pytest-378/test_bridge_adversarial_review0/paeos-t-1234-bridge-v380a49p`

Use the `run_command` tool with `Cwd` set to `/private/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/pytest-of-bob/pytest-378/test_bridge_adversarial_review0/paeos-t-1234-bridge-v380a49p`. DO NOT modify any repository files outside of this workspace sandbox! The sandbox contains a seeded mirror of the code you need.

## The Package Prompt
```
Test objective
```

## Instructions for Orchestrator
1. Spawn a subagent or perform the task yourself inside `/private/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/pytest-of-bob/pytest-378/test_bridge_adversarial_review0/paeos-t-1234-bridge-v380a49p`.
2. The subagent can read context files provided inside the workspace, and edit the code using `write_scopes` authorized inside the workspace.
 3. If this is a BUILDER role, the subagent MUST submit evidence to the PAEOS Court with
   **REAL, KERNEL-REPRODUCIBLE values** (CRITICAL-002: placeholder evidence is forbidden —
   the kernel re-runs the command and rejects fabricated results). Substitute the two
   REQUIRED placeholders, then write and run this python script inside the sandbox:
   ```python
   import shlex
   import subprocess
   import sys
   sys.path.insert(0, "/Users/bob/GitHub/paeos")
   from pathlib import Path
   from kernel.cas import content_hash
   from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
   from kernel.types import Role
   from runtime.orchestrator import FileCourtEvidencePool

   # REQUIRED (CRITICAL-002): real values, never placeholders.
   artifact_path = Path("REPLACE_WITH_THE_ARTIFACT_YOU_ACTUALLY_BUILT")  # relative to this sandbox
   command = "REPLACE_WITH_THE_REAL_VERIFICATION_COMMAND"  # e.g. "pytest"

   proc = subprocess.run(shlex.split(command), capture_output=True, text=True, timeout=600)
   pool = FileCourtEvidencePool(Path("/Users/bob/GitHub/paeos/.paeos_state/court"))
   pool.submit(
       "r-5678",
       Evidence(
           hash=content_hash(f"{command}:{proc.returncode}".encode()),
           kind=EvidenceKind.TEST,
           claim_id="builds",
           artifact_hash=content_hash(artifact_path.read_bytes()),
           environment_hash=content_hash(sys.executable.encode()),
           reproducible_command=command,
           producer=EvidenceProducer(role=Role.BUILDER, session="mcp"),
           determinism=Determinism.DETERMINISTIC,
           result={"exit_code": proc.returncode, "stdout": proc.stdout},
           attestation="pending-kernel-sig",
       ),
   )
   ```
4. Once completed, write your full response/transcript to `/Users/bob/GitHub/paeos/.paeos_state/bridge/current_output.md`.
