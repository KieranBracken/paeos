"""Offline composition checks; synthetic state is never a PAEOS qualification.

These catch a bypassed readiness gate, source-root drift, missing/tampered runtime
resources, or a broken Court execution root. Only external host bindings are replaced.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from nacl.signing import SigningKey
from runtime.builder_transport import BuilderTransportReadiness, canonical_qualification_bytes
from runtime.ceremony import assert_canonical_lifecycle_bound
from runtime.court.completeness_firewall import (
    CompletenessFirewallError,
    load_authoritative_manifest,
)
from runtime.lifecycle_projection import assert_lifecycle_projection_conformant
from runtime.orchestrator import RunStatus
from runtime.scheduler import GlobalBudget, StopReason
from runtime.triage import Trace, triage

from ops import autonomous_run

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_RELATIVE = Path("ops/manifests/p1_authoritative_completeness_manifest.json")
LIFECYCLE_RELATIVE = Path("operations/ENGINEERING_LIFECYCLE.md")
MANIFEST_HASH = "a0fe19d27519af43d870b25352198481fcab1d77f5333b58ae5377c592ac0800"
MANIFEST_FILE_HASH = "372e4b2f307074f1cf5e7483707505805db323a67cb0cf079580fd764494eea8"
LIFECYCLE_HASH = "0bc717cc738a27b126c48d2f9a034998ad7d4a29cca61eeff7f1e63149d8dfae"


def _expired_synthetic_readiness(directory: Path) -> BuilderTransportReadiness:
    """A validly signed but expired negative fixture; never eligible for dispatch."""
    key = SigningKey.generate()
    payload = {
        "schema": "paeos-builder-transport-qualification/1",
        "qualification_scope": "standalone-provider-probe",
        "qualification_id": "synthetic-expired-offline-only",
        "provider": "codex",
        "model": "gpt-5.6-sol",
        "family": "gpt",
        "observed_at": 100,
        "expires_at": 200,
        "lifecycle": ["STARTING", "RUNNING", "PROGRESS", "COMPLETED"],
        "canaries": [
            "approved_read",
            "approved_write",
            "forbidden_read_denied",
            "forbidden_write_denied",
            "parent_secret_invisible",
            "provider_credential_absent",
            "symlink_escape_denied",
            "traversal_escape_denied",
            "child_subprocess_confined",
            "broker_capability_task_scoped",
            "supervisor_restart_no_fallback",
        ],
        "fallback_used": False,
        "manual_chat_bridge": False,
    }
    for field in (
        "supervisor_identity_sha256",
        "request_sha256",
        "response_sha256",
        "artifact_sha256",
        "evidence_sha256",
    ):
        payload[field] = hashlib.sha256(f"synthetic:{field}".encode()).hexdigest()
    path = directory / "synthetic-expired-qualification.json"
    path.write_text(
        json.dumps(
            {
                "payload": payload,
                "signature": key.sign(canonical_qualification_bytes(payload)).signature.hex(),
            }
        ),
        encoding="utf-8",
    )
    path.chmod(0o600)
    return BuilderTransportReadiness(path, key.verify_key, clock=lambda: 500)


@pytest.fixture
def composition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Use the real composition and stores, redirecting host-only seams to tmp_path."""
    workspace = tmp_path / "workspaces"
    registry_root = tmp_path / "registry"
    state = tmp_path / "state"
    captures = SimpleNamespace(loop=None, registry=None, worker_calls=0, registration_calls=0)
    real_loop = autonomous_run.SoftLoop
    real_registry = autonomous_run.RunStateRegistry

    def capture_loop(**kwargs):
        captures.loop = real_loop(**kwargs)
        return captures.loop

    class ObservedRegistry(real_registry):
        def register(self, *args, **kwargs):
            captures.registration_calls += 1
            return super().register(*args, **kwargs)

    def temporary_registry(_host_root, signing_key):
        captures.registry = ObservedRegistry(registry_root, signing_key)
        return captures.registry

    def forbidden_worker(*_args, **_kwargs):
        captures.worker_calls += 1
        raise AssertionError("offline readiness check reached a worker")

    monkeypatch.setattr(autonomous_run, "DEFAULT_CODEX_WORKSPACE_ROOT", workspace)
    monkeypatch.setattr(autonomous_run, "_load_codex_transport", lambda _root: None)
    monkeypatch.setattr(autonomous_run, "_load_luna_planner_transport", lambda _root: None)
    monkeypatch.setattr(autonomous_run, "RunStateRegistry", temporary_registry)
    monkeypatch.setattr(autonomous_run, "SoftLoop", capture_loop)
    monkeypatch.setattr(autonomous_run.CodexRuntime, "run", forbidden_worker)
    stores = []

    def build(readiness=None, repository=ROOT):
        monkeypatch.setattr(autonomous_run, "_load_builder_transport_readiness", lambda: readiness)
        scheduler, _evolution, ledger = autonomous_run.build_scheduler(
            state,
            repository,
            global_budget=GlobalBudget(tokens=8_000_000, wallclock_s=10_800, runs=1),
            max_concurrency=1,
            runtime_type="codex",
        )
        stores.append(ledger)
        return SimpleNamespace(
            scheduler=scheduler,
            ledger=ledger,
            loop=captures.loop,
            state=state,
            workspace=workspace,
            registry_root=registry_root,
            observed=captures,
        )

    yield build
    for ledger in stores:
        ledger.close()
        ledger._store.close()
    if captures.loop is not None:
        captures.loop.scar_store.close()


