#!/usr/bin/env python3
"""Isolated manual bootstrap apparatus. Never a production lifecycle or qualification."""
from __future__ import annotations
import argparse
import ast
import copy
import asyncio
import dataclasses
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import time
import uuid

MODE = 'SOURCE_CONSTRUCTION_ONLY'
WRITES = ('runtime/scope_supersession.py', 'tests/runtime/test_scope_supersession.py')
APPARATUS = Path(__file__).resolve().parent
CAPTURED_SOURCE = Path('/Users/bob/GitHub/paeos/reviews/tasks/PAEOS_DEBT0258_SOURCE_CONSTRUCTION_20261015_db28d1ca/candidate')
REPO = Path('/Users/bob/GitHub/paeos')
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO))

def encoded(value):
    def default(v):
        if dataclasses.is_dataclass(v): return dataclasses.asdict(v)
        if isinstance(v, Enum): return v.value
        if isinstance(v, Path): return str(v)
        raise TypeError(type(v).__name__)
    return (json.dumps(value, sort_keys=True, indent=2, default=default)+'\n').encode()

def sha(data): return hashlib.sha256(data).hexdigest()
def read_json(path): return json.loads(Path(path).read_text())
def once(path, value):
    from runtime.integrations.bridge_protocol import write_once_bytes
    write_once_bytes(Path(path), encoded(value))

def safe_relative(raw):
    if not isinstance(raw,str) or not raw or raw != str(PurePosixPath(raw)):
        raise ValueError('noncanonical relative path')
    p = PurePosixPath(raw)
    if p.is_absolute() or any(x in ('..','.') for x in p.parts) or any(x in raw for x in '*?[]\\'):
        raise ValueError('path traversal, absolute paths and globs are forbidden')
    if (p.parts[0] in ('ops','.git','.venv','state','.paeos_state') and raw != 'ops/manifests/p1_authoritative_completeness_manifest.json') or any(x.startswith('.env') for x in p.parts):
        raise ValueError('private/state path is forbidden')
    return raw

def checked_file(root, rel):
    path = root/safe_relative(rel)
    if path != path.resolve(strict=True) or not path.is_file():
        raise ValueError(f'not a regular non-symlink file: {rel}')
    return path

def components(state):
    from kernel.cas import CAS, FilesystemCasStore
    from kernel.keystore import load_or_create_signing_key
    from kernel.capability import CapabilityBroker
    if not (state/'kernel.key').is_file(): raise ValueError('isolated key missing; will not regenerate')
    return CAS(FilesystemCasStore(state/'cas')), CapabilityBroker(load_or_create_signing_key(state/'kernel.key'))

def record(state, kind, payload):
    from kernel.ledger import Event, Ledger
    from kernel.ledger_sqlite import SqliteLedgerStore
    with Ledger(SqliteLedgerStore(state/'ledger.sqlite'),writer_id='source-construction-'+str(os.getpid())) as ledger:
        ledger.verify_chain()
        ledger.append(Event(1,kind,json.loads(encoded({'mode':MODE,**payload}))),domain_tag='RECOVERY')
        return ledger.head_hash()

def initialized(state):
    data=read_json(state/'initialization.json')
    if data['mode'] != MODE or data['state_root'] != str(state): raise ValueError('wrong state identity')
    if data['harness_sha256'] != sha(Path(__file__).read_bytes()): raise ValueError('harness changed after initialization')
    return data

