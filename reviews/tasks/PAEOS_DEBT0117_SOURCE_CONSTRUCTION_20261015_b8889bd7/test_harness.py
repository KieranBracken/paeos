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
    assert scope['source_files']['runtime/autonomy/resume_engine.py']['read_only'] is False
    assert scope['mutable_preimages']['tests/runtime/autonomy/test_resume_checkpoint_admission.py']=='5d332af1352f9018a42811cb77a413446bbef57fa153ff28549694612eab82d5'
    assert scope['source_files']['tests/runtime/autonomy/test_resume_checkpoint_admission.py']['source'].endswith('/captured-candidate/tests/runtime/autonomy/test_resume_checkpoint_admission.py')
    assert len([m for m in scope['source_files'].values() if m['read_only']])==38
    assert not (state/'package.json').exists()
    assert not list(state.glob('bridge/requests/*'))


def test_successor_keeps_production_death_proof_explicitly_deferred():
    scope=json.loads(HARNESS.with_name('scope.json').read_text())
    assert scope['supersedes_failed_source_construction']['reuse_prior_operation'] is False
    assert scope['deferred_verification'][0]['status']=='DEFERRED_FULL_AUTONOMY_PROOF'
    helper=HARNESS.with_name('verify_candidate.py').read_text()
    assert 'test_scenario_14_physical_controller_death_acceptance_test' not in helper
    assert 'test_scenario_13_lawful_ceremony_depth_selection_in_nested_branch' in helper
    assert 'test_scenario_01_one_level_remediation_and_autoresume' in helper


def test_missing_explicit_read_dependency_refuses_without_snapshot(tmp_path):
    state=tmp_path/'state'
    assert call('init','--state',state,'--source-root',REPO).returncode==0
    scope=json.loads(HARNESS.with_name('scope.json').read_text())
    scope['read_file_pins'].append({'path':'runtime/definitely_absent_source_harness_dependency.py','sha256':'0'*64})
    source=tmp_path/'scope.json'; source.write_text(json.dumps(scope))
    result=call('bind','--state',state,'--scope',source)
    assert result.returncode!=0
    assert 'explicit pinned dependencies are missing' in result.stderr
    assert not (state/'snapshot').exists()
    assert not (state/'package.json').exists()
