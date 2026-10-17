#!/usr/bin/env python3
"""Isolated manual bootstrap apparatus. Never a production lifecycle or qualification."""
from __future__ import annotations
import argparse
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
WRITES = ('runtime/critique.py', 'tests/runtime/test_debt0249_remand14.py')
AUTHORIZED_SCOPES = (WRITES,)
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

def init(args):
    state=Path(args.state).absolute()
    if state != state.resolve(): raise ValueError('state root must not use symlinks')
    source=Path(args.source_root).resolve(strict=True)
    if source != REPO: raise ValueError('canonical runtime root must be the authorized repository')
    state.mkdir(mode=0o700) # exclusive: no reuse of any existing state
    from kernel.cas import CAS, FilesystemCasStore
    from kernel.keystore import load_or_create_signing_key
    key=load_or_create_signing_key(state/'kernel.key')
    CAS(FilesystemCasStore(state/'cas'))
    data={'mode':MODE,'schema':1,'state_root':str(state),'source_root':str(source),
          'goal_id':'sc-g-'+uuid.uuid4().hex,'run_id':'sc-r-'+uuid.uuid4().hex,
          'created_at':datetime.now(timezone.utc).isoformat(),'worker_dispatches':0,
          'harness_sha256':sha(Path(__file__).read_bytes()),'key_public_hex':key.verify_key.encode().hex(),
          'claims':{'production':False,'full_lifecycle':False,'sealed':False,'qualification':False}}
    once(state/'initialization.json',data)
    record(state,'SOURCE_CONSTRUCTION_INITIALIZED',data)
    return data

def validate_scope(scope):
    if scope.get('mode') != MODE: raise ValueError('source-only mode required')
    if tuple(scope.get('write_files',[])) not in AUTHORIZED_SCOPES: raise ValueError('exact two-file write scope required')
    for key in ('objective','authority_reference','builder_session','builder_family'):
        if not isinstance(scope.get(key),str) or not scope[key].strip(): raise ValueError(f'{key} required')
    if scope.get('timeout_seconds') != 1800: raise ValueError('fixed 1800-second construction deadline required')
    if not scope.get('verification'): raise ValueError('non-vacuous frozen verification required')
    claims=set()
    for v in scope['verification']:
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}',v['claim_id']): raise ValueError('invalid claim id')
        argv=v['argv']
        if not isinstance(argv,list) or not argv or any(not isinstance(x,str) or not x for x in argv): raise ValueError('invalid argv')
        if not Path(argv[0]).is_absolute() or any(Path(x).is_absolute() for x in argv[1:]): raise ValueError('argv must use absolute executable and relative arguments')
        if any(any(c in x for c in ';' + '&|<>`$') for x in argv) or '-c' in argv: raise ValueError('shell argv forbidden')
        if v['artifact_path'] not in scope['write_files']: raise ValueError('verification must bind a mutable artifact')
        if v['claim_id'] in claims: raise ValueError('duplicate claim')
        claims.add(v['claim_id'])
    for path in scope.get('read_documents',[]): safe_relative(path)
    for item in scope.get('read_overrides',[]):
        rel=safe_relative(item['path'])
        if rel in scope['write_files'] or not rel.endswith('.py') or PurePosixPath(rel).parts[0] not in ('kernel','runtime','paeos','tests'):
            raise ValueError('read override must be an authorized source dependency')
        p=Path(item['source'])
        if not p.is_absolute() or p != p.resolve(strict=True) or not p.is_file(): raise ValueError('override source must be non-symlink regular file')
        if sha(p.read_bytes()) != item['sha256']: raise ValueError('override hash mismatch')
    return scope

def bind(args):
    state=Path(args.state).resolve(strict=True); initial=initialized(state)
    if (state/'scope.json').exists() or (state/'snapshot').exists(): raise ValueError('scope/snapshot already bound')
    scope=validate_scope(read_json(args.scope)); writes=tuple(scope['write_files'])
    source=Path(initial['source_root'])
    preimages=scope.get('mutable_preimages',{rel:None for rel in writes})
    if set(preimages)!=set(writes): raise ValueError('exact mutable preimages required')
    for rel,digest in preimages.items():
        path=source/rel
        if digest is None:
            if path.exists(): raise ValueError('expected ABSENT preimage: '+rel)
        elif sha(checked_file(source,rel).read_bytes())!=digest: raise ValueError('mutable preimage mismatch: '+rel)
    pins={x['path']:x['sha256'] for x in scope.get('read_file_pins',[])}
    if len(pins)!=len(scope.get('read_file_pins',[])): raise ValueError('duplicate read dependency pin')
    if pins:
        paths=set(pins)
    else:
        listing=subprocess.run(['git','ls-files','-z','--','kernel','runtime','paeos','tests'],cwd=source,check=True,capture_output=True).stdout
        paths={s.decode() for s in listing.split(b'\0') if s and s.endswith(b'.py')}
    paths.difference_update(writes)
    absent_source_files=sorted(p for p in paths if not (source/p).exists())
    paths.difference_update(absent_source_files)
    paths.update(('pyproject.toml','uv.lock')); paths.update(scope.get('read_documents',[]))
    overrides={x['path']:x for x in scope.get('read_overrides',[])}
    if len(overrides)!=len(scope.get('read_overrides',[])): raise ValueError('duplicate read override')
    paths.update(overrides)
    cas,_=components(state); snapshot=state/'snapshot'; snapshot.mkdir()
    manifest={}
    for rel in sorted(paths):
        if rel in writes: raise ValueError('mutable file unexpectedly in input closure')
        src=Path(overrides[rel]['source']) if rel in overrides else checked_file(source,rel)
        data=src.read_bytes(); digest=cas.put(data)
        if rel in pins and digest!=pins[rel]: raise ValueError('read dependency pin mismatch: '+rel)
        if rel in overrides and digest!=overrides[rel]['sha256']: raise ValueError('override changed during binding')
        dst=snapshot/rel; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(data)
        manifest[rel]={'sha256':digest,'source':str(src),'read_only':True}
    for rel,digest in preimages.items():
        if digest is not None:
            data=checked_file(source,rel).read_bytes()
            if cas.put(data)!=digest: raise ValueError('mutable preimage raced: '+rel)
            dst=snapshot/rel; dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(data)
            manifest[rel]={'sha256':digest,'source':str(source/rel),'read_only':False}
    helper=Path(__file__).with_name('verify_candidate.py'); helper_bytes=helper.read_bytes()
    (snapshot/'.source_construction_verify.py').write_bytes(helper_bytes)
    manifest['.source_construction_verify.py']={'sha256':cas.put(helper_bytes),'source':str(helper),'read_only':True}
    bound={**scope,'absent_source_files':absent_source_files,'source_files':manifest,'mutable_preimages':preimages}
    once(state/'scope.json',bound)
    scope_hash=sha((state/'scope.json').read_bytes())
    once(state/'binding.json',{'scope_sha256':scope_hash,'source_files':len(manifest),'bound_at':datetime.now(timezone.utc).isoformat()})
    record(state,'SOURCE_CONSTRUCTION_SCOPE_BOUND',{'scope_sha256':scope_hash,'write_files':list(writes),'source_files':len(manifest)})
    return {'state':str(state),'mode':MODE,'scope_sha256':scope_hash,'source_files':len(manifest),'worker_dispatches':0}

