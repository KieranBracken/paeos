"""Run synthetic Antigravity denial tests with network and non-candidate imports fenced."""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
labels = {
    "red": ["tests/runtime/test_antigravity_disclosure_denial.py"],
    "green": ["tests/runtime/test_antigravity_disclosure_denial.py"],
    "regression": [
        "tests/runtime/test_antigravity_disclosure_denial.py",
        "tests/runtime/test_live_adapter.py::test_live_invoker_denies_before_provider_launch",
    ],
}
label = sys.argv[1]
if label not in labels:
    raise SystemExit("unknown frozen verification label")

python = Path("/Users/bob/GitHub/paeos/.venv/bin/python")
dependencies = Path("/Users/bob/GitHub/paeos/.venv/lib/python3.13/site-packages")
scratch = Path(tempfile.mkdtemp(prefix="paeos-antigravity-denial-")).resolve()
quote = json.dumps
profile = (
    "(version 1)(allow default)(deny network*)"
    '(deny file-read* (subpath "/Users/bob"))'
    "(allow file-read-metadata)"
    f"(allow file-read* (subpath {quote(str(root))}) (subpath {quote(str(dependencies))}) "
    '(subpath "/Users/bob/.local/share/uv/python") '
    '(literal "/Users/bob/GitHub/paeos/.venv/pyvenv.cfg") '
    '(subpath "/Users/bob/GitHub/paeos/.venv/bin"))'
    "(deny file-write*)"
    f'(allow file-write* (subpath {quote(str(scratch))}) (literal "/dev/null"))'
)
bootstrap = """
import importlib.machinery, json, sys
from pathlib import Path
root, dependencies, scratch = map(Path, sys.argv[1:4])
nodes = sys.argv[4:]
sys.path[:0] = [str(root), str(dependencies)]
local_names = {"kernel", "runtime", "paeos", "ops", "contracts", "tests"}
class CandidateFence:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in local_names:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None:
            raise ModuleNotFoundError(fullname)
        locations = ([spec.origin] if spec.origin else []) + list(spec.submodule_search_locations or [])
        for location in locations:
            assert Path(location).resolve().is_relative_to(root), fullname
        return spec
sys.meta_path.insert(0, CandidateFence())
import socket
with socket.socket() as probe:
    try:
        probe.bind(("127.0.0.1", 0))
    except PermissionError:
        print("NETWORK_DENIAL_CONTROL=PASS")
    else:
        raise AssertionError("network-denial profile did not block loopback bind")
import pytest
code = pytest.main(["-c", str(root / "pyproject.toml"), "--confcutdir", str(root), "-o", "addopts=", "-q", "-p", "no:cacheprovider", "--basetemp", str(scratch / "pytest"), *nodes])
origins = {}
for name, module in tuple(sys.modules.items()):
    path = getattr(module, "__file__", None)
    if path is None:
        continue
    resolved = Path(path).resolve()
    if name.split(".")[0] in local_names or name.startswith("test_"):
        assert resolved.is_relative_to(root), name
        origins[name] = str(resolved.relative_to(root))
assert any(path.endswith("runtime/integrations/antigravity.py") for path in origins.values())
assert any(path.endswith("tests/runtime/test_antigravity_disclosure_denial.py") for path in origins.values())
assert not any(name == "google.antigravity" or name.startswith("google.antigravity.") for name in sys.modules)
print("SDK_IMPORT_CONTROL=PASS")
print("LOCAL_ORIGINS=" + json.dumps(origins, sort_keys=True))
raise SystemExit(code)
"""
argv = [
    "/usr/bin/sandbox-exec",
    "-p",
    profile,
    str(python),
    "-I",
    "-B",
    "-S",
    "-c",
    bootstrap,
    str(root),
    str(dependencies),
    str(scratch),
    *labels[label],
]
environment = {
    "PATH": "/usr/bin:/bin",
    "HOME": str(scratch),
    "TMPDIR": str(scratch),
    "TMP": str(scratch),
    "TEMP": str(scratch),
    "XDG_CACHE_HOME": str(scratch / "cache"),
    "PYTHON_DOTENV_DISABLED": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
}
result = subprocess.run(
    argv, cwd=root, env=environment, capture_output=True, text=True, timeout=120
)
stdout_bytes = result.stdout.encode("utf-8")
stderr_bytes = result.stderr.encode("utf-8")
for stream, raw in (("stdout", stdout_bytes), ("stderr", stderr_bytes)):
    (evidence / f"{label}.raw.{stream}.b64").write_text(
        base64.b64encode(raw).decode("ascii") + "\n"
    )
    readable = raw.decode("utf-8", errors="replace")
    normalized = "\n".join(line.rstrip(" \t") for line in readable.splitlines())
    if readable.endswith("\n"):
        normalized += "\n"
    (evidence / f"{label}.{stream}.txt").write_text(normalized)
(evidence / f"{label}.command.json").write_text(
    json.dumps(
        {
            "argv": argv,
            "environment_keys": sorted(environment),
            "exit_code": result.returncode,
            "raw_stdout_sha256": hashlib.sha256(stdout_bytes).hexdigest(),
            "raw_stderr_sha256": hashlib.sha256(stderr_bytes).hexdigest(),
            "readable_log_normalization": "trailing spaces and tabs removed from display copies; exact bytes retained in raw base64 artifacts",
            "scratch_preserved": str(scratch),
        },
        indent=2,
    )
    + "\n"
)
print(result.stdout)
print(result.stderr, file=sys.stderr)
raise SystemExit(result.returncode)
