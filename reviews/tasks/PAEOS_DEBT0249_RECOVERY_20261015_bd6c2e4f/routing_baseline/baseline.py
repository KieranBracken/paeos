from __future__ import annotations
import dataclasses, datetime, hashlib, importlib, json, os, pathlib, sys, traceback
ROOT=pathlib.Path(sys.argv[1]).resolve()
REPO=pathlib.Path('/Users/bob/GitHub/paeos').resolve()
blocked=[]
def audit(event,args):
    if event in {'socket.connect','socket.connect_ex','socket.getaddrinfo','socket.sendto','socket.sendmsg'}:
        blocked.append({'kind':'network','event':event})
        raise PermissionError('Network disabled for deterministic baseline')
    if event in {'subprocess.Popen','os.system','os.posix_spawn','os.posix_spawnp'}:
        blocked.append({'kind':'process','event':event})
        raise PermissionError('Child processes disabled for deterministic baseline')
    target=None
    if event=='open':
        path,mode,flags=args
        writing=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or (isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if writing and not isinstance(path,int): target=path
    elif event in {'os.mkdir','os.remove','os.rmdir','os.chmod','os.truncate'}: target=args[0]
    elif event=='sqlite3.connect' and args[0] != ':memory:': target=args[0]
    if target is not None:
        p=pathlib.Path(os.fsdecode(target)).resolve()
        if not p.is_relative_to(ROOT):
            blocked.append({'kind':'write','event':event,'path':str(p)})
            raise PermissionError('Write outside evidence directory disabled')
    if event in {'os.rename','os.link','os.symlink'}:
        for target in args[:2]:
            if isinstance(target,(str,bytes)) and not pathlib.Path(os.fsdecode(target)).resolve().is_relative_to(ROOT):
                blocked.append({'kind':'write','event':event})
                raise PermissionError('Cross-directory filesystem mutation disabled')
sys.addaudithook(audit)
sys.path.insert(0,str(REPO))
report={'schema':'paeos.free-pool-policy-baseline/1','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'canonical_root':str(REPO),'python':sys.executable,'python_version':sys.version,'provider_calls':0,'router_route_calls':0,'scope':'deterministic policy API fixture checks; no live availability or qualification claims','cases':[]}
try:
    from paeos.model_router.catalog import ModelCatalog
    from paeos.model_router.credentials import CredentialStore, PROVIDER_ENV_MAPPING
    from paeos.model_router.state import RouterStateDB
    from paeos.model_router.aimd import AIMDController
    from paeos.model_router.policy import RoutingPolicyEngine
    from paeos.model_router.types import AdmissionState,CostTier,DataClass,FailureScope,LogicalModel,ModelCatalogEntry,ModelFamily,ProviderHealth,ProviderId,TaskClass,TaskRequest
    modules=['paeos.model_router.policy','paeos.model_router.audit','paeos.model_router.a08_enforcer','paeos.model_router.catalog','paeos.model_router.state','paeos.model_router.aimd','paeos.model_router.credentials','paeos.model_router.types','paeos.model_router.intelligence_tier']
    report['imports']={}
    for name in modules:
        module=importlib.import_module(name);path=pathlib.Path(module.__file__).resolve()
        if not path.is_relative_to(REPO): raise RuntimeError('Noncanonical source import')
        report['imports'][name]={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    def make(entries,name,providers=(ProviderId.GOOGLE,)):
        cat=ModelCatalog(entries)
        creds=object.__new__(CredentialStore)
        creds.provider_registry=cat.provider_registry
        creds._keys={PROVIDER_ENV_MAPPING[p]:'synthetic-test-only-placeholder' for p in providers}
        db=RouterStateDB(ROOT/(name+'.sqlite3'))
        policy=RoutingPolicyEngine(cat,db,creds,AIMDController(db))
        return policy,db
    def entry(model='gemini-3.6-flash',**kwargs):
        values=dict(model_id=model,provider_id=ProviderId.GOOGLE,family=ModelFamily.GEMINI,cost_tier=CostTier.FREE,pricing_verified_free=True,live_verified=True,available=True,admission_state=AdmissionState.ADMITTED,context_window=32000)
        values.update(kwargs)
        return ModelCatalogEntry(**values)
    def req(**kwargs):
        values=dict(messages=[{'role':'user','content':'deterministic bounded policy test'}],task_class=TaskClass.CODE_REVIEW,data_class=DataClass.INTERNAL,logical_model=LogicalModel.PAEOS_AUDIT,builder_family=ModelFamily.GPT,max_tokens=100,allow_paid_usage=False,free_worker_pool=True)
        values.update(kwargs)
        return TaskRequest(**values)
    def ids(chain): return [f'{m.provider_id.value}:{m.model_id}' for m in chain]
    def record(name,chain,expected,kind,details=None):
        actual=ids(chain)
        report['cases'].append({'name':name,'kind':kind,'expected':expected,'actual':actual,'contract_passed':actual==expected,'details':details or {}})
    p,d=make([entry()],'duplicate')
    record('audit_candidate_is_not_duplicated',p.resolve_candidate_chain(req()),['google:gemini-3.6-flash'],'defect')
    record('non_audit_selection_control',p.resolve_candidate_chain(req(logical_model=LogicalModel.PAEOS_AUTO)),['google:gemini-3.6-flash'],'positive_control')
    p,d=make([entry('fixture/subscription-gemini',cost_tier=CostTier.SUBSCRIPTION_INCLUDED),entry()],'free_reintroduction')
    record('audit_does_not_reintroduce_subscription_outside_free_pool',p.resolve_candidate_chain(req()),['google:gemini-3.6-flash'],'defect')
    record('free_pool_filter_control',p.resolve_candidate_chain(req(logical_model=LogicalModel.PAEOS_AUTO)),['google:gemini-3.6-flash'],'positive_control')
    p,d=make([entry(context_window=32),entry('fixture/long-context-gemini')],'context_reintroduction')
    longreq=req(messages=[{'role':'user','content':'x'*4096}],free_worker_pool=False)
    record('audit_does_not_reintroduce_context_excluded_model',p.resolve_candidate_chain(longreq),['google:fixture/long-context-gemini'],'defect',{'estimated_tokens':1124,'first_context_window':32})
    record('context_filter_control',p.resolve_candidate_chain(dataclasses.replace(longreq,logical_model=LogicalModel.PAEOS_AUTO)),['google:fixture/long-context-gemini'],'positive_control')
    p,d=make([entry(),entry('fixture/healthy-gemini')],'health_reintroduction')
    d.set_scoped_health(ProviderId.GOOGLE,FailureScope.MODEL,'gemini-3.6-flash',ProviderHealth.UNAVAILABLE)
    record('audit_does_not_reintroduce_scoped_unavailable_model',p.resolve_candidate_chain(req(free_worker_pool=False)),['google:fixture/healthy-gemini'],'defect')
    record('scoped_health_filter_control',p.resolve_candidate_chain(req(free_worker_pool=False,logical_model=LogicalModel.PAEOS_AUTO)),['google:fixture/healthy-gemini'],'positive_control')
    p,d=make([entry('openrouter/free',provider_id=ProviderId.OPENROUTER,family=ModelFamily.UNKNOWN)],'unknown_family',providers=(ProviderId.OPENROUTER,))
    record('audit_rejects_unknown_family',p.resolve_candidate_chain(req()),[],'defect')
    p,d=make([entry(available=False)],'unavailable_control')
    record('unavailable_model_control',p.resolve_candidate_chain(req()),[],'positive_control')
    p,d=make([entry()],'credentials_control',providers=())
    record('audit_does_not_revive_empty_credential_filtered_chain',p.resolve_candidate_chain(req()),[],'defect')
    record('missing_credentials_non_audit_control',p.resolve_candidate_chain(req(logical_model=LogicalModel.PAEOS_AUTO)),[],'positive_control')
    report['counts']={'defects_reproduced':sum(c['kind']=='defect' and not c['contract_passed'] for c in report['cases']),'defect_cases':sum(c['kind']=='defect' for c in report['cases']),'positive_controls_passed':sum(c['kind']=='positive_control' and c['contract_passed'] for c in report['cases']),'positive_controls':sum(c['kind']=='positive_control' for c in report['cases'])}
    report['canonical_import_hashes_unchanged']=all(hashlib.sha256(pathlib.Path(v['path']).read_bytes()).hexdigest()==v['sha256'] for v in report['imports'].values())
    report['status']='BASELINE_RED_CONFIRMED' if report['counts']=={'defects_reproduced':6,'defect_cases':6,'positive_controls_passed':6,'positive_controls':6} and report['canonical_import_hashes_unchanged'] else 'UNEXPECTED_BASELINE'
except Exception as exc:
    report['status']='HARNESS_ERROR';report['error']={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
report['blocked_events']=blocked
(ROOT/'baseline-results.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':report['status'],'counts':report.get('counts'),'results':str(ROOT/'baseline-results.json'),'blocked_events':blocked},indent=2))
if report['status']=='HARNESS_ERROR': print(report['error']['traceback'])
sys.exit(0 if report['status']=='BASELINE_RED_CONFIRMED' else 1)
