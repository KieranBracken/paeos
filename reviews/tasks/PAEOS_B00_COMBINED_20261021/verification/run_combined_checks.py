from pathlib import Path
from datetime import datetime, timezone
import fcntl
import subprocess
import tempfile
import json
import time
import hashlib

root = Path('/Users/bob/.codex/worktrees/p1-bound-source-recovery/paeos')
coord = Path('/Users/bob/.codex/paeos-coordination/completion-loop-20261018')
out = coord / 'evidence/bootstrap-integration-20261021'
lock = (coord / 'heavy-test.lock').open('a+')
try:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    raise SystemExit('HELD: shared heavy-test.lock is active; no checks started')
scratch = Path(tempfile.mkdtemp(prefix='paeos-combined-checks-', dir='/private/tmp'))
for name in ['home', 'codex', 'tmp', 'uv-cache']:
    (scratch / name).mkdir()
env = {
    'PATH': '/Users/bob/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
    'HOME': str(scratch / 'home'), 'CODEX_HOME': str(scratch / 'codex'),
    'TMPDIR': str(scratch / 'tmp') + '/', 'UV_CACHE_DIR': str(scratch / 'uv-cache'),
    'UV_NO_SYNC': '1', 'PYTHONPATH': str(root), 'PYTHONDONTWRITEBYTECODE': '1',
    'LANG': 'en_GB.UTF-8', 'TZ': 'Europe/London',
    'RUFF_NO_CACHE': 'true',
}
profile = f'(version 1) (allow default) (deny file-write*) (allow file-write* (subpath "{scratch}")) (allow file-write* (literal "/dev/null")) (deny network*) (allow network-bind (local ip "localhost:*")) (allow network-inbound (local ip "localhost:*")) (allow network-outbound (remote ip "localhost:*"))'
python = root / '.venv/bin/python'
base = 'c6709750a07c823bcb31b0a4d819f9ab84ae1f25'
changed = subprocess.check_output(['/usr/bin/git', '-C', str(root), 'diff', '--name-only', base, '--', '*.py']).decode().splitlines()
source_paths = [p for p in changed if p.split('/')[0] in {'runtime', 'paeos', 'ops', 'tests'}]
assert len(source_paths) == 13, source_paths
snapshot = {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in source_paths}
record = {
    'schema': 'paeos.combined-verification/1',
    'source_commit': subprocess.check_output(['/usr/bin/git', '-C', str(root), 'rev-parse', 'HEAD']).decode().strip(),
    'started_at_utc': datetime.now(timezone.utc).isoformat(),
    'network': 'Inherited Seatbelt: external network denied, explicit localhost loopback only. Filesystem writes restricted to the synthetic scratch root and /dev/null. Isolated child HOME/CODEX_HOME; no provider credentials inherited.',
    'seatbelt_profile_sha256': hashlib.sha256(profile.encode()).hexdigest(),
    'source_files': snapshot, 'checks': [], 'full_suite': 'NOT_STARTED',
    'working_source_delta_sha256': hashlib.sha256(subprocess.check_output(['/usr/bin/git', '-C', str(root), 'diff', base, '--', *source_paths])).hexdigest(),
    'real_cli_capability': 'KNOWN_FAILED: tools=None. real_pinned_cli excluded to avoid repeating the unchanged prohibited probe. No editing capability claimed.',
    'harness_correction': 'Earlier source selection and numeric-host preflight failures are preserved. The first actual combined run used network confinement without the write fence required by the inherited-confinement test; it also found the real missing bundle dependency. The current runner retains that RED record and applies scratch-only write confinement. The owner test is unchanged.',
}

def persist():
    (out / 'COMBINED_VERIFICATION.json').write_text(json.dumps(record, indent=2) + '\n')

def run(name, args, timeout=240):
    log = out / (name + '.txt')
    start = time.monotonic()
    cmd = ['/usr/bin/sandbox-exec', '-p', profile, *map(str, args)]
    check = {'name': name, 'command': list(map(str, args)), 'log': log.name,
             'started_at_utc': datetime.now(timezone.utc).isoformat(), 'state': 'RUNNING'}
    record['checks'].append(check)
    persist()
    print('START', name, flush=True)
    with log.open('wb') as stream:
        try:
            result = subprocess.run(cmd, cwd=root, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
            check['timeout_seconds'] = timeout
    check.update({'state': 'FINISHED', 'exit_code': code, 'seconds': round(time.monotonic() - start, 3),
                  'sha256': hashlib.sha256(log.read_bytes()).hexdigest(), 'bytes': log.stat().st_size})
    persist()
    print('END', name, 'exit', code, 'tail', log.read_text(errors='replace')[-1000:], flush=True)
    return code

persist()
for name, args in [
    ('ruff-check', [python, '-m', 'ruff', 'check', *source_paths]),
    ('ruff-format', [python, '-m', 'ruff', 'format', '--check', *source_paths]),
    ('compile', [python, '-c', 'from pathlib import Path; import sys; [compile(Path(p).read_bytes(),p,"exec") for p in sys.argv[1:]]; print("compiled",len(sys.argv)-1,"files")', *source_paths]),
]:
    if run(name, args):
        record['full_suite'] = 'HELD_STATIC_FAILURE'
        persist()
        raise SystemExit(2)
tests = [
    'tests/runtime/autonomy/test_admission_authority.py', 'tests/runtime/autonomy/test_admission_send_fence.py',
    'tests/kernel/test_ledger.py', 'tests/kernel/test_ledger_sqlite.py',
    'tests/ops/test_autonomous_run_fence_composition.py', 'tests/runtime/test_trusted_codex_worker_transport.py',
    'tests/runtime/test_trusted_codex_client.py', 'tests/runtime/test_mediated_worker_tools.py',
    'tests/runtime/test_worker_confinement_mutations.py', 'tests/runtime/test_confined_codex_cli.py',
    'tests/runtime/test_responses_broker_disclosure_denial.py', 'tests/runtime/test_responses_broker_request_limit.py',
    'tests/runtime/test_responses_broker_model_identity.py', 'tests/runtime/test_disclosure_frame.py',
    'tests/model_router/test_disclosure_policy.py', 'tests/model_router/test_disclosure_store.py',
    'tests/ops/test_trusted_codex_installer_binding.py',
]
if run('focused', [python, '-m', 'pytest', '-p', 'no:cacheprovider', *tests, '-k', 'not real_pinned_cli', '-o', 'addopts=', '-q']):
    record['full_suite'] = 'HELD_FOCUSED_FAILURE'
    persist()
    raise SystemExit(3)
record['full_suite'] = 'ATTEMPTED_ONCE'
persist()
run('full-suite', ['/Users/bob/.local/bin/uv', 'run', '--no-sync', 'pytest', '-p', 'no:cacheprovider', '-k', 'not real_pinned_cli', '-q'], timeout=300)
record['source_files_unchanged_after_checks'] = all(hashlib.sha256((root / p).read_bytes()).hexdigest() == h for p, h in snapshot.items())
record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
persist()
print('RECORD', out / 'COMBINED_VERIFICATION.json', flush=True)
