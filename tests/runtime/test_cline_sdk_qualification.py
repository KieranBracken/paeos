"""Behavioral tests for the read-only public Cline SDK qualification boundary."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
from runtime.integrations.cline_sdk_qualification import (
    QualificationError,
    QualificationGap,
    qualify_cline_sdk,
    write_qualification_record,
)

from ops import cline_sdk_inspect

DECLARATIONS = """
export declare class ClineCore {
  static create(options?: ClineCoreOptions): Promise<ClineCore>;
  start(input: StartSessionInput): Promise<StartSessionResult>;
  subscribe(listener: (event: unknown) => void): () => void;
  abort(sessionId: string): Promise<void>;
  stop(sessionId: string): Promise<void>;
}
export type RuntimeHostMode = "local" | "hub" | "remote" | "auto";
export interface ClineCoreOptions {
  backendMode?: RuntimeHostMode;
  fetch?: typeof fetch;
}
export interface StartSessionInput {
  providerId: string;
  modelId: string;
  sessionId?: string;
  enableTools: boolean;
  enableSpawnAgent: boolean;
  enableAgentTeams: boolean;
  disableMcpSettingsTools?: boolean;
  toolPolicies?: unknown;
  toolExecutors?: unknown;
  requestToolApproval?: (request: unknown) => unknown;
}
export interface StartSessionResult {
  sessionId: string;
  manifestPath: string;
  messagesPath: string;
}
""".strip()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _package_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "cline"
    _write(
        root / "package.json",
        json.dumps(
            {
                "name": "cline",
                "version": "3.0.60",
                "dependencies": {"@cline/sdk": "0.0.81", "@cline/core": "0.0.81"},
            }
        ),
    )
    for name, dependencies in (("sdk", {"@cline/core": "0.0.81"}), ("core", {})):
        package = root / "node_modules" / "@cline" / name
        _write(
            package / "package.json",
            json.dumps(
                {
                    "name": f"@cline/{name}",
                    "version": "0.0.81",
                    "type": "module",
                    "main": "./dist/index.js",
                    "types": "./dist/index.d.ts",
                    "exports": {".": {"types": "./dist/index.d.ts", "import": "./dist/index.js"}},
                    "dependencies": dependencies,
                }
            ),
        )
        _write(package / "dist" / "index.js", f"export const packageName = '@cline/{name}';\n")
        _write(package / "dist" / "index.d.ts", DECLARATIONS)

    node = tmp_path / "node"
    node.write_bytes(b"#!/bin/sh\nprintf 'v24.1.0\\n'\n")
    node.chmod(0o700)
    return root, node


def test_qualification_hashes_exact_public_sdk_closure(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)

    record = qualify_cline_sdk(root, node)

    paths = [item.relative_path for item in record.files]
    assert paths == sorted(paths)
    assert "node_modules/@cline/sdk/dist/index.js" in paths
    assert "node_modules/@cline/core/dist/index.d.ts" in paths
    sdk_js = root / "node_modules/@cline/sdk/dist/index.js"
    item = next(
        value for value in record.files if value.relative_path.endswith("sdk/dist/index.js")
    )
    assert item.sha256 == hashlib.sha256(sdk_js.read_bytes()).hexdigest()
    assert item.byte_count == len(sdk_js.read_bytes())
    assert record.cline_version == "3.0.60"
    assert record.sdk_version == record.core_version == "0.0.81"
    assert len(record.record_sha256) == 64


@pytest.mark.parametrize("missing", ["static create(", "start(", "subscribe(", "abort(", "stop("])
def test_qualification_rejects_missing_core_lifecycle_symbol(tmp_path: Path, missing: str) -> None:
    root, node = _package_tree(tmp_path)
    declaration = root / "node_modules/@cline/core/dist/index.d.ts"
    declaration.write_text(DECLARATIONS.replace(missing, f"missing_{missing}"), encoding="utf-8")

    with pytest.raises(QualificationError) as exc:
        qualify_cline_sdk(root, node)

    assert QualificationGap.MISSING_PUBLIC_SYMBOL in exc.value.gaps


def test_qualification_rejects_missing_local_backend_mode(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)
    for declaration in root.glob("node_modules/@cline/*/dist/index.d.ts"):
        declaration.write_text(DECLARATIONS.replace('"local" | ', ""), encoding="utf-8")

    with pytest.raises(QualificationError) as exc:
        qualify_cline_sdk(root, node)

    assert QualificationGap.MISSING_LOCAL_BACKEND in exc.value.gaps


@pytest.mark.parametrize("missing", ["toolPolicies", "requestToolApproval", "toolExecutors"])
def test_qualification_rejects_missing_tool_control(tmp_path: Path, missing: str) -> None:
    root, node = _package_tree(tmp_path)
    for declaration in root.glob("node_modules/@cline/*/dist/index.d.ts"):
        declaration.write_text(
            DECLARATIONS.replace(missing, f"missing_{missing}"), encoding="utf-8"
        )

    with pytest.raises(QualificationError) as exc:
        qualify_cline_sdk(root, node)

    assert QualificationGap.MISSING_TOOL_CONTROL in exc.value.gaps


def test_qualification_rejects_missing_injected_fetch_boundary(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)
    for declaration in root.glob("node_modules/@cline/*/dist/index.d.ts"):
        declaration.write_text(
            DECLARATIONS.replace("fetch?: typeof fetch", "fetchBoundary?: never")
        )

    with pytest.raises(QualificationError) as exc:
        qualify_cline_sdk(root, node)

    assert QualificationGap.OPAQUE_PROVIDER_BOUNDARY in exc.value.gaps


def test_qualification_rejects_symlink_escape_from_package_root(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)
    outside = tmp_path / "outside.js"
    outside.write_text("export const escaped = true;\n", encoding="utf-8")
    target = root / "node_modules/@cline/sdk/dist/escape.js"
    target.symlink_to(outside)

    with pytest.raises(QualificationError) as exc:
        qualify_cline_sdk(root, node)

    assert QualificationGap.PACKAGE_ESCAPE in exc.value.gaps


def test_qualification_output_is_canonical_and_contains_no_file_contents(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)
    record = qualify_cline_sdk(root, node)
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    write_qualification_record(record, first)
    write_qualification_record(record, second)

    assert first.read_bytes() == second.read_bytes()
    assert first.stat().st_mode & 0o777 == 0o600
    payload = first.read_text(encoding="utf-8")
    assert DECLARATIONS not in payload
    assert "printf 'v24.1.0" not in payload
    assert json.loads(payload)["schema"] == "paeos.cline-sdk-qualification/1"


def test_qualification_record_is_create_only(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)
    record = qualify_cline_sdk(root, node)
    output = tmp_path / "qualification.json"
    output.write_text("existing", encoding="utf-8")

    with pytest.raises(FileExistsError):
        write_qualification_record(record, output)

    assert output.read_text(encoding="utf-8") == "existing"


def test_qualification_rejects_non_absolute_inputs(tmp_path: Path) -> None:
    _, node = _package_tree(tmp_path)

    with pytest.raises(QualificationError) as exc:
        qualify_cline_sdk(Path("relative/cline"), node)

    assert QualificationGap.PACKAGE_ESCAPE in exc.value.gaps


def test_qualification_resolves_nested_node_dependency(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)
    core = root / "node_modules/@cline/core"
    manifest_path = core / "package.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["dependencies"]["nested-runtime"] = "1.0.0"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    nested = core / "node_modules/nested-runtime"
    _write(
        nested / "package.json",
        json.dumps(
            {
                "name": "nested-runtime",
                "version": "1.0.0",
                "main": "./index.js",
                "dependencies": {},
            }
        ),
    )
    _write(nested / "index.js", "export const nested = true;\n")

    record = qualify_cline_sdk(root, node)

    assert any(item.relative_path.endswith("nested-runtime/index.js") for item in record.files)


def test_missing_dependency_is_not_misreported_as_package_escape(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)
    core_manifest = root / "node_modules/@cline/core/package.json"
    manifest = json.loads(core_manifest.read_text(encoding="utf-8"))
    manifest["dependencies"]["absent-runtime"] = "1.0.0"
    core_manifest.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(QualificationError) as exc:
        qualify_cline_sdk(root, node)

    assert exc.value.gaps == (QualificationGap.MISSING_DEPENDENCY,)


def test_qualification_resolves_and_hashes_symlinked_node_executable(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)
    link = tmp_path / "node-link"
    os.symlink(node, link)

    record = qualify_cline_sdk(root, link)

    assert record.node_sha256 == hashlib.sha256(node.read_bytes()).hexdigest()
    assert record.node_executable == str(node.resolve())


def test_inspector_cli_writes_one_canonical_record(tmp_path: Path) -> None:
    root, node = _package_tree(tmp_path)
    output = tmp_path / "qualification.json"

    result = cline_sdk_inspect.main(
        [
            "--cline-package-root",
            str(root),
            "--node-executable",
            str(node),
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert json.loads(output.read_text(encoding="utf-8"))["record_sha256"]


def test_inspector_cli_preserves_existing_output(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root, node = _package_tree(tmp_path)
    output = tmp_path / "qualification.json"
    output.write_text("do-not-replace", encoding="utf-8")

    result = cline_sdk_inspect.main(
        [
            "--cline-package-root",
            str(root),
            "--node-executable",
            str(node),
            "--output",
            str(output),
        ]
    )

    assert result == 2
    assert output.read_text(encoding="utf-8") == "do-not-replace"
    assert "OUTPUT_EXISTS" in capsys.readouterr().err
