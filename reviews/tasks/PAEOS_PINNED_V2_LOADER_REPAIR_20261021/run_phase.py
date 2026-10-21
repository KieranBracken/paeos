from pathlib import Path
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
import time

root = Path('/Users/bob/.codex/worktrees/p1-bound-source-recovery/paeos')
coord = Path('/Users/bob/.codex/paeos-coordination/completion-loop-20261018')
out = coord / 'evidence/pinned-v2-loader-repair-20261021'
phase = sys.argv[1]
assert phase in {'red', 'green', 'corrective'}
counts_path = out / 'COUNTERS.json'
counts = json.loads(counts_path.read_text()) if counts_path.exists() else dict(red=0, green=0, corrective=0)
assert counts[phase] == 0, 'Phase allowance already reserved; reconcile existing result instead of retrying'
lock = (coord / 'heavy-test.lock').open('a+')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('HELD_HEAVY_TEST_LOCK: no phase reserved or executed')
counts[phase] += 1
counts_path.write_text(json.dumps(counts, indent=2) + '\n')
scratch = Path(tempfile.mkdtemp(prefix='paeos-v2-loader-test-', dir='/private/tmp'))
for name in ('home', 'codex', 'tmp'):
    (scratch / name).mkdir()
profile = f'(version 1) (allow default) (deny file-write*) (allow file-write* (subpath "{scratch}")) (allow file-write* (literal "/dev/null")) (deny network*) (deny file-read* (literal "/Users/bob/.codex/auth.json") (literal "/Users/bob/.codex/config.toml") (subpath "/Users/bob/.ssh") (subpath "/Users/bob/Library/Keychains") (subpath "/Volumes/PAEOS_KEYS") (subpath "/Users/bob/GitHub/paeos/ops/keys"))'
env = {
    'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(scratch / 'home'),
    'CODEX_HOME': str(scratch / 'codex'), 'TMPDIR': str(scratch / 'tmp') + '/',
    'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1', 'LANG': 'C.UTF-8',
}
tests = ['tests/model_router/test_disclosure_store.py', 'tests/model_router/test_disclosure_policy.py']
if phase == 'red':
    tests = ['tests/model_router/test_disclosure_store.py::test_explicit_v2_loads_signed_derivative_snapshot_without_authority']
command = [str(root / '.venv/bin/python'), '-m', 'pytest', '-p', 'no:cacheprovider', *tests, '-o', 'addopts=', '-q']
record = {'phase': phase, 'command': command, 'state': 'RESERVED',
          'started_at_utc': datetime.now(timezone.utc).isoformat(),
          'profile_sha256': hashlib.sha256(profile.encode()).hexdigest(),
          'network': 'DENY_ALL', 'filesystem': 'SCRATCH_WRITES_ONLY; known host key/auth paths denied',
          'environment': 'Isolated HOME/CODEX_HOME/TMPDIR; no provider credentials inherited',
          'source_hashes': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in (
              'paeos/model_router/disclosure_store.py', 'tests/model_router/test_disclosure_store.py')}}
receipt = out / (phase + '.json')
receipt.write_text(json.dumps(record, indent=2) + '\n')
start = time.monotonic()
with (out / (phase + '.txt')).open('wb') as stream:
    process = subprocess.run(['/usr/bin/sandbox-exec', '-p', profile, *command], cwd=root,
                             env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=120)
record.update(state='RETURNED', exit_code=process.returncode, seconds=round(time.monotonic() - start, 3))
record['stdout_sha256'] = hashlib.sha256((out / (phase + '.txt')).read_bytes()).hexdigest()
receipt.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
print((out / (phase + '.txt')).read_text()[-1900:])
raise SystemExit(0 if (process.returncode == 1 if phase == 'red' else process.returncode == 0) else 1)
