"""AST-Based Anti-Pattern Linter for PAEOS Court Verification (RB-0015 / RB-ARCH-VERIFY-004).

Statically inspects Python syntax trees to reject bare `except:`, swallowed exceptions (`except Exception: pass`),
and un-logged fallback returns before code execution or unit testing.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AstViolation:
    line_number: int
    rule_id: str
    message: str


class PaeosAstVisitor(ast.NodeVisitor):
    """AST Visitor enforcing PAEOS Exception Handling Rules (PAEOS-AST-01..03)."""

    def __init__(self) -> None:
        self.violations: list[AstViolation] = []

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        lineno = node.lineno

        # PAEOS-AST-01: Bare `except:` is strictly forbidden
        if node.type is None:
            self.violations.append(
                AstViolation(
                    line_number=lineno,
                    rule_id="PAEOS-AST-01",
                    message="Bare 'except:' is strictly forbidden. Specify exception types explicitly.",
                )
            )

        # PAEOS-AST-02 & PAEOS-AST-03: Single-statement body checks (pass / silent return)
        body = node.body
        if len(body) == 1:
            stmt = body[0]
            if isinstance(stmt, ast.Pass):
                self.violations.append(
                    AstViolation(
                        line_number=lineno,
                        rule_id="PAEOS-AST-02",
                        message="Silent 'except Exception: pass' is forbidden. Log exception or raise.",
                    )
                )
            elif isinstance(stmt, ast.Return):
                # Return None or empty without logging
                val = stmt.value
                if val is None or (isinstance(val, ast.Constant) and val.value is None):
                    self.violations.append(
                        AstViolation(
                            line_number=lineno,
                            rule_id="PAEOS-AST-03",
                            message="Un-logged 'except Exception: return None' is forbidden.",
                        )
                    )

        self.generic_visit(node)


def check_ast_violations(code: str, filename: str = "<unknown>") -> tuple[AstViolation, ...]:
    """Parse python source code into an AST and return any PAEOS AST violations."""
    try:
        tree = ast.parse(code, filename=filename)
    except SyntaxError as exc:
        return (
            AstViolation(
                line_number=exc.lineno or 1,
                rule_id="PAEOS-AST-SYNTAX",
                message=f"Syntax error during AST parsing: {exc.msg}",
            ),
        )

    visitor = PaeosAstVisitor()
    visitor.visit(tree)
    return tuple(visitor.violations)


def check_file_ast(file_path: Path) -> tuple[AstViolation, ...]:
    """Check a Python file for AST violations."""
    if not file_path.is_file() or file_path.suffix != ".py":
        return ()
    code = file_path.read_text(encoding="utf-8")
    return check_ast_violations(code, filename=str(file_path))