def source_inputs(scope):
    if scope.get('input_manifest') != 'input_manifest.json':
        raise ValueError('exact input manifest path required')
    path = checked_file(APPARATUS, 'input_manifest.json')
    if sha(path.read_bytes()) != scope.get('input_manifest_sha256'):
        raise ValueError('input manifest pin mismatch')
    manifest = read_json(path)
    if manifest.get('source_root') != str(CAPTURED_SOURCE) or set(manifest['preimages']) != set(WRITES):
        raise ValueError('captured source identity/preimage mismatch')
    if scope.get('expected_preimages') != manifest['preimages']:
        raise ValueError('exact existing-file preimages required')
    if scope.get('excluded_from_declared_read_closure') != manifest['excluded_from_declared_read_closure']:
        raise ValueError('declared read closure exclusions changed')
    if set(manifest['declared_candidate_paths']) != set(manifest['files']) - set(manifest['excluded_from_declared_read_closure']):
        raise ValueError('declared source file set mismatch')
    if sha((CAPTURED_SOURCE.parent / 'MANIFEST.json').read_bytes()) != manifest['handoff_manifest_sha256'] or sha((CAPTURED_SOURCE.parent / 'STATUS.json').read_bytes()) != manifest['handoff_status_sha256']:
        raise ValueError('durable handoff metadata changed')
    for rel, item in manifest['files'].items():
        safe_relative(rel)
        data = checked_file(APPARATUS / 'archival_snapshot', rel).read_bytes()
        if sha(data) != item['sha256'] or len(data) != item['size']:
            raise ValueError('archival source mismatch: ' + rel)
        if sha(checked_file(CAPTURED_SOURCE, rel).read_bytes()) != item['sha256']:
            raise ValueError('durable captured source changed: ' + rel)
    observed = {p.relative_to(APPARATUS / 'archival_snapshot').as_posix() for p in (APPARATUS / 'archival_snapshot').rglob('*') if p.is_file()}
    if observed != set(manifest['files']):
        raise ValueError('archival file set mismatch')
    forbidden = {'sentium', 'credentials.py', '.env', '.env.local', 'api_keys.json'}
    for rel in manifest['declared_candidate_paths']:
        if any(part.casefold() in forbidden or part.casefold().startswith('sentium') for part in Path(rel).parts):
            raise ValueError('canonical seeder would quarantine declared dependency: ' + rel)
    cp = checked_file(APPARATUS, 'canonical_runtime_manifest.json')
    if sha(cp.read_bytes()) != scope.get('canonical_runtime_manifest_sha256'):
        raise ValueError('controller-runtime manifest mismatch')
    canonical = read_json(cp)
    if canonical.get('root') != str(REPO):
        raise ValueError('controller root changed')
    for rel, item in canonical['files'].items():
        if sha(checked_file(REPO, rel).read_bytes()) != item['sha256']:
            raise ValueError('canonical machinery changed: ' + rel)
    return manifest

def validate_scope(scope, *, require_review=True):
    if scope.get('mode') != MODE or tuple(scope.get('write_files', ())) != WRITES:
        raise ValueError('exact two-existing-file source-only scope required')
    if scope.get('construction_kind') != 'READ_ONLY_PENDING_DENIAL_API_NO_ACTIVATION':
        raise ValueError('scope construction kind changed')
    if scope.get('claims') != {'production': False, 'admission': False, 'qualification': False, 'integration': False, 'activation': False, 'authority_issuance': False}:
        raise ValueError('source-only claims changed')
    if scope.get('heterogeneous_review') != 'PENDING_NOT_FOR_INTEGRATION' or scope.get('provider_attempts_permitted') is not False:
        raise ValueError('review hold/provider-attempt boundary changed')
    if scope.get('timeout_seconds') != 1800:
        raise ValueError('fixed source construction deadline required')
    for field in ('scope_id', 'objective', 'authority_reference'):
        if not isinstance(scope.get(field), str) or not scope[field].strip():
            raise ValueError(field + ' is required')
    source_inputs(scope)
    helper = checked_file(APPARATUS, 'verify_candidate.py')
    if sha(helper.read_bytes()) != scope.get('verification_helper_sha256'):
        raise ValueError('verification helper changed')
    exe = Path(scope['python_executable'])
    if not exe.is_absolute() or sha(exe.read_bytes()) != scope.get('python_executable_sha256'):
        raise ValueError('verification interpreter changed')
    expected = [{'claim_id': 'pending-contract-read-only-denial', 'argv': [str(exe), '-I', '-B', '.source_construction_verify.py', WRITES[1]], 'artifact_path': WRITES[0]}]
    if scope.get('verification') != expected:
        raise ValueError('exact frozen physical command required')
    if require_review:
        if scope.get('status') != 'REVIEWED_SOURCE_CONSTRUCTION_ONLY' or not scope.get('implementation_requirements'):
            raise ValueError('NOT_READY: parent must freeze full implementation requirements')
        for field in ('review_reference', 'builder_session', 'builder_family'):
            if not isinstance(scope.get(field), str) or not scope[field].strip() or scope[field].startswith('PENDING'):
                raise ValueError('reviewed ' + field + ' is required')
    return scope

