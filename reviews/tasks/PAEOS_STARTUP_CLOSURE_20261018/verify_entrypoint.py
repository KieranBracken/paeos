"""No-input entrypoint probe: no site hooks, host reads, writes, or network."""

from __future__ import annotations

import importlib.machinery
import json
import os
import runpy
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve(strict=True)
dependencies = Path(sys.argv[2]).resolve(strict=True)
stdlib = [Path(p).resolve() for p in sys.path if p]
sys.path.insert(0, str(dependencies))
sys.path.insert(0, str(root))
local_names = {"kernel", "runtime", "paeos", "ops", "contracts"}
effects: list[str] = []
effect_stacks = {}
blocked_socket_binds = 0


def record_effect(event):
    effects.append(event)
    if event not in effect_stacks:
        frames = []
        frame = sys._getframe(1)
        while frame and len(frames) < 12:
            frames.append([frame.f_code.co_filename, frame.f_lineno, frame.f_code.co_name])
            frame = frame.f_back
        effect_stacks[event] = frames


def contained(path: Path, directory: Path) -> bool:
    return path == directory or directory in path.parents


class LocalSourceFence:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split(".")[0] not in local_names:
            return None
        spec = importlib.machinery.PathFinder.find_spec(fullname, path)
        if spec is None:
            raise ModuleNotFoundError(f"candidate-local module missing: {fullname}")
        locations = ([spec.origin] if spec.origin else []) + list(
            spec.submodule_search_locations or []
        )
        for location in locations:
            if not contained(Path(location).resolve(), root):
                raise ImportError(f"candidate source escape: {fullname}")
        return spec


def audit(event, args):
    global blocked_socket_binds
    if event == "open":
        path, _mode, flags = args
        if isinstance(path, int):
            return
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            record_effect("file_write")
            raise PermissionError("entrypoint probe forbids writes")
        resolved = Path(path).resolve()
        system_metadata = Path("/System/Library/CoreServices/SystemVersion.plist")
        if resolved != system_metadata and not any(
            contained(resolved, base) for base in [root, dependencies, *stdlib]
        ):
            record_effect("outside_read")
            raise PermissionError("entrypoint probe forbids outside reads")
    if event == "socket.__new__":
        return  # Creating a socket object does not send data.
    if event == "socket.bind":
        blocked_socket_binds += 1
        raise PermissionError("entrypoint probe forbids socket binds")
    if event.startswith("socket.") or event in {
        "subprocess.Popen",
        "os.system",
        "os.posix_spawn",
        "os.exec",
        "os.mkdir",
        "os.remove",
        "os.rmdir",
        "os.rename",
        "os.symlink",
        "os.link",
        "os.chmod",
        "os.chown",
        "os.truncate",
    }:
        record_effect(event)
        raise PermissionError("entrypoint probe forbids effects")


sys.meta_path.insert(0, LocalSourceFence())
sys.addaudithook(audit)
sys.argv = [str(root / "ops/autonomous_run.py")]
error = None
try:
    runpy.run_path(sys.argv[0], run_name="__main__")
    entrypoint_exit = 0
except SystemExit as exc:
    entrypoint_exit = exc.code
except Exception as exc:
    entrypoint_exit = None
    error = f"{type(exc).__name__}: {exc}"

origins = {}
for name, module in tuple(sys.modules.items()):
    if name.split(".")[0] in local_names:
        path = getattr(module, "__file__", None)
        if path:
            resolved = Path(path).resolve()
            assert contained(resolved, root), name
            origins[name] = str(resolved.relative_to(root))
passed = entrypoint_exit == 64 and error is None and not effects
print(
    json.dumps(
        {
            "status": "PASS" if passed else "FAIL",
            "entrypoint_exit": entrypoint_exit,
            "error": error,
            "effects_attempted": effects,
            "effect_stacks": effect_stacks,
            "blocked_socket_binds": blocked_socket_binds,
            "local_module_count": len(origins),
            "local_module_origins": origins,
            "scope": "IMPORT_AND_NO_ARGUMENT_USAGE_ONLY",
        },
        sort_keys=True,
    )
)
raise SystemExit(0 if passed else 1)
