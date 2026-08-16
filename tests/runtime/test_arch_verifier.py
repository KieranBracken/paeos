"""Level 4 Architectural Graph Conformance Tests.

Verifies that runtime/arch_verifier.py accurately enforces Kernel Isolation and Layer DAG Invariants.
"""

from __future__ import annotations

from pathlib import Path

from runtime.arch_verifier import (
    check_kernel_isolation,
    extract_imports,
    verify_architectural_conformance,
)


def test_kernel_isolation_has_zero_runtime_imports() -> None:
    """Rule 1: Verify kernel/ contains zero imports of upper runtime or ops layers in production repo."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    violations = check_kernel_isolation(repo_root)
    assert violations == [], f"Kernel isolation violated by imports: {violations}"


def test_arch_verifier_detects_kernel_importing_runtime(tmp_path: Path) -> None:
    """Rule 1 (Negative Test): Verify synthetic kernel module importing runtime is caught and blocked."""
    repo = tmp_path / "repo"
    kernel_dir = repo / "kernel"
    kernel_dir.mkdir(parents=True)
    (kernel_dir / "bad_module.py").write_text("import runtime\nimport ops\n")

    violations = check_kernel_isolation(repo)
    assert len(violations) >= 1
    assert violations[0].rule_id == "ARCH-INVARIANT-01"
    assert "bad_module.py" in violations[0].source_path


def test_extract_imports_parses_ast() -> None:
    """Test AST import parser extracts imports cleanly."""
    source = "import os\nfrom runtime.orchestrator import SoftLoop\nimport kernel.cas\n"
    imports = extract_imports(source, "dummy.py")
    assert "os" in imports
    assert "runtime" in imports
    assert "kernel" in imports
