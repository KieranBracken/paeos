"""AST Static Anti-Pattern Linter (PAEOS RB-0015 / RB-ARCH-VERIFY-004).

Scans Abstract Syntax Trees of Python source code to detect swallowed exceptions, bare excepts,
and un-logged fallback returns before Court verification runs.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path

__all__ = [
    "PaeosAstLinter",
    "PaeosMockDetector",
    "check_ast",
    "detect_mock_usage",
    "verify_production_event_stream",
]


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


class PaeosMockDetector(ast.NodeVisitor):
    """AST visitor detecting unauthorized mock imports and synthetic test stubs in production paths (ELH-05)."""

    def __init__(self, *, is_test_file: bool = False) -> None:
        self.violations: list[str] = []
        self.is_test_file = is_test_file

    def visit_Import(self, node: ast.Import) -> None:
        if not self.is_test_file:
            forbidden_modules = {
                "unittest.mock",
                "mock",
                "pytest_mock",
                "responses",
                "freezegun",
                "httpretty",
                "respx",
                "requests_mock",
            }
            for alias in node.names:
                name_low = alias.name.lower()
                asname_low = (alias.asname or "").lower()
                if (
                    alias.name in forbidden_modules
                    or alias.name.startswith("unittest.mock.")
                    or any(name_low == m or name_low.startswith(m + ".") for m in forbidden_modules)
                    or any(kw in asname_low for kw in ("mock", "monkeypatch", "fake", "stub"))
                ):
                    self.violations.append(
                        f"Line {node.lineno}: Import of mock framework '{alias.name}' forbidden in production code (PAEOS-AST-MOCK-01)."
                    )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if not self.is_test_file:
            mod = (node.module or "").lower()
            forbidden_modules = {
                "unittest.mock",
                "mock",
                "pytest_mock",
                "responses",
                "freezegun",
                "httpretty",
                "respx",
                "requests_mock",
            }
            if mod in forbidden_modules or any(mod == m or mod.startswith(m + ".") for m in forbidden_modules):
                self.violations.append(
                    f"Line {node.lineno}: From-import of mock framework '{node.module}' forbidden in production code (PAEOS-AST-MOCK-01)."
                )
            elif mod == "unittest":
                for alias in node.names:
                    if alias.name == "mock" or (alias.asname and "mock" in alias.asname.lower()):
                        self.violations.append(
                            f"Line {node.lineno}: Import of 'unittest.mock' via '{alias.name}' forbidden in production code (PAEOS-AST-MOCK-01)."
                        )
            forbidden_symbols = {
                "magicmock",
                "mock",
                "asyncmock",
                "propertymock",
                "patch",
                "create_autospec",
                "monkeypatch",
            }
            for alias in node.names:
                name_low = alias.name.lower()
                asname_low = (alias.asname or "").lower()
                if (
                    name_low in forbidden_symbols
                    or any(name_low.startswith(kw) for kw in ("mock", "fake", "stub"))
                    or any(kw in asname_low for kw in ("mock", "monkeypatch", "fake", "stub"))
                ):
                    self.violations.append(
                        f"Line {node.lineno}: Import of mock symbol '{alias.name}' forbidden in production code (PAEOS-AST-MOCK-01)."
                    )
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if not self.is_test_file:
            attr_low = node.attr.lower()
            if attr_low in {
                "magicmock",
                "mock",
                "asyncmock",
                "propertymock",
                "patch",
                "monkeypatch",
            }:
                self.violations.append(
                    f"Line {node.lineno}: Reference to mock attribute '{node.attr}' forbidden in production code (PAEOS-AST-MOCK-02)."
                )
            elif isinstance(node.value, ast.Name) and node.value.id == "unittest" and node.attr == "mock":
                self.violations.append(
                    f"Line {node.lineno}: Reference to 'unittest.mock' forbidden in production code (PAEOS-AST-MOCK-02)."
                )
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if not self.is_test_file and node.id.lower() in {"magicmock", "mock", "asyncmock", "propertymock", "monkeypatch"}:
            self.violations.append(
                f"Line {node.lineno}: Direct usage of mock class '{node.id}' forbidden in production code (PAEOS-AST-MOCK-03)."
            )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not self.is_test_file:
            name_low = node.name.lower()
            if (
                name_low.startswith(("fake", "mock", "stub"))
            ) and not name_low.endswith("detector") and not name_low.endswith("linter"):
                self.violations.append(
                    f"Line {node.lineno}: Definition of mock/stub/fake class '{node.name}' forbidden in production code (PAEOS-AST-MOCK-05)."
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if not self.is_test_file:
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr
            if func_name in {"import_module", "__import__"} and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str):
                    val = first_arg.value
                    if "mock" in val:
                        self.violations.append(
                            f"Line {node.lineno}: Dynamic import of '{val}' forbidden in production code (PAEOS-AST-MOCK-04)."
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


def detect_mock_usage(source_or_path: str | Path, *, is_test_file: bool = False) -> list[str]:
    """Scan Python source code for forbidden mock imports or mock object creation."""
    if isinstance(source_or_path, Path):
        try:
            source = source_or_path.read_text(encoding="utf-8")
            if not is_test_file:
                path_str = str(source_or_path).replace("\\", "/")
                is_test_file = "tests/" in path_str or "test_" in path_str
        except OSError as e:
            return [f"Could not read file {source_or_path}: {e}"]
    else:
        source = str(source_or_path)

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [f"SyntaxError parsing AST: {e}"]

    detector = PaeosMockDetector(is_test_file=is_test_file)
    detector.visit(tree)
    return detector.violations


def verify_production_event_stream(events: object) -> tuple[bool, list[str]]:
    """Verify live ledger event stream contains authentic production lifecycle events (ELH-05).
    
    Requires presence and causal order of L05 (research), L06 (tradeoff), L11 (freeze), and L13 (verification/audit),
    strict monotonically non-decreasing sequence numbers, PRODUCTION domain integrity, and cryptographic row hash
    continuity when Ledger or LedgerRow instances are supplied.
    """
    if hasattr(events, "_store") and hasattr(events._store, "read"):
        events = events._store.read(1, None)
    elif not isinstance(events, list) and isinstance(events, Iterable):
        events = list(events)
    elif not isinstance(events, list):
        events = [events]

    violations: list[str] = []
    event_kinds: list[str] = []
    l05_idx = -1
    l06_idx = -1
    l11_idx = -1
    l13_idx = -1

    last_seq = 0
    last_row_hash: str | None = None
    for idx, ev in enumerate(events):
        kind = getattr(ev, "kind", None)
        if kind is None and hasattr(ev, "event"):
            kind = getattr(ev.event, "kind", None)
        if isinstance(ev, dict) and "kind" in ev:
            kind = ev["kind"]

        kind_str = str(kind) if kind else ""
        event_kinds.append(kind_str)

        # Domain & State integrity check
        domain = getattr(ev, "domain_tag", None)
        if domain is None and hasattr(ev, "event"):
            domain = getattr(ev.event, "domain_tag", None)
        if isinstance(ev, dict) and "domain_tag" in ev:
            domain = ev["domain_tag"]
        if domain is None or not str(domain).strip():
            violations.append(f"PROD-PATH-DOMAIN-MISSING: Event {idx} missing mandatory domain_tag; must be PRODUCTION")
        elif str(domain).upper() != "PRODUCTION":
            violations.append(f"PROD-PATH-CONTAMINATION: Non-production domain '{domain}' present in event {idx}")

        # Check for synthetic flags in payload
        payload = getattr(ev, "payload", None)
        if payload is None and hasattr(ev, "event"):
            payload = getattr(ev.event, "payload", None)
        if isinstance(ev, dict) and "payload" in ev:
            payload = ev["payload"]
        if isinstance(payload, dict):
            if any(kw in str(payload).lower() for kw in ("synthetic", "mock_id", "test_fixture", "fake_evidence", "synthetic_mock")):
                violations.append(f"PROD-PATH-SYNTHETIC: Event {idx} payload contains synthetic test markers")

        # Sequence monotonicity and density
        seq = getattr(ev, "seq", None)
        if seq is None and hasattr(ev, "event"):
            seq = getattr(ev.event, "seq", None)
        if isinstance(ev, dict) and "seq" in ev:
            seq = ev["seq"]
        if seq is None or not isinstance(seq, int) or seq <= 0:
            violations.append(f"PROD-PATH-SEQUENCE-MISSING: Event {idx} missing valid strictly positive integer sequence number")
        else:
            if idx == 0 and seq != 1:
                violations.append(f"PROD-PATH-SEQUENCE-GAP: Initial event seq must be 1, got {seq}")
            elif idx > 0 and seq != last_seq + 1:
                if seq <= last_seq:
                    violations.append(f"PROD-PATH-SEQUENCE-REGRESSION: Event seq {seq} <= previous seq {last_seq}")
                else:
                    violations.append(f"PROD-PATH-SEQUENCE-GAP: Event seq {seq} != expected dense seq {last_seq + 1}")
            last_seq = seq

        # Cryptographic Row Hash & Chain Integrity Verification
        ev_prev_hash = getattr(ev, "prev_hash", None)
        ev_row_hash = getattr(ev, "row_hash", None)
        ev_timestamp = getattr(ev, "timestamp", None)
        ev_event = getattr(ev, "event", None)

        if isinstance(ev, dict):
            ev_prev_hash = ev.get("prev_hash")
            ev_row_hash = ev.get("row_hash")
            ev_timestamp = ev.get("timestamp")
            if "event" in ev:
                ev_event = ev["event"]
            elif "payload" in ev and "schema_ver" in ev and kind is not None:
                from kernel.types import Event as EventObj
                ev_event = EventObj(schema_ver=int(ev["schema_ver"]), kind=str(kind), payload=ev["payload"])

        if ev_prev_hash is None or ev_row_hash is None or ev_timestamp is None or ev_event is None:
            violations.append(
                f"PROD-PATH-UNAUTHENTICATED-ROW: Event {idx} missing mandatory cryptographic row fields (prev_hash, row_hash, timestamp, event)"
            )
        else:
            try:
                from kernel.ledger import compute_row_hash, GENESIS_HASH
                expected_prev = last_row_hash if last_row_hash is not None else GENESIS_HASH
                if ev_prev_hash != expected_prev:
                    violations.append(
                        f"PROD-PATH-HASH-CHAIN-BROKEN: Event seq {seq} prev_hash mismatch: expected {expected_prev}, got {ev_prev_hash}"
                    )
                calc_hash = compute_row_hash(
                    ev_prev_hash, seq, ev_timestamp, ev_event, domain_tag=str(domain).upper() if domain else "PRODUCTION"
                )
                if ev_row_hash != calc_hash:
                    violations.append(
                        f"PROD-PATH-ROW-HASH-CORRUPTED: Event seq {seq} row_hash mismatch: expected {calc_hash}, got {ev_row_hash}"
                    )
                last_row_hash = ev_row_hash
            except Exception as e:
                violations.append(f"PROD-PATH-ROW-HASH-ERROR: Failed cryptographic verification on event seq {seq}: {e}")

        if l05_idx == -1 and (kind_str.startswith("L05_") or "FRONTIER_RESEARCH" in kind_str or "RESEARCH_PACKET" in kind_str):
            l05_idx = idx
        if l06_idx == -1 and (kind_str.startswith("L06_") or "TRADEOFF" in kind_str):
            l06_idx = idx
        if l11_idx == -1 and (kind_str.startswith("L11_") or "FREEZE" in kind_str):
            l11_idx = idx
        if l13_idx == -1 and (kind_str.startswith("L13_") or "COMPLETENESS" in kind_str or "VERIFICATION" in kind_str):
            l13_idx = idx

    if l05_idx == -1:
        violations.append("PROD-PATH-MISSING: No L05 Frontier Research event recorded in live stream")
    if l06_idx == -1:
        violations.append("PROD-PATH-MISSING: No L06 Multi-Criteria Tradeoff event recorded in live stream")
    if l11_idx == -1:
        violations.append("PROD-PATH-MISSING: No L11 Scope-Completeness Freeze event recorded in live stream")
    if l13_idx == -1:
        violations.append("PROD-PATH-MISSING: No L13 Verification/Completeness event recorded in live stream")

    # Lifecycle order enforcement: L05 -> L06 -> L11 -> L13
    if l05_idx != -1 and l06_idx != -1 and l06_idx < l05_idx:
        violations.append("PROD-PATH-ORDER-VIOLATION: L06 Tradeoff recorded before L05 Research")
    if l06_idx != -1 and l11_idx != -1 and l11_idx < l06_idx:
        violations.append("PROD-PATH-ORDER-VIOLATION: L11 Freeze recorded before L06 Tradeoff")
    if l11_idx != -1 and l13_idx != -1 and l13_idx < l11_idx:
        violations.append("PROD-PATH-ORDER-VIOLATION: L13 Verification recorded before L11 Freeze")

    return len(violations) == 0, violations
