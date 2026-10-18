"""Run only the frozen offline tests with host home/state and network denied."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
label = sys.argv[1]
if not label.replace("-", "").isalnum():
    raise SystemExit("invalid evidence label")
python = Path("/Users/bob/GitHub/paeos/.venv/bin/python")
dependencies = Path("/Users/bob/GitHub/paeos/.venv/lib/python3.13/site-packages")
scratch = Path(tempfile.mkdtemp(prefix="paeos-offline-readiness-")).resolve()
q = json.dumps
profile = (
    '''(version 1)(allow default)(deny network*)(allow network-inbound (local ip "localhost:*"))(allow network-outbound (remote ip "localhost:*"))(allow network-bind (local ip "localhost:*"))'''
    '(deny file-read* (subpath "/Users/bob"))'
    "(allow file-read-metadata)"
    f"(allow file-read* (subpath {q(str(root))}) (subpath {q(str(dependencies))}) "
    '(subpath "/Users/bob/.local/share/uv/python") '
    '(literal "/Users/bob/GitHub/paeos/.venv/pyvenv.cfg") '
    '(subpath "/Users/bob/GitHub/paeos/.venv/bin"))'
    "(deny file-write*)"
    f'(allow file-write* (subpath {q(str(scratch))}) (literal "/dev/null"))'
)
bootstrap = """
import importlib.machinery, json, sys
from pathlib import Path
root, dependencies, scratch = map(Path, sys.argv[1:])
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
import pytest
code = pytest.main(["-c", str(root / "pyproject.toml"), "--confcutdir", str(root), "-o", "addopts=", "-q", "--tb=short", "-p", "no:cacheprovider", "--basetemp", str(scratch / "pytest"), "tests/runtime/test_responses_broker_model_identity.py", "tests/runtime/test_responses_broker_request_limit.py", "tests/runtime/test_trusted_codex_worker_transport.py", "tests/runtime/test_responses_broker_disclosure_denial.py"])
origins = {}
for name, module in tuple(sys.modules.items()):
    if name.split(".")[0] in local_names and getattr(module, "__file__", None):
        path = Path(module.__file__).resolve()
        assert path.is_relative_to(root), name
        origins[name] = str(path.relative_to(root))
assert "litellm" not in sys.modules
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
result = subprocess.run(argv, cwd=root, env=environment, capture_output=True, text=True, timeout=90)
for suffix, value in (("stdout.txt", result.stdout), ("stderr.txt", result.stderr)):
    with (evidence / f"{label}.{suffix}").open("x") as stream:
        stream.write(value)
with (evidence / f"{label}.command.json").open("x") as stream:
    json.dump(
        {
            "argv": argv,
            "environment": environment,
            "exit_code": result.returncode,
            "scratch_preserved": str(scratch),
        },
        stream,
        indent=2,
    )
print(result.stdout)
print(result.stderr, file=sys.stderr)
raise SystemExit(result.returncode)
