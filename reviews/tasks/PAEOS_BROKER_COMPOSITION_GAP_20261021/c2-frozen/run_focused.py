import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

out = Path(__file__).resolve().parent
root = Path('/Users/bob/.codex/worktrees/debt0261-slice1/paeos')
python = '/Users/bob/GitHub/paeos/.venv/bin/python'
phase = sys.argv[1]
assert phase in ('red', 'green', 'corrective')
record_path = out / (phase + '.json')
if record_path.exists():
    raise SystemExit('Phase already consumed; no duplicate run')
tmp = out / ('tmp-' + phase)
tmp.mkdir(exist_ok=False)
child = '''import os, pathlib, sys
allowed = pathlib.Path(sys.argv[1]).resolve()
def guard(event, args):
    if event in {"socket.connect", "socket.bind", "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork"}:
        raise RuntimeError("OFFLINE_EFFECT_DENIED: " + event)
    if event == "open":
        path, mode, flags = args
        if isinstance(path, (str, bytes, os.PathLike)) and ((isinstance(mode,str) and any(c in mode for c in "wax+")) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))):
            resolved = pathlib.Path(os.fsdecode(path)).resolve()
            if resolved != pathlib.Path('/dev/null') and not resolved.is_relative_to(allowed):
                raise RuntimeError("OFFLINE_WRITE_DENIED: " + str(resolved))
sys.addaudithook(guard)
import pytest
result = pytest.main(sys.argv[2:])
for name in ('runtime.scheduler','runtime.orchestrator','kernel.types'):
    module = sys.modules.get(name)
    print('IMPORTED_SOURCE',name,getattr(module,'__file__',None))
sys.exit(result)
'''
args = [python, '-B', '-c', child, str(tmp), '-q', '-p', 'no:cacheprovider', '--noconftest', 'tests/runtime/test_scheduler.py']
if phase == 'red':
    args += ['-k', 'default_scheduler_holds_before_budget_and_invocation']
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONPATH=str(root), TMPDIR=str(tmp))
meta = {'phase':phase,'command':args,'cwd':str(root),'env_overrides':{k:env[k] for k in ['PYTHONDONTWRITEBYTECODE','PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONPATH','TMPDIR']},'source_sha256':{name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ['runtime/scheduler.py','tests/runtime/test_scheduler.py']}}
with (out.parent.parent/'heavy-test.lock').open('a') as lock:
    try:
        fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit('HEAVY_TEST_LOCK_BUSY; no test started')
    meta['state']='STARTED'
    record_path.write_text(json.dumps(meta,indent=2)+'\n')
    start=time.monotonic()
    try:
        result=subprocess.run(args,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=60)
        output=result.stdout; meta['exit_code']=result.returncode
    except subprocess.TimeoutExpired as exc:
        output=str(exc.stdout); meta['exit_code']='TIMEOUT'
    meta['seconds']=round(time.monotonic()-start,3)
    meta['state']='FINISHED'
    (out/(phase+'.log')).write_text(output)
    record_path.write_text(json.dumps(meta,indent=2)+'\n')
print(output)
print('EXIT',meta['exit_code'])
sys.exit(meta['exit_code'] if isinstance(meta['exit_code'],int) else 1)
