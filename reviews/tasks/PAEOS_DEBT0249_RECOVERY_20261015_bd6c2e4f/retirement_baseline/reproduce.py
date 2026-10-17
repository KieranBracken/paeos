from pathlib import Path
import ast,hashlib,json,os,sys
EVIDENCE=Path(__file__).resolve().parent
ROOT=Path('/Users/bob/GitHub/paeos')
sys.dont_write_bytecode=True
sys.path.insert(0,str(ROOT))
denied=[]
def guard(event,args):
    if event in ('socket.connect','socket.connect_ex','socket.getaddrinfo','subprocess.Popen','os.system'):
        denied.append(event)
        raise RuntimeError('No network or process execution in baseline discrimination')
    if event=='sqlite3.connect':
        target=Path(args[0]).resolve()
        if not target.is_relative_to(EVIDENCE):raise RuntimeError('SQLite restricted to temporary evidence directory')
    if event=='open' and isinstance(args[0],(str,bytes,os.PathLike)):
        target=Path(os.fsdecode(args[0])).resolve()
        mode=args[1] if len(args)>1 else None
        flags=args[2] if len(args)>2 and isinstance(args[2],int) else 0
        writes=(isinstance(mode,str) and any(x in mode for x in 'wax+')) or bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if writes and not target.is_relative_to(EVIDENCE):raise RuntimeError('Writes restricted to temporary evidence directory')
sys.addaudithook(guard)
from paeos.model_router.errors import normalize_error
from paeos.model_router.aimd import AIMDController
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import FailureScope,NormalizedError,NormalizedErrorType,ProviderHealth,ProviderId
receipt_path=Path('/private/tmp/paeos-debt0249-run-7df8fadd781147ffb563e97caa80b814/L07_ADVERSARY.receipt.json')
receipt_raw=receipt_path.read_bytes()
receipt=json.loads(receipt_raw)
message=receipt['message']
wrapped=message.split('RetryAfter=None: ',1)[1]
body=ast.literal_eval(wrapped.split('Error code: 410 - ',1)[1])
assert set(body)=={'type','title','status','detail'}
assert body['status']==410 and body['title']=='Gone'
model='meta/llama-3.1-8b-instruct'
sibling='same-provider-sibling-health-control'
provider=ProviderId.NVIDIA
(EVIDENCE/'redacted-response.json').write_text(json.dumps({'http_status':410,'body':body,'wrapped_exception_message':wrapped,'source_receipt_sha256':hashlib.sha256(receipt_raw).hexdigest(),'redaction':'Only public error fields retained; all task/prompt/request envelope fields omitted. No original HTTP response bytes are present in the saved receipt.'},indent=2)+'\n')
results={}
errors={}
for label,shape in [('dict',body),('json_string',json.dumps(body)),('saved_exception_string',wrapped)]:
    err=normalize_error(http_status=410,body=shape,provider_id=provider,model_id=model)
    errors[label]=err
    results[label]={'type':err.error_type.value,'scope':err.failure_scope.value,'scope_key':err.scope_key,'retry_after':err.retry_after,'http_status':err.http_status}

def snap(db,aimd):
    return {'provider_health':db.get_provider_state(provider)['health_status'],'model_health':db.get_scoped_health(provider,FailureScope.MODEL,model)['health_status'],'sibling_health':db.get_scoped_health(provider,FailureScope.MODEL,sibling)['health_status'],'model_admission':list(aimd.check_admission(provider,model_id=model)),'sibling_admission':list(aimd.check_admission(provider,model_id=sibling))}

def scenario(label,error):
    db_path=EVIDENCE/(label+'.sqlite3')
    db=RouterStateDB(db_path)
    aimd=AIMDController(db)
    before=snap(db,aimd)
    aimd.on_error(provider,error)
    after=snap(db,aimd)
    reopened=RouterStateDB(db_path)
    return {'before':before,'after_on_error':after,'after_reopen':snap(reopened,AIMDController(reopened))}
observed=scenario('actual_410',errors['saved_exception_string'])
explicit=NormalizedError(error_type=NormalizedErrorType.MODEL_UNAVAILABLE,message='Offline discriminator for already-normalized retirement',provider_id=provider,model_id=model,http_status=410,failure_scope=FailureScope.MODEL,scope_key=model)
normalized=scenario('explicit_model_unavailable',explicit)
control_db=RouterStateDB(EVIDENCE/'state_primitive_control.sqlite3')
control_aimd=AIMDController(control_db)
control_db.set_scoped_health(provider,FailureScope.MODEL,model,ProviderHealth.UNAVAILABLE,error_type=NormalizedErrorType.MODEL_UNAVAILABLE)
control=snap(control_db,control_aimd)
reopened=RouterStateDB(EVIDENCE/'state_primitive_control.sqlite3')
control_reopened=snap(reopened,AIMDController(reopened))
assert all(x['type']=='UNKNOWN' for x in results.values())
assert observed['after_on_error']['model_admission']==[True,None]
assert normalized['after_on_error']['model_admission']==[True,None]
assert normalized['after_on_error']['sibling_admission']==[True,None]
assert control['model_admission'][0] is False and control['sibling_admission']==[True,None]
assert control_reopened==control
imports=[]
for name,module in sorted(sys.modules.items()):
    if name.startswith('paeos.model_router') and getattr(module,'__file__',None):
        path=Path(module.__file__).resolve()
        imports.append({'module':name,'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
report={'python':sys.executable,'python_version':sys.version,'cwd':str(Path.cwd()),'direct_imports':['paeos.model_router.errors.normalize_error','paeos.model_router.aimd.AIMDController','paeos.model_router.state.RouterStateDB','paeos.model_router.types.FailureScope/NormalizedError/NormalizedErrorType/ProviderHealth/ProviderId'],'actual_router_package_imports':imports,'normalization':results,'actual_410_on_error':observed,'explicit_model_unavailable_on_error':normalized,'state_primitive_control':control,'state_primitive_after_reopen':control_reopened,'network_or_process_attempts_denied':denied,'state_scope':'Only three new explicit temporary SQLite paths; default production state never instantiated. Sibling is an offline health-control identity, not a claim of catalog eligibility.','baseline_discrimination':'CONFIRMED: exact saved retirement shape normalizes UNKNOWN; even explicit MODEL_UNAVAILABLE is ignored; existing scoped-state primitive correctly excludes only selected model.'}
(EVIDENCE/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='actual_router_package_imports'},indent=2))
