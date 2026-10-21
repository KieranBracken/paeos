from pathlib import Path
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
import time

root=Path('/Users/bob/.codex/worktrees/p1-bound-source-recovery/paeos')
coord=Path('/Users/bob/.codex/paeos-coordination/completion-loop-20261018')
out=coord/'evidence/transport-boundary-source-20261021'
phase=sys.argv[1]
assert phase in {'red','green','corrective','collect'}
cp=out/'COUNTERS.json'
counts=json.loads(cp.read_text()) if cp.exists() else dict(red=0,green=0,corrective=0,collect=0)
assert counts[phase]==0,'Phase reserved already; reconcile result, do not retry'
lock=(coord/'heavy-test.lock').open('a+')
try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('HELD_HEAVY_TEST_LOCK; no allowance consumed')
if phase=='collect':
 assert json.loads((out/'COLLECTION_PREFLIGHT.json').read_text())['permitted_collect_only'] is True
counts[phase]+=1
cp.write_text(json.dumps(counts,indent=2)+'\n')
scratch=Path(tempfile.mkdtemp(prefix='paeos-transport-boundary-',dir='/private/tmp'))
for p in ['home','codex','tmp']:(scratch/p).mkdir()
profile=f'(version 1) (allow default) (deny network*) (deny file-write*) (allow file-write* (subpath "{scratch}")) (allow file-write* (literal "/dev/null")) (deny file-read* (literal "/Users/bob/.codex/auth.json") (literal "/Users/bob/.codex/config.toml") (subpath "/Users/bob/.ssh") (subpath "/Users/bob/Library/Keychains") (subpath "/Volumes/PAEOS_KEYS") (subpath "/Users/bob/GitHub/paeos/ops/keys"))'
env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(scratch/'home'),'CODEX_HOME':str(scratch/'codex'),'TMPDIR':str(scratch/'tmp')+'/', 'PYTHONPATH':str(root),'PYTHONDONTWRITEBYTECODE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','LANG':'C.UTF-8'}
tests=['tests/runtime/test_transport_boundary_restoration.py']
options=[]
if phase=='red':tests=[tests[0]+'::test_missing_boundary_exports_runtime_checkable_protocol']
if phase=='collect':
 tests=['tests/runtime/test_transport.py','tests/runtime/test_claude_cli_transport.py','tests/runtime/test_mcp_transport.py'];options=['--collect-only']
cmd=[str(root/'.venv/bin/python'),'-m','pytest','-p','no:cacheprovider',*tests,*options,'-o','addopts=','-q']
paths=['runtime/transport.py','tests/runtime/test_transport_boundary_restoration.py']
record={'phase':phase,'state':'RESERVED','started_at_utc':datetime.now(timezone.utc).isoformat(),'command':cmd,'environment':'Isolated HOME/CODEX_HOME/TMPDIR; no credentials; plugin autoload disabled','network':'DENY_ALL','filesystem':'Scratch writes only; known host credentials/USB reads denied','profile_sha256':hashlib.sha256(profile.encode()).hexdigest(),'source_hashes':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() if (root/p).exists() else 'ABSENT' for p in paths}}
receipt=out/(phase+'.json');receipt.write_text(json.dumps(record,indent=2)+'\n')
start=time.monotonic()
with (out/(phase+'.txt')).open('wb') as stream:
 process=subprocess.run(['/usr/bin/sandbox-exec','-p',profile,*cmd],cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
record.update(state='RETURNED',exit_code=process.returncode,seconds=round(time.monotonic()-start,3),stdout_sha256=hashlib.sha256((out/(phase+'.txt')).read_bytes()).hexdigest())
receipt.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2));print((out/(phase+'.txt')).read_text()[-3400:])
raise SystemExit(0 if phase=='red' and process.returncode==1 or phase in {'green','corrective'} and process.returncode==0 or phase=='collect' else 1)
