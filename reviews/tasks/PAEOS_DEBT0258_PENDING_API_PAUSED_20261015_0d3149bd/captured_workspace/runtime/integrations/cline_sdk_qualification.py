"""Read-only qualification of an installed public Cline SDK package closure.

This module never starts Cline, reads a Cline profile, or contacts a provider.  It binds the
installed public declarations and runtime package bytes that a later admission adapter may use.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import asdict, dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any

SDK_QUALIFICATION_SCHEMA = "paeos.cline-sdk-qualification/1"
_VERSION = re.compile(r"^v?\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


class QualificationGap(StrEnum):
    """Stable reasons that make a public SDK installation unqualifiable."""

    MISSING_PUBLIC_SYMBOL = "MISSING_PUBLIC_SYMBOL"
    MISSING_LOCAL_BACKEND = "MISSING_LOCAL_BACKEND"
    MISSING_TOOL_CONTROL = "MISSING_TOOL_CONTROL"
    OPAQUE_PROVIDER_BOUNDARY = "OPAQUE_PROVIDER_BOUNDARY"
    PACKAGE_ESCAPE = "PACKAGE_ESCAPE"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"


class QualificationError(RuntimeError):
    """Fail-closed qualification result containing no package file content."""

    def __init__(self, gaps: set[QualificationGap] | tuple[QualificationGap, ...]) -> None:
        self.gaps = tuple(sorted(set(gaps), key=lambda gap: gap.value))
        super().__init__(",".join(gap.value for gap in self.gaps))


@dataclass(frozen=True, slots=True)
class QualifiedFile:
    role: str
    relative_path: str
    sha256: str
    byte_count: int


@dataclass(frozen=True, slots=True)
class AdapterQualificationRecord:
    schema: str
    cline_version: str
    sdk_version: str
    core_version: str
    node_version: str
    node_executable: str
    node_sha256: str
    package_root: str
    sdk_entrypoint: str
    core_entrypoint: str
    files: tuple[QualifiedFile, ...]
    required_symbols: tuple[str, ...]
    record_sha256: str


_METHOD_SYMBOLS: dict[str, str] = {
    "ClineCore.create": r"(?<![0-9A-Za-z_])static\s+create\s*\(",
    "ClineCore.start": r"(?<![0-9A-Za-z_])start\s*\(",
    "ClineCore.subscribe": r"(?<![0-9A-Za-z_])subscribe\s*\(",
    "ClineCore.abort": r"(?<![0-9A-Za-z_])abort\s*\(",
    "ClineCore.stop": r"(?<![0-9A-Za-z_])stop\s*\(",
}
_PUBLIC_SYMBOLS: dict[str, str] = {
    "explicit.provider": "providerId",
    "explicit.model": "modelId",
    "explicit.session": "sessionId",
    "feature.enableTools": "enableTools",
    "feature.disableSpawn": "enableSpawnAgent",
    "feature.disableTeams": "enableAgentTeams",
    "feature.disableMcpSettings": "disableMcpSettingsTools",
    "result.manifestPath": "manifestPath",
    "result.messagesPath": "messagesPath",
}
_TOOL_SYMBOLS: dict[str, str] = {
    "tool.toolPolicies": "toolPolicies",
    "tool.requestToolApproval": "requestToolApproval",
    "tool.toolExecutors": "toolExecutors",
}


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _record_payload(record: AdapterQualificationRecord, *, include_hash: bool) -> dict[str, Any]:
    payload = asdict(record)
    if not include_hash:
        payload.pop("record_sha256")
    return payload


def _load_package(path: Path, gaps: set[QualificationGap]) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        gaps.add(QualificationGap.VERSION_MISMATCH)
        return None
    if not isinstance(value, dict):
        gaps.add(QualificationGap.VERSION_MISMATCH)
        return None
    return value


def _resolved_regular_file(path: Path, gaps: set[QualificationGap]) -> Path | None:
    if not path.is_absolute():
        gaps.add(QualificationGap.PACKAGE_ESCAPE)
        return None
    try:
        resolved = path.resolve(strict=True)
        mode = resolved.stat().st_mode
    except OSError:
        gaps.add(QualificationGap.PACKAGE_ESCAPE)
        return None
    if not stat.S_ISREG(mode):
        gaps.add(QualificationGap.PACKAGE_ESCAPE)
        return None
    return resolved


def _safe_package_root(path: Path, cline_root: Path, gaps: set[QualificationGap]) -> Path | None:
    if not path.is_absolute():
        gaps.add(QualificationGap.PACKAGE_ESCAPE)
        return None
    try:
        resolved = path.resolve(strict=True)
        if path.is_symlink() or not resolved.is_dir() or not resolved.is_relative_to(cline_root):
            raise ValueError
    except (OSError, ValueError):
        gaps.add(QualificationGap.PACKAGE_ESCAPE)
        return None
    return resolved


def _dependency_root(cline_root: Path, dependency: str) -> Path:
    return cline_root / "node_modules" / Path(*dependency.split("/"))


def _resolve_dependency_root(
    cline_root: Path,
    requester_root: Path,
    dependency: str,
    gaps: set[QualificationGap],
) -> Path | None:
    relative = Path(*dependency.split("/"))
    current = requester_root
    while current.is_relative_to(cline_root):
        candidate = current / "node_modules" / relative
        if candidate.exists():
            return _safe_package_root(candidate, cline_root, gaps)
        if current == cline_root:
            break
        current = current.parent
    gaps.add(QualificationGap.MISSING_DEPENDENCY)
    return None


def _package_closure(
    cline_root: Path,
    initial: tuple[str, ...],
    gaps: set[QualificationGap],
) -> dict[str, Path]:
    pending = [(name, cline_root) for name in initial]
    roots: dict[str, Path] = {}
    while pending:
        name, requester_root = pending.pop(0)
        root = _resolve_dependency_root(cline_root, requester_root, name, gaps)
        if root is None:
            continue
        identity = root.relative_to(cline_root).as_posix()
        if identity in roots:
            continue
        manifest = _load_package(root / "package.json", gaps)
        if manifest is None or manifest.get("name") != name:
            gaps.add(QualificationGap.VERSION_MISMATCH)
            continue
        roots[identity] = root
        dependencies = manifest.get("dependencies", {})
        if not isinstance(dependencies, dict):
            gaps.add(QualificationGap.VERSION_MISMATCH)
            continue
        pending.extend(
            (key, root) for key in sorted(key for key in dependencies if isinstance(key, str))
        )
    return roots


def _collect_package_files(
    cline_root: Path, packages: dict[str, Path], gaps: set[QualificationGap]
) -> tuple[QualifiedFile, ...]:
    found: list[QualifiedFile] = []
    for _, package_root in sorted(packages.items()):
        manifest = _load_package(package_root / "package.json", gaps)
        package_name = manifest.get("name") if manifest else None
        if not isinstance(package_name, str):
            gaps.add(QualificationGap.VERSION_MISMATCH)
            continue
        for directory, names, filenames in os.walk(package_root, followlinks=False):
            directory_path = Path(directory)
            names[:] = sorted(name for name in names if name != "node_modules")
            for name in [*names, *sorted(filenames)]:
                candidate = directory_path / name
                try:
                    if candidate.is_symlink():
                        gaps.add(QualificationGap.PACKAGE_ESCAPE)
                except OSError:
                    gaps.add(QualificationGap.PACKAGE_ESCAPE)
            for filename in sorted(filenames):
                candidate = directory_path / filename
                if candidate.is_symlink():
                    continue
                try:
                    if not candidate.is_file():
                        continue
                    data = candidate.read_bytes()
                    relative = candidate.relative_to(cline_root).as_posix()
                except (OSError, ValueError):
                    gaps.add(QualificationGap.PACKAGE_ESCAPE)
                    continue
                found.append(
                    QualifiedFile(
                        role=f"package:{package_name}",
                        relative_path=relative,
                        sha256=hashlib.sha256(data).hexdigest(),
                        byte_count=len(data),
                    )
                )
    return tuple(sorted(found, key=lambda item: item.relative_path))


def _public_declarations(packages: dict[str, Path], gaps: set[QualificationGap]) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for package_name in ("@cline/sdk", "@cline/core"):
        root = next(
            (
                path
                for path in packages.values()
                if json.loads((path / "package.json").read_text(encoding="utf-8")).get("name")
                == package_name
            ),
            None,
        )
        if root is None:
            continue
        parts: list[str] = []
        for path in sorted(root.rglob("*.d.ts")):
            if path.is_symlink() or "node_modules" in path.relative_to(root).parts:
                gaps.add(QualificationGap.PACKAGE_ESCAPE)
                continue
            try:
                parts.append(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError):
                gaps.add(QualificationGap.VERSION_MISMATCH)
        declarations[package_name] = "\n".join(parts)
    return declarations


def _has_identifier(declarations: str, identifier: str) -> bool:
    return (
        re.search(rf"(?<![0-9A-Za-z_]){re.escape(identifier)}(?![0-9A-Za-z_])", declarations)
        is not None
    )


def _public_entrypoint(package_root: Path, manifest: dict[str, Any]) -> Path | None:
    exports = manifest.get("exports")
    candidate: object = None
    if isinstance(exports, dict):
        root_export = exports.get(".")
        if isinstance(root_export, dict):
            candidate = root_export.get("import")
        elif isinstance(root_export, str):
            candidate = root_export
    if candidate is None:
        candidate = manifest.get("main")
    if not isinstance(candidate, str):
        return None
    try:
        resolved = (package_root / candidate).resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_relative_to(package_root) or not resolved.is_file():
        return None
    return resolved


def qualify_cline_sdk(
    cline_package_root: Path, node_executable: Path
) -> AdapterQualificationRecord:
    """Qualify public declarations and bytes without starting Cline or reading its profile."""

    gaps: set[QualificationGap] = set()
    if not cline_package_root.is_absolute():
        raise QualificationError({QualificationGap.PACKAGE_ESCAPE})
    try:
        cline_root = cline_package_root.resolve(strict=True)
    except OSError:
        raise QualificationError({QualificationGap.PACKAGE_ESCAPE}) from None
    if cline_package_root.is_symlink() or not cline_root.is_dir():
        raise QualificationError({QualificationGap.PACKAGE_ESCAPE})

    node = _resolved_regular_file(node_executable, gaps)
    cline_manifest = _load_package(cline_root / "package.json", gaps)
    if node is None or cline_manifest is None:
        raise QualificationError(gaps)

    cline_dependencies = cline_manifest.get("dependencies", {})
    if not isinstance(cline_dependencies, dict):
        raise QualificationError({QualificationGap.VERSION_MISMATCH})
    packages = _package_closure(cline_root, ("@cline/sdk", "@cline/core"), gaps)
    sdk_manifest = _load_package(_dependency_root(cline_root, "@cline/sdk") / "package.json", gaps)
    core_manifest = _load_package(
        _dependency_root(cline_root, "@cline/core") / "package.json", gaps
    )
    if sdk_manifest is None or core_manifest is None:
        raise QualificationError(gaps)

    cline_version = cline_manifest.get("version")
    sdk_version = sdk_manifest.get("version")
    core_version = core_manifest.get("version")
    versions = (cline_version, sdk_version, core_version)
    if not all(isinstance(value, str) and value for value in versions):
        gaps.add(QualificationGap.VERSION_MISMATCH)
    if cline_dependencies.get("@cline/sdk") != sdk_version:
        gaps.add(QualificationGap.VERSION_MISMATCH)
    if cline_dependencies.get("@cline/core") != core_version:
        gaps.add(QualificationGap.VERSION_MISMATCH)
    if sdk_manifest.get("dependencies", {}).get("@cline/core") != core_version:
        gaps.add(QualificationGap.VERSION_MISMATCH)

    sdk_root = _safe_package_root(_dependency_root(cline_root, "@cline/sdk"), cline_root, gaps)
    core_root = _safe_package_root(_dependency_root(cline_root, "@cline/core"), cline_root, gaps)
    sdk_entry = _public_entrypoint(sdk_root, sdk_manifest) if sdk_root else None
    core_entry = _public_entrypoint(core_root, core_manifest) if core_root else None
    if sdk_entry is None or core_entry is None:
        gaps.add(QualificationGap.MISSING_PUBLIC_SYMBOL)

    declaration_map = _public_declarations(packages, gaps)
    core_declarations = declaration_map.get("@cline/core", "")
    missing_public = [
        name
        for name, pattern in _METHOD_SYMBOLS.items()
        if not re.search(pattern, core_declarations)
    ]
    missing_public.extend(
        name
        for name, token in _PUBLIC_SYMBOLS.items()
        if not _has_identifier(core_declarations, token)
    )
    if missing_public:
        gaps.add(QualificationGap.MISSING_PUBLIC_SYMBOL)
    missing_tools = [
        name
        for name, token in _TOOL_SYMBOLS.items()
        if not _has_identifier(core_declarations, token)
    ]
    if missing_tools:
        gaps.add(QualificationGap.MISSING_TOOL_CONTROL)
    if '"local"' not in core_declarations and "'local'" not in core_declarations:
        gaps.add(QualificationGap.MISSING_LOCAL_BACKEND)
    if not re.search(r"\bfetch\s*\?\s*:\s*typeof\s+fetch\b", core_declarations):
        gaps.add(QualificationGap.OPAQUE_PROVIDER_BOUNDARY)

    files = _collect_package_files(cline_root, packages, gaps)
    try:
        version_result = subprocess.run(
            [str(node), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            env={},
        )
    except (OSError, subprocess.SubprocessError):
        gaps.add(QualificationGap.VERSION_MISMATCH)
        node_version = ""
    else:
        node_version = version_result.stdout.strip()
        if version_result.returncode != 0 or not _VERSION.fullmatch(node_version):
            gaps.add(QualificationGap.VERSION_MISMATCH)

    if gaps:
        raise QualificationError(gaps)

    required_symbols = tuple(
        sorted((*_METHOD_SYMBOLS, *_PUBLIC_SYMBOLS, *_TOOL_SYMBOLS, "backend.local", "fetch"))
    )
    record = AdapterQualificationRecord(
        schema=SDK_QUALIFICATION_SCHEMA,
        cline_version=str(cline_version),
        sdk_version=str(sdk_version),
        core_version=str(core_version),
        node_version=node_version.removeprefix("v"),
        node_executable=str(node),
        node_sha256=hashlib.sha256(node.read_bytes()).hexdigest(),
        package_root=str(cline_root),
        sdk_entrypoint=str(sdk_entry),
        core_entrypoint=str(core_entry),
        files=files,
        required_symbols=required_symbols,
        record_sha256="",
    )
    digest = hashlib.sha256(
        _canonical_bytes(_record_payload(record, include_hash=False))
    ).hexdigest()
    return replace(record, record_sha256=digest)


def write_qualification_record(record: AdapterQualificationRecord, output: Path) -> None:
    """Durably create one canonical qualification record without replacing existing evidence."""

    if not output.is_absolute():
        raise ValueError("output must be absolute")
    payload = _canonical_bytes(_record_payload(record, include_hash=True)) + b"\n"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(fd)
    directory_fd = os.open(output.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
