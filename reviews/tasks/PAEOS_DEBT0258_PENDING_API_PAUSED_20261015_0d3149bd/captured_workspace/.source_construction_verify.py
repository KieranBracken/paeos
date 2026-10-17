"""Source-only physical tests; imports must stay inside the declared snapshot."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
root = Path(__file__).resolve().parent
args = [a for a in sys.argv[1:] if a != '--network-confined']
if args != ['tests/runtime/test_scope_supersession.py']:
    raise SystemExit('exact frozen test file required')
if '--network-confined' not in sys.argv:
    os.execv('/usr/bin/sandbox-exec', ['/usr/bin/sandbox-exec', '-p', '(version 1)(allow default)(deny network*)', sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--network-confined', *args])
os.chdir(root)
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
sys.path.insert(0, str(root))
def check_origins():
    origins = {}
    for name, module in tuple(sys.modules.items()):
        if name == 'contracts' or name.startswith('contracts.') or name == 'paeos.model_router' or name.startswith('paeos.model_router.'):
            raise RuntimeError('undeclared ORCA/router dependency: ' + name)
        if name.split('.')[0] not in ('kernel', 'runtime', 'tests', 'paeos'):
            continue
        origin = getattr(module, '__file__', None)
        if origin and not Path(origin).resolve().is_relative_to(root):
            raise RuntimeError('candidate import escaped snapshot: ' + name)
        for package_path in getattr(module, '__path__', ()):
            if not Path(package_path).resolve().is_relative_to(root):
                raise RuntimeError('candidate package escaped snapshot: ' + name)
        if origin:
            origins[name] = Path(origin).resolve().relative_to(root).as_posix()
    return origins
for name in ('kernel.ledger', 'kernel.ledger_sqlite', 'kernel.capability', 'kernel.cas', 'kernel.types', 'runtime.scope_supersession', 'runtime.implementation_contract'):
    importlib.import_module(name)
print(json.dumps({'mode': 'SOURCE_CONSTRUCTION_ONLY', 'import_origins': check_origins(), 'network': 'macOS sandbox-exec deny network'}, sort_keys=True))
import pytest
with tempfile.TemporaryDirectory(prefix='paeos-pending-contract-tests-') as temp:
    code = pytest.main(['-q', '-p', 'no:cacheprovider', args[0], '--basetemp', temp])
check_origins()
raise SystemExit(int(code))