def test_actual_scheduler_constructs_only_temporary_state(composition) -> None:
    composed = composition()
    report = composed.scheduler.run([])
    assert report.stop_reason is StopReason.SOURCE_EXHAUSTED
    assert report.outcomes == ()
    assert composed.ledger.read() == []
    assert composed.loop.mission_controller.graph.tasks == {}
    assert composed.observed.worker_calls == composed.observed.registration_calls == 0
    assert not composed.registry_root.exists()
    assert composed.workspace.is_dir()
    assert (composed.state / "seal.key").stat().st_mode & 0o777 == 0o600
    config = json.loads((composed.state / "mcp-config.json").read_text())
    server = config["mcpServers"]["paeos-court"]
    assert server["command"] == sys.executable
    assert server["args"] == [
        "-m",
        "runtime.transports.mcp.court_server",
        str(composed.state / "court"),
        str(composed.workspace),
    ]
    assert server["env"] == {"PYTHONPATH": str(ROOT)}


@pytest.mark.parametrize("kind", ["missing-loader", "missing-file", "expired"])
def test_trace_b_readiness_denies_before_registration_or_worker(
    composition,
    tmp_path: Path,
    kind: str,
) -> None:
    readiness = None
    if kind == "missing-file":
        readiness = BuilderTransportReadiness(
            tmp_path / "absent-qualification.json",
            SigningKey.generate().verify_key,
            clock=lambda: 500,
        )
    elif kind == "expired":
        readiness = _expired_synthetic_readiness(tmp_path)
    composed = composition(readiness)
    arguments = {
        "changed_paths": ("runtime/synthetic_codec.py",),
        "verifiable": False,
        "reversible": True,
    }
    assert triage(**arguments, budget_by_class=autonomous_run.DEFAULT_BUDGETS).trace is Trace.B
    outcome = composed.loop.run(
        objective="Synthetic offline readiness rejection, no implementation",
        plan_write_scopes=("runtime/synthetic_codec.py",),
        builder_evidence=(),
        goal_signature="synthetic-offline-readiness",
        run_id="synthetic-offline-run",
        capability_manifest=load_authoritative_manifest(ROOT / MANIFEST_RELATIVE),
        **arguments,
    )
    assert outcome.status is RunStatus.REMANDED
    assert outcome.goal_id == ""
    assert "BuilderTransportReady prerequisite unavailable" in outcome.detail
    if kind == "expired":
        assert "expired or stale" in outcome.detail
    assert composed.observed.worker_calls == composed.observed.registration_calls == 0
    assert composed.loop.mission_controller.graph.tasks == {}
    assert composed.ledger.read() == []
    assert not composed.registry_root.exists()
    assert not list(composed.workspace.iterdir())


