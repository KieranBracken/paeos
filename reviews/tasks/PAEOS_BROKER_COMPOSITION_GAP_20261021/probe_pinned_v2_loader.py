"""Required v2 loader join RED, using temporary public fixtures and ephemeral signing."""

from pathlib import Path
import hashlib
import importlib.util
import json
import os

from nacl.signing import SigningKey
from paeos.model_router.disclosure_policy import policy_digest, verify_founder_derivative_policy
from paeos.model_router.disclosure_store import DisclosureInputError, load_pinned_disclosure_policy


repository = Path('/Users/bob/.codex/worktrees/p1-bound-source-recovery/paeos')
spec = importlib.util.spec_from_file_location('policy_fixtures', repository / 'tests/model_router/test_disclosure_policy.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
key = SigningKey.generate()
root = Path(os.environ['PAEOS_SYNTHETIC_WORKSPACE']) / 'policy-fixture'
root.mkdir()
public = {'schema': 'paeos.founder-public-key/1', 'key_id': 'synthetic-founder',
          'algorithm': 'Ed25519', 'public_key_hex': bytes(key.verify_key).hex()}
(root / 'public.json').write_text(json.dumps(public))
policy = fixtures.policy.__wrapped__()
raw_v1 = fixtures.signed(policy, key)
(root / 'policy.json').write_bytes(raw_v1)
inputs = dict(root=root, public_key_relative_path='public.json', policy_relative_path='policy.json',
              expected_key_id='synthetic-founder', expected_public_key_sha256=hashlib.sha256(bytes(key.verify_key)).hexdigest(),
              expected_policy_sha256=hashlib.sha256(json.dumps(json.loads(raw_v1), sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(),
              now=fixtures.NOW)
assert load_pinned_disclosure_policy(**inputs).policy_id == 'synthetic-policy'
policy['schema'] = 'paeos.disclosure-policy/2'
policy['derivative_rules'] = [{
    'rule_id': 'synthetic-rule', 'class_id': 'PUBLIC_ARTIFACT',
    'input_artifact_sha256s': [policy['classes'][0]['scope']['allowed_artifacts'][0]['sha256']],
    'input_data_class': 'PUBLIC', 'output_data_class': 'PUBLIC',
    'tool_envelope_sha256': 'a' * 64, 'transformation_ids': ['READ_APPROVED_ARTIFACT'],
    'max_output_bytes': 1000,
}]
raw_v2 = fixtures.signed(policy, key, domain=b'PAEOS-DISCLOSURE-POLICY-V2\0')
verified_v2 = verify_founder_derivative_policy(raw_v2, key.verify_key, 'synthetic-founder', now=fixtures.NOW)
assert len(verified_v2.derivative_rules) == 1
(root / 'policy.json').write_bytes(raw_v2)
inputs['expected_policy_sha256'] = policy_digest(verified_v2)
try:
    load_pinned_disclosure_policy(**inputs)
except DisclosureInputError:
    print(json.dumps({'required_behavior': 'Load an independently pinned valid signed v2 snapshot through the existing store, still without granting egress.',
                      'v1_loader_control': 'PASS', 'v2_signature_and_shape_control': 'PASS',
                      'v2_pinned_loader_join': 'RED_REJECTED', 'source_changed': False,
                      'provider_calls': 0, 'host_keys': False, 'new_authority': False}, indent=2), flush=True)
    raise SystemExit(2)
raise AssertionError('Observed store behavior changed; refresh source disposition')
