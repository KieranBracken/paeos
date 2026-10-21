"""Synthetic characterization of existing interfaces; not an authorization producer."""

from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
from dataclasses import replace

from nacl.signing import SigningKey
from paeos.model_router.disclosure_policy import (
    DisclosurePolicyError,
    verify_founder_derivative_policy,
)
from runtime.autonomy.admission_send_fence import AdmissionNotCurrent
from runtime.integrations.mediated_worker_tools import MediatedWorkerTools, WorkerToolScope


ROOT = Path('/Users/bob/.codex/worktrees/p1-bound-source-recovery/paeos')


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


policies = load('synthetic_policy_fixtures', 'tests/model_router/test_disclosure_policy.py')
admissions = load('synthetic_authority_fixtures', 'tests/runtime/autonomy/test_admission_authority.py')
policy = policies.policy.__wrapped__()
key = SigningKey.generate()
policy['schema'] = 'paeos.disclosure-policy/2'
artifact_digest = policy['classes'][0]['scope']['allowed_artifacts'][0]['sha256']
policy['derivative_rules'] = [{
    'rule_id': 'synthetic-read', 'class_id': 'PUBLIC_ARTIFACT',
    'input_artifact_sha256s': [artifact_digest], 'input_data_class': 'PUBLIC',
    'output_data_class': 'PUBLIC', 'tool_envelope_sha256': 'a' * 64,
    'transformation_ids': ['READ_APPROVED_ARTIFACT'], 'max_output_bytes': 1000,
}]
raw = policies.signed(policy, key, domain=b'PAEOS-DISCLOSURE-POLICY-V2\0')
parsed = verify_founder_derivative_policy(raw, key.verify_key, 'synthetic-founder', now=policies.NOW)
assert len(parsed.derivative_rules) == 1

quota_policy = copy.deepcopy(policy)
quota_policy['classes'][0]['allowed_routes'][0]['entitlement_class'] = 'CODEX_PLAN_QUOTA'
quota_raw = policies.signed(quota_policy, key, domain=b'PAEOS-DISCLOSURE-POLICY-V2\0')
try:
    verify_founder_derivative_policy(quota_raw, key.verify_key, 'synthetic-founder', now=policies.NOW)
except DisclosurePolicyError:
    quota_result = 'REJECTED_BY_EXISTING_ROUTE_POLICY_VOCABULARY'
else:
    raise AssertionError('Unexpected plan-quota policy acceptance')

ledger, authority, fence, operation, canonical_policy, admission, issuer, *_ = admissions.setup_authority()
sink = []
fence.send_once(operation, lambda body: sink.append(body))
assert sink == [b'frame']

ledger2, authority2, fence2, operation2, *_ = admissions.setup_authority()
derived_sink = []
try:
    fence2.send_once(replace(operation2, frame=b'synthetic derived bytes'), lambda body: derived_sink.append(body))
except AdmissionNotCurrent:
    pass
else:
    raise AssertionError('Existing exact-frame fence unexpectedly authorised an unlisted derivative')
assert not derived_sink

head = ledger.head_hash()
try:
    authority.issue(
        'TOOL_DERIVATION_OBSERVED',
        dict(grant_id='grant', expires_at=admissions.END, **admissions.BINDINGS),
        issuer_id='issuer', signer=issuer.sign,
    )
except ValueError as error:
    assert str(error) == 'unsupported authority event'
else:
    raise AssertionError('Unknown derivation event was admitted')
assert ledger.head_hash() == head

workspace = Path(os.environ['PAEOS_SYNTHETIC_WORKSPACE']) / 'workspace'
workspace.mkdir()
(workspace / 'public.txt').write_text('synthetic public bytes', encoding='utf-8')
scope = WorkerToolScope(workspace=workspace, artifacts={'public': 'public.txt'}, patch_targets={}, tests={})
result = MediatedWorkerTools(scope).invoke('read_artifact', {'artifact_id': 'public'})
assert result['sha256'] == hashlib.sha256(b'synthetic public bytes').hexdigest()

print(json.dumps({
    'probe': 'EXISTING_SOURCE_INTERFACE_CHARACTERIZATION_ONLY',
    'valid_signed_v2_derivative_permission': 'PARSED_SIGNATURE_AND_SHAPE_ONLY_NOT_EGRESS_AUTHORITY',
    'plan_quota_route_class': quota_result,
    'signed_exact_frame_positive_control': {'fake_sink_writes': len(sink)},
    'unlisted_derived_frame_negative_control': {'fake_sink_writes': len(derived_sink)},
    'unknown_derivation_authority_event': {'rejected': True, 'ledger_head_unchanged': ledger.head_hash() == head},
    'actual_parent_tool_result': {'keys': sorted(result), 'content_digest': result['sha256'], 'authority_or_currentness_established': False},
    'boundary': 'The source has exact-frame admission and derivative permission syntax, but this probe did not establish an authenticated derivation observation/consumer join or a plan-quota route contract. No new event kind or authority is introduced.',
    'effects': {'canonical_host_store': False, 'host_keys': False, 'external_network': False, 'provider_calls': 0, 'production_admission': False},
}, indent=2))