def init(args):
    state = Path(args.state).absolute()
    if state != APPARATUS / 'state' or state != state.resolve():
        raise ValueError('only this new isolated state root is authorized')
    scope = validate_scope(read_json(args.scope))
    source = Path(args.source_root).resolve(strict=True)
    if source != REPO:
        raise ValueError('canonical machinery root required')
    state.mkdir(mode=0o700)
    from kernel.cas import CAS, FilesystemCasStore
    from kernel.keystore import load_or_create_signing_key
    key = load_or_create_signing_key(state / 'kernel.key')
    CAS(FilesystemCasStore(state / 'cas'))
    data = {'mode': MODE, 'schema': 2, 'state_root': str(state), 'source_root': str(source), 'captured_source_root': str(CAPTURED_SOURCE), 'approved_scope_sha256': sha(encoded(scope)), 'goal_id': 'sc-pending-g-' + uuid.uuid4().hex, 'run_id': 'sc-pending-r-' + uuid.uuid4().hex, 'created_at': datetime.now(timezone.utc).isoformat(), 'worker_dispatches': 0, 'harness_sha256': sha(Path(__file__).read_bytes()), 'key_public_hex': key.verify_key.encode().hex(), 'claims': {'production': False, 'full_lifecycle': False, 'sealed': False, 'qualification': False}}
    once(state / 'initialization.json', data)
    record(state, 'SOURCE_CONSTRUCTION_INITIALIZED', data)
    return data

def bind(args):
    state = Path(args.state).resolve(strict=True)
    initial = initialized(state)
    scope = validate_scope(read_json(args.scope))
    if sha(encoded(scope)) != initial['approved_scope_sha256']:
        raise ValueError('reviewed scope changed after initialization')
    if (state / 'scope.json').exists() or (state / 'snapshot').exists():
        raise ValueError('scope/snapshot already bound; no reuse')
    manifest = source_inputs(scope)
    cas, _ = components(state)
    snapshot = state / 'snapshot'
    snapshot.mkdir()
    all_files = {}
    for rel in manifest['declared_candidate_paths']:
        data = checked_file(APPARATUS / 'archival_snapshot', rel).read_bytes()
        digest = cas.put(data)
        if digest != manifest['files'][rel]['sha256']:
            raise ValueError('captured source changed during binding')
        dst = snapshot / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        all_files[rel] = {'sha256': digest, 'source': str(APPARATUS / 'archival_snapshot' / rel), 'read_only': rel not in WRITES}
    helper = checked_file(APPARATUS, 'verify_candidate.py')
    helper_bytes = helper.read_bytes()
    (snapshot / '.source_construction_verify.py').write_bytes(helper_bytes)
    all_files['.source_construction_verify.py'] = {'sha256': cas.put(helper_bytes), 'source': str(helper), 'read_only': True}
    reviewed_bytes = encoded(scope)
    (snapshot / '.source_construction_scope.json').write_bytes(reviewed_bytes)
    all_files['.source_construction_scope.json'] = {'sha256': cas.put(reviewed_bytes), 'source': str(Path(args.scope).resolve()), 'read_only': True}
    bound_scope = {**scope, 'source_files': {p: item for p, item in all_files.items() if p not in WRITES}, 'snapshot_files': all_files}
    once(state / 'scope.json', bound_scope)
    scope_hash = sha((state / 'scope.json').read_bytes())
    once(state / 'binding.json', {'scope_sha256': scope_hash, 'source_files': len(all_files), 'bound_at': datetime.now(timezone.utc).isoformat()})
    record(state, 'SOURCE_CONSTRUCTION_SCOPE_BOUND', {'scope_sha256': scope_hash, 'write_files': list(WRITES), 'source_files': len(all_files), 'existing_file_preimages': scope['expected_preimages']})
    return {'state': str(state), 'mode': MODE, 'scope_sha256': scope_hash, 'source_files': len(all_files), 'worker_dispatches': 0}

def bound(state):
    initial = initialized(state)
    scope = read_json(state / 'scope.json')
    binding = read_json(state / 'binding.json')
    if sha((state / 'scope.json').read_bytes()) != binding['scope_sha256']:
        raise ValueError('bound scope changed')
    for rel, item in scope['snapshot_files'].items():
        if sha(checked_file(state / 'snapshot', rel).read_bytes()) != item['sha256']:
            raise ValueError('snapshot changed: ' + rel)
    return initial, scope, binding

