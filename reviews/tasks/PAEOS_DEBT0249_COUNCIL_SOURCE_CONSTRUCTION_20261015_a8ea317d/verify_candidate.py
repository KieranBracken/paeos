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
if len(args)!=1 or args[0] != 'tests/runtime/test_debt0249_remand14.py':
    raise SystemExit('exact prebound test file required')
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.path.insert(0,str(root))
modules=['kernel.cas','runtime.critique']
origins={}
for name in modules:
    m=importlib.import_module(name); p=Path(m.__file__).resolve()
    if not p.is_relative_to(root): raise SystemExit('wrong candidate import origin: '+name)
    origins[name]=p.relative_to(root).as_posix()
print(json.dumps({'mode':'SOURCE_CONSTRUCTION_ONLY','import_origins':origins,'network':'macOS sandbox-exec deny network'},sort_keys=True))
import pytest
with tempfile.TemporaryDirectory(prefix='paeos-source-verify-') as temp:
    tests=[args[0], 'tests/runtime/test_l09_critique.py']
    code=pytest.main(['-q','-p','no:cacheprovider',*tests,'--basetemp',temp])
raise SystemExit(int(code))
