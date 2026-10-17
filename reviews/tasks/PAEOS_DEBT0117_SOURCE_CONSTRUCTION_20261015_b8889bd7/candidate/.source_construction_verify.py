"""Frozen local verification apparatus; never imports candidate into the controller."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile

root=Path(__file__).resolve().parent
if '--network-confined' not in sys.argv:
    os.execv('/usr/bin/sandbox-exec',['/usr/bin/sandbox-exec','-p','(version 1)(allow default)(deny network*)',sys.executable,'-I','-B',str(Path(__file__).resolve()),'--network-confined',*sys.argv[1:]])
args=[a for a in sys.argv[1:] if a!='--network-confined']
if len(args)!=1 or args[0] not in ('tests/runtime/test_scope_supersession.py','tests/runtime/autonomy/test_resume_checkpoint_admission.py'):
    raise SystemExit('exact prebound test file required')
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.path.insert(0,str(root))
modules=['kernel.ledger','kernel.ledger_sqlite','kernel.cas','kernel.types']
modules += ['runtime.scope_supersession','runtime.implementation_contract','kernel.capability'] if 'scope_supersession' in args[0] else ['runtime.autonomy.resume_engine']
origins={}
for name in modules:
    m=importlib.import_module(name); p=Path(m.__file__).resolve()
    if not p.is_relative_to(root): raise SystemExit('wrong candidate import origin: '+name)
    origins[name]=p.relative_to(root).as_posix()
print(json.dumps({'mode':'SOURCE_CONSTRUCTION_ONLY','import_origins':origins,'network':'macOS sandbox-exec deny network','deferred_verification':{'scenario14':'DEFERRED_FULL_AUTONOMY_PROOF','qualification':False}},sort_keys=True))
import pytest
with tempfile.TemporaryDirectory(prefix='paeos-source-verify-') as temp:
    tests=[args[0]]
    if args[0]=='tests/runtime/autonomy/test_resume_checkpoint_admission.py': tests.extend('tests/runtime/autonomy/test_pre_p2_qualification_scenarios.py::'+name for name in ['test_scenario_01_one_level_remediation_and_autoresume', 'test_scenario_02_nested_remediation_unwind_5_levels', 'test_scenario_03_restart_while_deepest_child_active', 'test_scenario_04_exact_once_resume_under_replay', 'test_scenario_05_multiple_sibling_blockers', 'test_scenario_06_autonomous_recovery_from_child_failure', 'test_scenario_07_nonblocking_finding_isolation', 'test_scenario_08_deterministic_cycle_rejection', 'test_scenario_09_orphan_detection_and_reconciliation', 'test_scenario_10_interrupted_resume_recovery', 'test_scenario_11_root_envelope_authority_confinement', 'test_scenario_12_full_blocking_chain_observability', 'test_scenario_13_lawful_ceremony_depth_selection_in_nested_branch'])
    code=pytest.main(['-q','-p','no:cacheprovider',*tests,'--basetemp',temp])
raise SystemExit(int(code))