def inspect_workspace(state, workspace, scope):
    writes=tuple(scope['write_files'])
    if workspace != workspace.resolve(strict=True) or not workspace.is_dir(): raise ValueError('workspace must be a non-symlink directory')
    files={}
    for p in workspace.rglob('*'):
        if p.is_symlink(): raise ValueError(f'workspace symlink rejected: {p}')
        if not p.is_file(): continue
        rel=p.relative_to(workspace).as_posix()
        if '__pycache__' in p.parts or '.pytest_cache' in p.parts or rel.endswith(('.pyc','.pyo')): continue
        if rel not in scope['source_files'] and rel not in writes: raise ValueError(f'out-of-scope file: {rel}')
        data=p.read_bytes(); digest=sha(data)
        if rel in scope['source_files'] and digest!=scope['source_files'][rel]['sha256']: raise ValueError(f'read-only dependency modified: {rel}')
        files[rel]=digest
    for rel in scope['source_files']:
        if rel not in files: raise ValueError(f'read-only dependency removed: {rel}')
    for rel in writes:
        if rel not in files or not (workspace/rel).stat().st_size: raise ValueError(f'complete nonempty source file required: {rel}')
    return files

def package_record(state):
    initial,scope,binding=bound(state); package=read_json(state/'package.json')
    if (state/'result.json').exists() or time.time()>package['deadline_unix']: raise ValueError('dispatch has ended or expired')
    return initial,scope,package

def exact_workspace(state, workspace, package):
    p=Path(workspace).absolute()
    if p.parent!=state/'workspaces' or p != p.resolve(strict=True): raise ValueError('wrong workspace root')
    expected=f"{package['run_id']}--{package['task_id']}--implement"
    prompt=state/'bridge'/'requests'/f'{expected}.prompt.md'
    if not prompt.is_file() or f'`{p}`' not in prompt.read_text(): raise ValueError('workspace is not the emitted request workspace')
    return p

def verify_capability(state, package, operation):
    from kernel.types import CapabilityBinding,CapabilityToken,Role,StageId
    _,broker=components(state); raw=package['capability']; b=raw['bound_to']
    token=CapabilityToken(raw['token'],CapabilityBinding(b['goal_id'],b['run_id'],StageId(b['stage']),Role(b['role']),b['session']),tuple(raw['operations']),raw['issued_seq'],raw['expires_seq'])
    broker.verify(token,goal_id=package['goal_id'],run_id=package['run_id'],stage=StageId.IMPLEMENT,role=Role.BUILDER,session=package['builder_session'],operation=operation,current_seq=raw['issued_seq'])

def court_submit(args):
    state=Path(args.state).resolve(strict=True); initial,scope,package=package_record(state)
    workspace=exact_workspace(state,args.workspace,package)
    verify_capability(state,package,'mcp:court:submit_evidence')
    manifest=inspect_workspace(state,workspace,scope)
    from runtime.transports.mcp.court_server import build_court_mcp_server
    from runtime.orchestrator import FileCourtEvidencePool
    cas,_=components(state)
    for rel,digest in manifest.items():
        if cas.put((workspace/rel).read_bytes())!=digest: raise ValueError('source changed during unverified capture')
    once(state/'court-submission.started.json',{'mode':MODE,'status':'SOURCE_SUBMITTED_UNVERIFIED','workspace':str(workspace),'manifest':manifest,'candidate_source_preserved_in_cas':True})
    server=build_court_mcp_server(state/'court_pool',workspace_root=state/'workspaces')
    for v in scope['verification']:
        response=asyncio.run(server.call_tool('submit_evidence',{'run_id':initial['run_id'],'claim_id':v['claim_id'],'argv':v['argv'],'workspace_root':str(workspace),'artifact_path':v['artifact_path']}))
        if response.is_error: raise ValueError('real Court MCP submission failed: '+str(response))
    after=inspect_workspace(state,workspace,scope)
    if manifest!=after: raise ValueError('verification changed candidate source')
    evidence=FileCourtEvidencePool(state/'court_pool').evidence_for(initial['run_id'])
    if len(evidence)!=len(scope['verification']) or any(e.result.get('exit_code')!=0 for e in evidence): raise ValueError('physical source verification failed; no completion permitted')
    cas,_=components(state)
    receipt={'mode':MODE,'run_id':initial['run_id'],'workspace_manifest':manifest,'evidence':evidence,'court_adjudication':False,'qualification':False}
    once(state/'court-submission.json',receipt)
    return {'physical_observations':len(evidence),'receipt_sha256':cas.put(encoded(receipt)),'adjudication':False}

