from kernel.cas import CAS, InMemoryCasStore
from runtime.ast_linter import check_ast_violations
from runtime.verification import vacuous_commands


def test_ast_linter_rejects_bare_except():
    code = "try:\n    pass\nexcept:\n    pass"
    violations = check_ast_violations(code)
    assert len(violations) > 0
    assert violations[0].rule_id == "PAEOS-AST-01"


def test_ast_linter_rejects_swallowed_exception():
    code = "try:\n    pass\nexcept Exception:\n    pass"
    violations = check_ast_violations(code)
    assert len(violations) > 0
    assert any(v.rule_id == "PAEOS-AST-02" for v in violations)


def test_ast_linter_rejects_silent_return():
    code = "def foo():\n    try:\n        pass\n    except Exception:\n        return None"
    violations = check_ast_violations(code)
    assert len(violations) > 0
    assert any(v.rule_id == "PAEOS-AST-03" for v in violations)


def test_ast_linter_allows_logging():
    code = "import logging\ntry:\n    pass\nexcept Exception as e:\n    logging.exception(e)"
    violations = check_ast_violations(code)
    assert len(violations) == 0


def test_vacuous_commands(tmp_path):
    cas = CAS(InMemoryCasStore())

    # Setup mock repo
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "test.py").write_text("print('test')")

    # Create fake written path (the change)
    change_content = b"print('changed')"
    h = cas.put(change_content)
    written = (("test.py", h),)

    # A command that doesn't care about the change (vacuous)
    commands = ("python -c 'print(1)'",)

    vacuous = vacuous_commands(repo, written, cas, commands)
    assert "python -c 'print(1)'" in vacuous
