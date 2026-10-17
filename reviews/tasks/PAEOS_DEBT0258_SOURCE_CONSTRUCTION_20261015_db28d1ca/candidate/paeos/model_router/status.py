"""
PAEOS Model Router — Real-Time Inference Mesh & Quota Dashboard CLI
Usage: uv run python -m paeos.model_router.status
"""
from __future__ import annotations

import sys

from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.observability import ObservabilityDiagnostics
from paeos.model_router.state import RouterStateDB


def main() -> None:
    state_db = RouterStateDB()
    catalog = ModelCatalog()
    credentials = CredentialStore()
    diagnostics = ObservabilityDiagnostics(state_db=state_db, catalog=catalog, credentials=credentials)

    if "--json" in sys.argv:
        import json
        print(json.dumps(diagnostics.get_mesh_status(), indent=2))
    elif "--markdown" in sys.argv:
        print(diagnostics.format_markdown_table())
    else:
        print(diagnostics.format_terminal_dashboard())


if __name__ == "__main__":
    main()