def complete(args):
    state=Path(args.state).resolve(strict=True); initial,scope,package=package_record(state)
    writes=tuple(scope['write_files'])
    workspace=exact_workspace(state,args.workspace,package)
    verify_capability(state,package,'mcp:artifacts:publish')
    manifest=inspect_workspace(state,workspace,scope)
    receipt=read_json(state/'court-submission.json')
    if receipt['workspace_manifest']!=manifest: raise ValueError('candidate differs from physically observed candidate')
    cas,_=components(state)
    for rel,digest in manifest.items():
        if cas.put((workspace/rel).read_bytes())!=digest: raise ValueError('candidate changed during capture')
    once(state/'completion.json',{'mode':MODE,'manifest':manifest,'scope_sha256':read_json(state/'binding.json')['scope_sha256'],'run_id':initial['run_id'],'task_id':package['task_id'],'status':'SOURCE_CAPTURED_REQUIRES_INDEPENDENT_VERIFICATION_AND_REVIEW'})
    from runtime.integrations.bridge_protocol import write_once_bytes
    output=state/'bridge'/'responses'/f"{package['run_id']}--{package['task_id']}--implement.response.md"
    write_once_bytes(output,encoded({'mode':MODE,'complete_source_manifest':manifest,'physical_evidence_receipt':str(state/'court-submission.json'),'claims':{'sealed':False,'qualified':False,'promoted':False}}))
    return {'response':str(output),'complete_files':len(manifest),'mutable_files':list(writes)}

def dispatch(args):
    state=Path(args.state).resolve(strict=True); initial,scope,binding=bound(state)
    writes=tuple(scope['write_files'])
    if args.scope_sha256!=binding['scope_sha256']: raise ValueError('explicit bound scope digest mismatch')
    validate_scope(scope)
    once(state/'dispatch.started.json',{'run_id':initial['run_id'],'scope_sha256':binding['scope_sha256'],'started_at':datetime.now(timezone.utc).isoformat(),'retry_authorized':False})
    from runtime.claude_code import AgentDispatcher
    from runtime.integrations.chat_bridge import ChatBridgeRuntime
    from runtime.task_package import Budget,TaskStatus
    from kernel.types import Role,StageId
    cas,broker=components(state); (state/'workspaces').mkdir()
    bridge=ChatBridgeRuntime(state_root=state,workspace_root=state/'workspaces',workspace_source=state/'snapshot',artifact_resolver=cas.get,timeout_seconds=scope['timeout_seconds'])
    class RecordedBridge:
        def run(self,package):
            public={'mode':MODE,'goal_id':package.goal_id,'run_id':package.run_id,'task_id':package.task_id,'builder_session':scope['builder_session'],'builder_family':scope['builder_family'],'deadline_unix':time.time()+scope['timeout_seconds'],'capability':package.capability,'permissions':package.permissions}
            once(state/'package.json',public)
            record(state,'SOURCE_CONSTRUCTION_PACKAGE_DISPATCHED',public)
            return bridge.run(package)
    command=f'{sys.executable} -B {Path(__file__).resolve()}'
    objective=f'''SOURCE_CONSTRUCTION_ONLY. This is a separate manual bootstrap source package. It is not a production mission, full lifecycle, SEALED result, qualification, or integration. Only the two existing captured files {writes!r} are mutable. Preserve their exact frozen preimages. Read .source_construction_scope.json for the full reviewed requirements. Add only the validated read-only pending-state/contract-denial API. Never consume a new supersession, activate or qualify a contract, or issue authority. No pending record means only not invalidated here, never authenticated currentness. Dependencies are read-only. Do not read the harness key or state database, touch canonical source, spawn workers, or self-authorize.\nAuthority reference: {scope['authority_reference']}\n{scope['objective']}\nYou may run the fixed local test helper before submission to repair ordinary test failures inside scope. Court submission is one-use. Physical evidence: after implementation and local tests, invoke the configured Court boundary adapter:\n{command} court-submit --state {state} --workspace <EXACT_WORKSPACE_BELOW>\nThis calls the real Court MCP submit_evidence tool for frozen commands and derives evidence physically; do not write the pool yourself. If it fails, stop and report to the coordinator without publishing completion.\nOn success invoke:\n{command} complete --state {state} --workspace <EXACT_WORKSPACE_BELOW>\nOnly this completion adapter publishes the response after complete source/CAS and dependency-integrity checks. Do not publish a response manually. Heterogeneous review is pending; no provider attempts or resets are allowed. Independent verification and heterogeneous review remain mandatory before integration; this package authorizes no integration. Deadline is fixed at {scope['timeout_seconds']} seconds.\n'''
    try:
        result=AgentDispatcher(broker,cas,RecordedBridge(),clock=lambda:1).dispatch(goal_id=initial['goal_id'],run_id=initial['run_id'],stage=StageId.IMPLEMENT,role=Role.BUILDER,session=scope['builder_session'],objective=objective,write_scopes=writes,read_scopes=tuple(scope['source_files']),mcp_servers=('court:submit_evidence','artifacts:publish'),budget=Budget(100000,scope['timeout_seconds'],0),ttl=scope['timeout_seconds'])
        report={'mode':MODE,'result':result,'scope_sha256':binding['scope_sha256'],'status':'FAILED_OR_UNVERIFIED','integration_permitted':False}
        if result.status is TaskStatus.COMPLETE:
            completion=read_json(state/'completion.json')
            if dict(result.written_paths)!={p:completion['manifest'][p] for p in writes}: raise ValueError('bridge output differs from complete captured source')
            candidate=state/'candidate'; candidate.mkdir()
            for rel,digest in completion['manifest'].items():
                dest=candidate/rel; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(cas.get(digest))
            report['status']='SOURCE_CAPTURED_REQUIRES_INDEPENDENT_VERIFICATION_AND_REVIEW'; report['candidate_root']=str(candidate)
        once(state/'result.json',report); record(state,'SOURCE_CONSTRUCTION_RETURNED',{'status':report['status'],'task_id':result.task_id,'trace_ref':result.trace_ref})
        return report
    except BaseException as exc:
        once(state/'dispatch.failure.json',{'mode':MODE,'error_type':type(exc).__name__,'message':str(exc),'retry_authorized':False})
        raise

