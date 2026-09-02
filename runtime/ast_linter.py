"""AST Static Anti-Pattern Linter (PAEOS RB-0015 / RB-ARCH-VERIFY-004).

Scans Abstract Syntax Trees of Python source code to detect swallowed exceptions, bare excepts,
and un-logged fallback returns before Court verification runs.
"""

from __future__ import annotations

import ast
from pathlib import Path

__all__ = ["PaeosAstLinter", "check_ast"]


class PaeosAstLinter(ast.NodeVisitor):
    """AST visitor that detects exception-swallowing anti-patterns."""

    def __init__(self) -> None:
        self.violations: list[str] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        # Rule 1: Bare except (except:)
        if node.type is None:
            self.violations.append(
                f"Line {node.lineno}: Bare 'except:' is strictly forbidden (PAEOS-AST-01)."
            )

        # Rule 2: Swallowed exception (body contains only 'pass')
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            self.violations.append(
                f"Line {node.lineno}: Silent 'except Exception: pass' is forbidden (PAEOS-AST-02)."
            )

        # Rule 3: Un-logged return None fallback without raise/logging
        if (
            len(node.body) == 1
            and isinstance(node.body[0], ast.Return)
            and (
                node.body[0].value is None
                or (
                    isinstance(node.body[0].value, ast.Constant)
                    and node.body[0].value.value is None
                )
            )
        ):
            self.violations.append(
                f"Line {node.lineno}: Un-logged 'except Exception: return None' is forbidden (PAEOS-AST-03)."
            )

        self.generic_visit(node)


def check_ast(source_or_path: str | Path) -> list[str]:
    """Check Python source string or file path for AST anti-patterns."""
    if isinstance(source_or_path, Path):
        try:
            source = source_or_path.read_text(encoding="utf-8")
        except OSError as e:
            return [f"Could not read file {source_or_path}: {e}"]
    else:
        source = str(source_or_path)

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"SyntaxError parsing AST: {e}"]

    linter = PaeosAstLinter()
    linter.visit(tree)
    return linter.violations