def test_captured_manifest_and_lifecycle_are_bound() -> None:
    manifest = load_authoritative_manifest(ROOT / MANIFEST_RELATIVE)
    assert manifest.manifest_sha256 == MANIFEST_HASH
    assert hashlib.sha256((ROOT / MANIFEST_RELATIVE).read_bytes()).hexdigest() == MANIFEST_FILE_HASH
    assert hashlib.sha256((ROOT / LIFECYCLE_RELATIVE).read_bytes()).hexdigest() == LIFECYCLE_HASH
    assert_canonical_lifecycle_bound(ROOT / LIFECYCLE_RELATIVE)
    assert_lifecycle_projection_conformant(ROOT / LIFECYCLE_RELATIVE)


@pytest.mark.parametrize("mutation", ["missing", "tampered"])
def test_scheduler_rejects_missing_or_tampered_manifest(
    composition,
    tmp_path: Path,
    mutation: str,
) -> None:
    repository = tmp_path / "resource-copy"
    target = repository / MANIFEST_RELATIVE
    target.parent.mkdir(parents=True)
    if mutation == "tampered":
        value = json.loads((ROOT / MANIFEST_RELATIVE).read_text())
        value["milestone_id"] = "SYNTHETIC-TAMPERING"
        target.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(CompletenessFirewallError):
        composition(repository=repository)


@pytest.mark.parametrize("mutation", ["missing", "tampered"])
def test_lifecycle_consumer_rejects_missing_or_tampered_source(
    tmp_path: Path,
    mutation: str,
) -> None:
    target = tmp_path / "ENGINEERING_LIFECYCLE.md"
    if mutation == "tampered":
        target.write_bytes((ROOT / LIFECYCLE_RELATIVE).read_bytes() + b"\nSYNTHETIC TAMPER\n")
    with pytest.raises(RuntimeError, match="canonical lifecycle source"):
        assert_lifecycle_projection_conformant(target)


COURT_CHILD = r"""
import importlib.machinery, json, runpy, sys
from pathlib import Path
root, dependencies, pool, workspace = map(Path, sys.argv[1:])
sys.path[:0] = [str(root), str(dependencies)]
local_names = {"kernel", "runtime", "paeos", "ops", "contracts"}
class Fence:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in local_names:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None:
            raise ModuleNotFoundError(fullname)
        for location in ([spec.origin] if spec.origin else []) + list(spec.submodule_search_locations or []):
            assert Path(location).resolve().is_relative_to(root), fullname
        return spec
sys.meta_path.insert(0, Fence())
sys.argv = ["runtime.transports.mcp.court_server", str(pool), str(workspace)]
runpy.run_module("runtime.transports.mcp.court_server", run_name="__main__")
origins = {}
for name, module in tuple(sys.modules.items()):
    if name.split(".")[0] in local_names and getattr(module, "__file__", None):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(root), name
        origins[name] = str(path.relative_to(root))
assert "litellm" not in sys.modules
print(json.dumps({"court_stdio_eof": True, "origins": origins}))
"""


def test_court_server_real_stdio_root_uses_candidate_imports(tmp_path: Path) -> None:
    workspace = tmp_path / "court-workspace"
    workspace.mkdir()
    dependencies = Path(pytest.__file__).resolve().parents[1]
    child = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-S",
            "-c",
            COURT_CHILD,
            str(ROOT),
            str(dependencies),
            str(tmp_path / "court-pool"),
            str(workspace),
        ],
        input="",
        capture_output=True,
        text=True,
        timeout=20,
        cwd=tmp_path,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(tmp_path),
            "TMPDIR": str(tmp_path),
            "PYTHON_DOTENV_DISABLED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    assert child.returncode == 0, child.stderr
    result = json.loads(child.stdout)
    assert result["court_stdio_eof"] is True
    assert result["origins"]["runtime.orchestrator"] == "runtime/orchestrator/__init__.py"
    assert result["origins"]["kernel.capability"] == "kernel/capability.py"
    assert len(result["origins"]) >= 60
    assert (tmp_path / "court-pool").is_dir()
    assert not list((tmp_path / "court-pool").iterdir())
