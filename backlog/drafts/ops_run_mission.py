"""Execute the PAEOS Multi-Branch Canonical Execution Model Mission Natively."""

import json
from pathlib import Path

from kernel.cas import CAS, FilesystemCasStore
from kernel.keystore import load_or_create_signing_key
from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from runtime.integrations import ClaudeCodeRuntime
from runtime.investigation import InvestigationLoop


def main():
    print("Setting up PAEOS state...")
    state_dir = Path(".paeos_state_investigation")
    state_dir.mkdir(exist_ok=True)
    db_path = str(state_dir / "ledger.db")
    keys_path = str(state_dir / "keys.json")

    ledger = Ledger(SqliteLedgerStore(db_path))
    signing_key = load_or_create_signing_key(keys_path)
    cas_store = FilesystemCasStore(state_dir / "cas")
    cas = CAS(cas_store)

    print("Initializing ClaudeCodeRuntime (LIVE PAEOS agent runtime)...")
    runtime = ClaudeCodeRuntime(workspace_source=Path.cwd(), artifact_resolver=cas.get)

    loop = InvestigationLoop(ledger=ledger, signing_key=signing_key, cas=cas, agent_runtime=runtime)

    mission = """
PAEOS Canonical Execution Model Investigation
Your task is to analyze candidate architectures for the foundational execution model of PAEOS.
Candidate A: Goal-centric / Hierarchical execution.
Candidate B: Event-driven / Blackboard execution.

Determine which model best fits PAEOS's requirements for append-only determinism and strict isolation.
"""

    print("Dispatching Native Investigation Mission...")
    result = loop.run_investigation(mission=mission, budget_tokens=2_000_000)
    print("\nMission Completed Successfully.")
    print("Results:")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
