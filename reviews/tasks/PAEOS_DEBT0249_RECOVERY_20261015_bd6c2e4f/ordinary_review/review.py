import dataclasses
import hashlib
import json
from pathlib import Path
import sys
import time

REPO = Path('/Users/bob/GitHub/paeos')
ROOT = Path(__file__).resolve().parent
OLD = Path('/private/tmp/paeos-debt0249-run-7df8fadd781147ffb563e97caa80b814')
sys.path.insert(0, str(REPO))
from paeos.model_router import (ModelRouter, TaskRequest, TaskClass, DataClass, LogicalModel,
    ModelFamily, CostTier, RetryPolicy, request_fingerprint, response_fingerprint)
from paeos.model_router.a08_enforcer import derive_family_from_actual_model

def sha(data):
    return hashlib.sha256(data).hexdigest()

def write(name, obj):
    (ROOT / name).write_text(json.dumps(obj, indent=2, default=str) + '\n')

old = json.loads((OLD / 'L07_ADVERSARY_RECOVERY.intent.json').read_text())
prompt = ('The referenced runtime attempt has since remanded and is closed. This is a fresh, ordinary source review of its preserved planning artifacts. Your response cannot resume it or certify lifecycle completion. Preserve the exact source context below.\n\n' + (OLD / 'L07_ADVERSARY.prompt.txt').read_text())
(ROOT / 'prompt.txt').write_text(prompt)
request = TaskRequest(messages=[{'role': 'user', 'content': prompt}],
    task_class=TaskClass.CODE_REVIEW, data_class=DataClass.INTERNAL,
    logical_model=LogicalModel.PAEOS_AUDIT, builder_family=ModelFamily.GPT,
    explicit_model='gemini-3.6-flash', max_tokens=6000, temperature=0,
    retry_policy=RetryPolicy.NONE, allow_fallback=False, allow_paid_usage=False,
    free_worker_pool=True,
    metadata={'operation_id': ROOT.name, 'purpose': 'ordinary-source-adversarial-review',
        'closed_run_reference': old['run_id'], 'artifact_bindings': old['bindings']})
write('request.json', dataclasses.asdict(request))
receipt = {'schema': 'paeos.ordinary-source-review/1', 'operation_id': ROOT.name,
    'status': 'PREPARED', 'closed_run_reference': old['run_id'],
    'runtime_stage_receipt': False, 'formal_L14_receipt': False,
    'bindings': old['bindings'], 'prompt_sha256': sha(prompt.encode()),
    'request_sha256': request_fingerprint(request),
    'request_policy_sha256': sha((ROOT / 'request.json').read_bytes()),
    'previous_failure_receipt_sha256': sha((OLD / 'L07_ADVERSARY_RECOVERY.receipt.json').read_bytes()),
    'allow_paid_usage': False, 'free_worker_pool': True, 'allow_fallback': False,
    'retry_policy': 'none', 'maximum_provider_attempts': 1}
router = ModelRouter()
chain = router.policy.resolve_candidate_chain(request)
receipt['eligible_candidates'] = [dataclasses.asdict(x) for x in chain]
assert len(chain) == 1
assert chain[0].cost_tier is CostTier.FREE
assert chain[0].family not in (ModelFamily.GPT, ModelFamily.UNKNOWN)
assert chain[0].model_id == 'gemini-3.6-flash'
receipt.update(status='STARTED', started_unix=time.time())
write('intent.json', receipt)
try:
    response = router.route(request)
    raw = response.raw_response
    if hasattr(raw, 'model_dump'):
        raw = raw.model_dump()
    write('raw_response.json', raw)
    (ROOT / 'report.txt').write_text(response.content)
    response_data = {f.name: getattr(response, f.name) for f in dataclasses.fields(response) if f.name not in ('content', 'raw_response')}
    write('response.json', response_data)
    actual_family = derive_family_from_actual_model(response.actual_model, router.catalog)
    checks = {
        'complete': response.finish_reason == 'stop' and bool(response.content.strip()),
        'actual_second_family': actual_family not in (ModelFamily.GPT, ModelFamily.UNKNOWN),
        'catalog_family_matches': actual_family == chain[0].family,
        'actual_model_matches': response.actual_model == chain[0].model_id,
        'request_fingerprint_matches': response.transport_request_sha256 == request_fingerprint(request),
        'response_fingerprint_matches': response.transport_response_sha256 == response_fingerprint(response),
        'generation_identity_present': bool(response.external_generation_id),
    }
    receipt.update(status='COMPLETE' if all(checks.values()) else 'INCOMPLETE_OR_INVALID',
        checks=checks, response=response_data, report_sha256=sha((ROOT / 'report.txt').read_bytes()),
        raw_response_sha256=sha((ROOT / 'raw_response.json').read_bytes()))
except Exception as exc:
    receipt.update(status='FAILED', error_type=type(exc).__name__, message=str(exc))
finally:
    receipt['ended_unix'] = time.time()
    write('receipt.json', receipt)
print(json.dumps({'status': receipt['status'], 'operation_id': ROOT.name,
    'receipt': str(ROOT / 'receipt.json'), 'checks': receipt.get('checks'), 'error': receipt.get('message')}))