def bound(state):
    initial=initialized(state); scope=read_json(state/'scope.json'); binding=read_json(state/'binding.json')
    if sha((state/'scope.json').read_bytes())!=binding['scope_sha256']: raise ValueError('bound scope changed')
    for rel,item in scope['source_files'].items():
        if sha(checked_file(state/'snapshot',rel).read_bytes())!=item['sha256']: raise ValueError(f'snapshot changed: {rel}')
    return initial,scope,binding

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
        if rel in scope['source_files'] and scope['source_files'][rel]['read_only'] and digest!=scope['source_files'][rel]['sha256']: raise ValueError(f'read-only dependency modified: {rel}')
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
    for rel,digest in scope['mutable_preimages'].items():
        current=Path(initial['source_root'])/rel
        if digest is None:
            if current.exists(): raise ValueError('canonical preimage is no longer absent')
        elif sha(checked_file(Path(initial['source_root']),rel).read_bytes())!=digest: raise ValueError('canonical mutable preimage changed')
    # Canonical machinery, frozen source read closure; never import candidate code into the broker.
    for rel,item in scope['source_files'].items():
        if item['source']==str(REPO/rel) and rel.startswith(('runtime/','kernel/')) and sha((REPO/rel).read_bytes())!=item['sha256']:
            raise ValueError('canonical runtime dependency changed since snapshot: '+rel)
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
    objective=f'''SOURCE_CONSTRUCTION_ONLY. This is a separate manual bootstrap source package. It is not a production mission, full lifecycle, SEALED result, qualification, or integration. Only the two source files {writes!r} are mutable. Dependencies are read-only. Do not read the harness key or state database, touch canonical source, spawn workers, or self-authorize.\nAuthority reference: {scope['authority_reference']}\n{scope['objective']}\nYou may run the fixed local test helper before submission to repair ordinary test failures inside scope. Court submission is one-use. Physical evidence: after implementation and local tests, invoke the configured Court boundary adapter:\n{command} court-submit --state {state} --workspace <EXACT_WORKSPACE_BELOW>\nThis calls the real Court MCP submit_evidence tool for frozen commands and derives evidence physically; do not write the pool yourself. If it fails, stop and report to the coordinator without publishing completion.\nOn success invoke:\n{command} complete --state {state} --workspace <EXACT_WORKSPACE_BELOW>\nOnly this completion adapter publishes the response after complete source/CAS and dependency-integrity checks. Do not publish a response manually. Independent verification and heterogeneous review remain mandatory before integration; this package authorizes no integration. Deadline is fixed at {scope['timeout_seconds']} seconds.\n'''
    try:
        result=AgentDispatcher(broker,cas,RecordedBridge(),clock=lambda:1).dispatch(goal_id=initial['goal_id'],run_id=initial['run_id'],stage=StageId.IMPLEMENT,role=Role.BUILDER,session=scope['builder_session'],objective=objective,write_scopes=writes,read_scopes=tuple(p for p,m in scope['source_files'].items() if m['read_only']),mcp_servers=('court:submit_evidence','artifacts:publish'),budget=Budget(100000,scope['timeout_seconds'],0),ttl=scope['timeout_seconds'])
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

def main():
    parser=argparse.ArgumentParser(description=__doc__); sub=parser.add_subparsers(dest='command',required=True)
    for name in ('init','bind','dispatch','court-submit','complete'):
        p=sub.add_parser(name); p.add_argument('--state',required=True)
        if name=='init': p.add_argument('--source-root',required=True)
        if name=='bind': p.add_argument('--scope',required=True)
        if name=='dispatch': p.add_argument('--scope-sha256',required=True)
        if name in ('court-submit','complete'): p.add_argument('--workspace',required=True)
    args=parser.parse_args()
    try: result={'init':init,'bind':bind,'dispatch':dispatch,'court-submit':court_submit,'complete':complete}[args.command](args)
    except Exception as exc:
        print(f'{type(exc).__name__}: {exc}',file=sys.stderr); return 1
    sys.stdout.buffer.write(encoded(result)); return 0

if __name__=='__main__': raise SystemExit(main())
