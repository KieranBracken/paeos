# PAEOS Task: g-1d5580def4bd (r-0c3b9c9f)
**Stage:** RESEARCH | **Role:** PLANNER

## Objective
Conduct frontier research on the ideated candidates. Analyze the codebase, dependencies, and relevant documentation to evaluate feasibility, architectural fit, and constraints. Produce a structured ResearchDossier (saved to the research/ directory) synthesizing the findings to inform the DESIGN stage. Goal objective: Instantiate L19 (Constitutional Evolution). Hook this into the proposal generation of L18 (Knowledge Extraction).

## Strict Workspace Binding
You MUST execute all work inside the isolated sandboxed workspace at:
`/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/paeos-t-84f88a636157-bridge-plm6zrnj`

Use the `run_command` tool with `Cwd` set to `/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/paeos-t-84f88a636157-bridge-plm6zrnj`. DO NOT modify any repository files outside of this workspace sandbox! The sandbox contains a seeded mirror of the code you need.

## The Package Prompt
```
Conduct frontier research on the ideated candidates. Analyze the codebase, dependencies, and relevant documentation to evaluate feasibility, architectural fit, and constraints. Produce a structured ResearchDossier (saved to the research/ directory) synthesizing the findings to inform the DESIGN stage. Goal objective: Instantiate L19 (Constitutional Evolution). Hook this into the proposal generation of L18 (Knowledge Extraction).
```

## Instructions for Orchestrator
1. Spawn a subagent or perform the task yourself inside `/var/folders/b0/hb9_mxhn4nz09tzctglbjq6w0000gp/T/paeos-t-84f88a636157-bridge-plm6zrnj`.
2. The subagent can read context files provided inside the workspace, and edit the code using `write_scopes` authorized inside the workspace.
3. If this is a BUILDER role, the subagent MUST submit evidence to the PAEOS Court. The simplest way is to write and run this python script inside the sandbox:
   ```python
   import sys
   sys.path.insert(0, "/Users/bob/GitHub/paeos")
   from pathlib import Path
   from kernel.cas import content_hash
   from kernel.evidence import Determinism, Evidence, EvidenceKind, EvidenceProducer
   from kernel.types import Role
   from runtime.orchestrator import FileCourtEvidencePool

   pool = FileCourtEvidencePool(Path("/Users/bob/GitHub/paeos/.paeos_state/court"))
   pool.submit(
       "r-0c3b9c9f",
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
       )
   )
   ```
4. Once completed, write your full response/transcript to `/Users/bob/GitHub/paeos/.paeos_state/bridge/current_output.md`.
