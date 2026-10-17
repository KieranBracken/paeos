import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HARNESS = Path(__file__).with_name('harness.py')
REPO = Path('/Users/bob/GitHub/paeos')

def call(*args):
    return subprocess.run([sys.executable, '-B', str(HARNESS), *map(str,args)], capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})

def test_init_is_fresh_and_has_no_worker_effect(tmp_path):
    state = tmp_path / 'state'
    r = call('init', '--state', state, '--source-root', REPO)
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data['mode'] == 'SOURCE_CONSTRUCTION_ONLY'
    assert data['worker_dispatches'] == 0
    assert (state/'kernel.key').stat().st_mode & 0o777 == 0o600
    assert not (state/'package.json').exists()
    assert not list(state.glob('bridge/requests/*'))
    import sqlite3
    with sqlite3.connect(state/'ledger.sqlite') as db:
        assert db.execute('select count(*) from ledger_rows').fetchone()[0] == 1
        assert db.execute('select domain_tag from ledger_rows').fetchone()[0] == 'RECOVERY'
    assert call('init','--state',state,'--source-root',REPO).returncode != 0

def test_dispatch_without_bound_scope_fails_before_prompt(tmp_path):
    state = tmp_path / 'state'
    assert call('init','--state',state,'--source-root',REPO).returncode == 0
    r = call('dispatch','--state',state,'--scope-sha256','0'*64)
    assert r.returncode != 0
    assert not (state/'dispatch.started.json').exists()
    assert not (state/'package.json').exists()
    assert not list(state.glob('bridge/requests/*'))

def test_path_and_scope_validation_without_dispatch():
    spec = importlib.util.spec_from_file_location('source_harness',HARNESS)
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    import pytest
    for bad in ('../x.py','/tmp/x.py','a/../x.py','ops/keys/key.py','.env','runtime/*.py'):
        with pytest.raises(ValueError):
            h.safe_relative(bad)
    assert h.safe_relative('runtime/scope_supersession.py') == 'runtime/scope_supersession.py'
    with pytest.raises(ValueError):
        h.validate_scope({'mode':'SOURCE_CONSTRUCTION_ONLY','write_files':['runtime/a.py']})


def test_real_typed_capability_can_be_recorded_in_recovery_ledger(tmp_path):
    state=tmp_path/'state'
    assert call('init','--state',state,'--source-root',REPO).returncode == 0
    spec=importlib.util.spec_from_file_location('source_harness_record',HARNESS)
    h=importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
    from kernel.types import Role, StageId
    cas,broker=h.components(state)
    token=broker.mint(goal_id='test-g',run_id='test-r',stage=StageId.IMPLEMENT,role=Role.BUILDER,session='test-session',operations=('mcp:court:submit_evidence',),issued_seq=1,expires_seq=2)
    from runtime.task_package import Permissions
    payload={'mode':h.MODE,'goal_id':'test-g','run_id':'test-r','task_id':'test-t','builder_session':'test-session','builder_family':'openai','deadline_unix':123.0,'capability':token,'permissions':Permissions(('runtime/a.py',),('kernel/types.py',),('court:submit_evidence',))}
    h.once(state/'package.json',payload)
    digest=h.record(state,'SOURCE_CONSTRUCTION_PACKAGE_DISPATCHED',payload)
    assert h.read_json(state/'package.json')['permissions']['write_scopes']==['runtime/a.py']
    assert len(digest)==64
    assert not list(state.glob('bridge/requests/*'))


def test_bound_existing_preimage_and_pinned_read_closure(tmp_path):
    state=tmp_path/'state'
    assert call('init','--state',state,'--source-root',REPO).returncode == 0
    r=call('bind','--state',state,'--scope',HARNESS.with_name('scope.json'))
    assert r.returncode==0,r.stderr
    scope=json.loads((state/'scope.json').read_text())
    assert scope['source_files']['runtime/critique.py']['read_only'] is False
    assert scope['mutable_preimages']['tests/runtime/test_debt0249_remand14.py'] is None
    assert len([m for m in scope['source_files'].values() if m['read_only']])==9
    assert not (state/'package.json').exists()
    assert not list(state.glob('bridge/requests/*'))
