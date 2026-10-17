import dataclasses,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,'/Users/bob/GitHub/paeos')
from paeos.model_router import ModelRouter,TaskRequest,TaskClass,DataClass,LogicalModel,ModelFamily,CostTier,RetryPolicy,request_fingerprint,response_fingerprint
from paeos.model_router.a08_enforcer import derive_family_from_actual_model
def write(name,obj):
    (ROOT/name).write_text(json.dumps(obj,indent=2,default=str)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
meta=json.loads((ROOT/'metadata.json').read_text())
request=TaskRequest(messages=[{'role':'user','content':(ROOT/'prompt.txt').read_text()}],task_class=TaskClass.CODE_REVIEW,data_class=DataClass.INTERNAL,logical_model=LogicalModel.PAEOS_AUDIT,builder_family=ModelFamily.GPT,explicit_model='gemini-3.6-flash',max_tokens=6000,temperature=0,retry_policy=RetryPolicy.NONE,allow_fallback=False,allow_paid_usage=False,free_worker_pool=True,metadata=meta)
write('request.json',dataclasses.asdict(request))
router=ModelRouter();chain=router.policy.resolve_candidate_chain(request)
assert len(chain)==1 and chain[0].cost_tier is CostTier.FREE and chain[0].family not in (ModelFamily.GPT,ModelFamily.UNKNOWN)
receipt=dict(meta,status='STARTED',started_unix=time.time(),prompt_sha256=sha(ROOT/'prompt.txt'),request_sha256=request_fingerprint(request),request_policy_sha256=sha(ROOT/'request.json'),eligible_candidates=[dataclasses.asdict(x) for x in chain])
assert not (ROOT/'intent.json').exists()
write('intent.json',receipt)
try:
    response=router.route(request)
    raw=response.raw_response
    if hasattr(raw,'model_dump'):raw=raw.model_dump()
    write('raw_response.json',raw)
    (ROOT/'report.txt').write_text(response.content)
    rd={f.name:getattr(response,f.name) for f in dataclasses.fields(response) if f.name not in ('content','raw_response')};write('response.json',rd)
    family=derive_family_from_actual_model(response.actual_model,router.catalog)
    checks={'complete':response.finish_reason=='stop' and bool(response.content.strip()),'actual_second_family':family not in (ModelFamily.GPT,ModelFamily.UNKNOWN),'actual_model_matches':response.actual_model==chain[0].model_id,'catalog_family_matches':family==chain[0].family,'request_matches':response.transport_request_sha256==request_fingerprint(request),'response_matches':response.transport_response_sha256==response_fingerprint(response),'generation_identity_present':bool(response.external_generation_id)}
    receipt.update(status='COMPLETE' if all(checks.values()) else 'INCOMPLETE_OR_INVALID',checks=checks,response=rd,report_sha256=sha(ROOT/'report.txt'),raw_response_sha256=sha(ROOT/'raw_response.json'))
except Exception as exc:
    receipt.update(status='FAILED',error_type=type(exc).__name__,message=str(exc))
finally:
    receipt['ended_unix']=time.time();write('receipt.json',receipt)
print(json.dumps({'status':receipt['status'],'receipt':str(ROOT/'receipt.json'),'error':receipt.get('message')}),flush=True)
