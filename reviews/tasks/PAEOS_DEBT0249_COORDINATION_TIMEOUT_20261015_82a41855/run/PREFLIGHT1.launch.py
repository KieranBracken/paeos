import hashlib
import json
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parent
p = json.loads((root / 'PREPARED.json').read_text())
source = Path(p['source'])
state = Path(p['state'])
assert not state.exists(), 'Fresh state required'
assert not (root / 'RUN.intent.json').exists(), 'Attempt already started'
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
assert sha(root / 'intake.json') == p['intake_sha256']
for entry in json.loads((root / 'RUN_SOURCE_MANIFEST.json').read_text())['files']:
    assert sha(source / entry['path']) == entry['sha256'], entry['path']
code = 'import pathlib,sys\nsource=pathlib.Path(sys.argv[1]);sys.path.insert(0,str(source))\nfrom runtime.ceremony import assert_lifecycle_contract_is_current\nassert_lifecycle_contract_is_current(source / "operations/ENGINEERING_LIFECYCLE.md")\nfrom ops.autonomous_run import main\nraise SystemExit(main(sys.argv[2:]))\n'
argv = ['/Users/bob/GitHub/paeos/.venv/bin/python', '-I', '-B', '-c', code,
        str(source), p['intake'], str(state), '1', '1', 'chat-bridge']
receipt = dict(p, status='REAL_SUCCESSOR_STARTED', argv=argv, cwd=str(source), started_unix=time.time())
(root / 'RUN.intent.json').write_text(json.dumps(receipt, indent=2) + '\n')
with (root / 'RUN.stdout.txt').open('wb') as stdout, (root / 'RUN.stderr.txt').open('wb') as stderr:
    process = subprocess.Popen(argv, cwd=source, stdout=stdout, stderr=stderr)
    (root / 'RUN.pid.json').write_text(json.dumps({'pid':process.pid,'started_unix':receipt['started_unix']})+'\n')
    print(json.dumps({'pid':process.pid,'root':str(root),'state':str(state)}),flush=True)
    code = process.wait()
receipt.update(status='REAL_SUCCESSOR_TERMINATED', exit_code=code, ended_unix=time.time(),
    stdout_sha256=sha(root / 'RUN.stdout.txt'), stderr_sha256=sha(root / 'RUN.stderr.txt'))
(root / 'RUN.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'exit_code':code,'receipt':str(root/'RUN.receipt.json')}),flush=True)