def self_check(args):
    scope = read_json(APPARATUS / 'scope.draft.json')
    validate_scope(scope, require_review=False)
    cases = []
    def rejects(label, call):
        try: call()
        except (ValueError, KeyError, FileNotFoundError): cases.append(label)
        else: raise AssertionError('invalid input accepted: ' + label)
    rejects('draft blocks init/bind/dispatch', lambda: validate_scope(scope))
    for value in ('../x', '/absolute.py', 'runtime//x.py', 'runtime/./x.py', 'runtime/*.py', 'runtime\\x.py'):
        rejects('unsafe path ' + value, lambda value=value: safe_relative(value))
    for label, mutate in (
        ('scope expansion', lambda s: s['write_files'].append('runtime/autonomy/mission_controller.py')),
        ('preimage substitution', lambda s: s['expected_preimages'].__setitem__(WRITES[0], '0' * 64)),
        ('manifest substitution', lambda s: s.__setitem__('input_manifest_sha256', '0' * 64)),
        ('verification command substitution', lambda s: s['verification'][0]['argv'].append('-c')),
        ('quarantine exclusion removed', lambda s: s['excluded_from_declared_read_closure'].pop('paeos/model_router/credentials.py')),
    ):
        changed = copy.deepcopy(scope); mutate(changed)
        rejects(label, lambda changed=changed: validate_scope(changed, require_review=False))
    for name in ('harness.py', 'verify_candidate.py'):
        ast.parse(checked_file(APPARATUS, name).read_bytes())
    imports = [n for n in sys.modules if n.split('.')[0] in ('runtime', 'kernel', 'paeos')]
    if imports or (APPARATUS / 'state').exists():
        raise ValueError('mechanical self-check crossed no-import/no-state boundary')
    return {'mode': MODE, 'mechanical_check': 'PASS', 'status': 'NOT_READY_REQUIREMENTS_REVIEW', 'negative_cases': cases, 'archive_files': len(read_json(APPARATUS / 'input_manifest.json')['files']), 'declared_source_paths': len(read_json(APPARATUS / 'input_manifest.json')['declared_candidate_paths']), 'kernel_imports': imports, 'kernel_keys_created': 0, 'capabilities_created': 0, 'dispatches': 0, 'provider_calls': 0, 'source_tests_run': False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('self-check')
    for name in ('init', 'bind', 'dispatch', 'court-submit', 'complete'):
        p = sub.add_parser(name); p.add_argument('--state', required=True)
        if name == 'init':
            p.add_argument('--source-root', required=True)
            p.add_argument('--scope', required=True)
        if name == 'bind': p.add_argument('--scope', required=True)
        if name == 'dispatch': p.add_argument('--scope-sha256', required=True)
        if name in ('court-submit', 'complete'): p.add_argument('--workspace', required=True)
    args = parser.parse_args()
    try:
        result = {'self-check': self_check, 'init': init, 'bind': bind, 'dispatch': dispatch, 'court-submit': court_submit, 'complete': complete}[args.command](args)
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}', file=sys.stderr); return 1
    sys.stdout.buffer.write(encoded(result)); return 0

if __name__ == '__main__':
    raise SystemExit(main())
