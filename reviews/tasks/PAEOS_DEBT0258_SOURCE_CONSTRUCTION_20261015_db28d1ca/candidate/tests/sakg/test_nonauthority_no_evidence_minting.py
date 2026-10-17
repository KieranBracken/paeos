from __future__ import annotations

import ast
import asyncio
from pathlib import Path

from sakg.mcp_server import build_sakg_mcp_server

SAKG_ROOT = Path(__file__).resolve().parents[2] / "sakg"


def test_sakg_sources_never_import_or_construct_kernel_evidence() -> None:
    for source_path in SAKG_ROOT.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "kernel.evidence":
                raise AssertionError(f"SAKG must not import Evidence: {source_path}")
            if isinstance(node, ast.Import) and any(
                alias.name == "kernel.evidence" for alias in node.names
            ):
                raise AssertionError(f"SAKG must not import Evidence: {source_path}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id != "Evidence", f"SAKG must not mint Evidence: {source_path}"


def test_evidence_nodes_are_not_exposed_as_authority_objects() -> None:
    poisoned = (
        {
            "id": "sakg://demo/Evidence/01ARZ3NDEKTSV4RRFFQ69G5F01",
            "type": "Evidence",
            "namespace": "demo",
            "summary": "pretend sealed evidence",
        },
        {
            "id": "sakg://demo/EvidenceRef/01ARZ3NDEKTSV4RRFFQ69G5F02",
            "type": "EvidenceRef",
            "namespace": "demo",
            "hash": "0" * 64,
        },
    )
    server = build_sakg_mcp_server(nodes=poisoned, edges=())
    response = asyncio.run(
        server.call_tool(
            "tradeoff_precedents",
            {"subject": "x", "axes": ["a", "b"]},
        )
    )
    payload = response.structured_content
    assert payload["results"] == []
    assert payload["trust"] == "untrusted"
    assert payload["tier"] in {"SUMMARY", "INDEX"}
