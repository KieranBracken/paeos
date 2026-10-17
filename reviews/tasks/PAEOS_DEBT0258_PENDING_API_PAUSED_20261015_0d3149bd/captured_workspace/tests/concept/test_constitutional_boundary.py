from __future__ import annotations

import ast
import importlib
from pathlib import Path


def test_static_import_boundary_and_public_surface() -> None:
    bridge = importlib.import_module("concept.bridge")
    bridge_file = bridge.__file__
    assert bridge_file is not None
    tree = ast.parse(Path(bridge_file).read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = ("runtime.integrations", "sakg.store", "sentium")
    assert not any(name == root or name.startswith(root + ".") for name in imported for root in forbidden)
    assert callable(bridge.build_candidate_envelope)
    assert callable(bridge.emit_candidate)
    assert not any(hasattr(bridge, name) for name in ("execute", "promote", "publish", "broker"))


def test_typed_boundary_errors_are_exposed() -> None:
    bridge = importlib.import_module("concept.bridge")
    assert issubclass(bridge.MissingFalsifierError, bridge.CandidateExportBoundaryError)
    assert issubclass(bridge.TruthBearingStatusForbiddenError, bridge.CandidateExportBoundaryError)
