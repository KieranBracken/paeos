"""Unit tests for PaeosAstLinter and AST verification (RB-0015 / RB-ARCH-VERIFY-004)."""

from __future__ import annotations

from runtime.ast_linter import check_ast


def test_ast_linter_detects_swallowed_exceptions() -> None:
    bad_code = """
def bad_function():
    try:
        x = 1 / 0
    except Exception:
        pass
"""
    violations = check_ast(bad_code)
    assert len(violations) == 1
    assert "PAEOS-AST-02" in violations[0]


def test_ast_linter_detects_bare_except() -> None:
    bad_code = """
def bad_function():
    try:
        do_something()
    except:
        do_fallback()
"""
    violations = check_ast(bad_code)
    assert len(violations) == 1
    assert "PAEOS-AST-01" in violations[0]


def test_ast_linter_passes_valid_code() -> None:
    good_code = """
import logging
logger = logging.getLogger(__name__)

def good_function():
    try:
        result = compute()
    except ValueError as e:
        logger.exception("Failed computation: %s", e)
        raise
"""
    violations = check_ast(good_code)
    assert len(violations) == 0
