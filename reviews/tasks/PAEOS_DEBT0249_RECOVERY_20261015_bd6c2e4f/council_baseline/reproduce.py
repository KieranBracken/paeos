from __future__ import annotations
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = Path('/Users/bob/GitHub/paeos')
sys.dont_write_bytecode = True
sys.path.insert(0, str(REPO))
blocked_events = []
def require_local(path):
    if isinstance(path, int):
        return
    resolved = Path(os.fsdecode(path)).resolve()
    if resolved != ROOT and ROOT not in resolved.parents:
        raise RuntimeError('write outside temporary evidence directory rejected: ' + str(resolved))
def guard(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo', 'subprocess.Popen', 'os.system'):
        blocked_events.append(event)
        raise RuntimeError('network or process execution forbidden: ' + event)
    if event == 'open':
        path, mode, flags = args
        if (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
            require_local(path)
    elif event in ('os.mkdir', 'os.remove', 'os.rmdir'):
        require_local(args[0])
    elif event in ('os.rename', 'os.link', 'os.symlink'):
        require_local(args[0]); require_local(args[1])
sys.addaudithook(guard)

from kernel.cas import CAS, FilesystemCasStore
from runtime.critique import (
    CouncilVote, CouncilVoteStance, record_council_deliberation,
    verify_council_deliberation_invariants,
)

paths = ['runtime/critique.py', 'kernel/cas.py', 'runtime/__init__.py', 'kernel/__init__.py', 'tests/runtime/test_executable_law_canaries.py', 'docs/PAEOS_MODEL_ROUTER_INFERENCE_MESH_SPEC.md']
def pins():
    return {p: {'sha256': hashlib.sha256((REPO/p).read_bytes()).hexdigest(), 'bytes': (REPO/p).stat().st_size} for p in paths}
initial_pins = pins()
(ROOT/'source-pins.json').write_text(json.dumps(initial_pins, indent=2)+'\n')
cas = CAS(FilesystemCasStore(ROOT/'cas'))
votes = (
    CouncilVote('offline-a', CouncilVoteStance.APPROVE, 'offline-fixture-a', 'Approve bounded fixture.'),
    CouncilVote('offline-b', CouncilVoteStance.APPROVE, 'offline-fixture-b', 'Approve bounded fixture.'),
    CouncilVote('offline-d', CouncilVoteStance.DISSENT, 'offline-fixture-c', 'Trusted stream origin is unresolved.', ('Origin is unbound.',), ('Hold promotion until origin is bound.',)),
)
base = record_council_deliberation('offline-vote-1', 'offline-proposal-1', 'Local invariant regression fixture; no real Council or provider', votes, cas=cas)
original_dissent = base.votes[2]
def with_dissent_field(**changes):
    altered = dataclasses.replace(original_dissent, **changes)
    return dataclasses.replace(base, votes=base.votes[:2]+(altered,), dissenting_opinions=(altered,))
absent = 'f'*64
assert not cas.has(absent)
nonobject_hash = cas.put(b'[]')
nonobject_record = record_council_deliberation('offline-nonobject-1', base.proposal_id, base.topic, votes[:2]+(dataclasses.replace(votes[2], dissent_cas_hash=nonobject_hash),), cas=cas)
case_specs = [
    ('valid_control', base, [], True, 'Unmodified real-recorder output.'),
    ('stance_tampered', with_dissent_field(stance=CouncilVoteStance.REJECT), ['votes[2].stance', 'dissenting_opinions[0].stance'], False, 'One logical vote field changed consistently in both views; original dissent and whole-record CAS retained.'),
    ('risks_tampered', with_dissent_field(risks_identified=('Different unreviewed risk.',)), ['votes[2].risks_identified', 'dissenting_opinions[0].risks_identified'], False, 'One logical vote field changed consistently in both views; original CAS retained.'),
    ('alternatives_tampered', with_dissent_field(suggested_alternatives=('Ship without binding.',)), ['votes[2].suggested_alternatives', 'dissenting_opinions[0].suggested_alternatives'], False, 'One logical vote field changed consistently in both views; original CAS retained.'),
    ('whole_record_hash_absent', dataclasses.replace(base, vote_cas_hash=absent), ['vote_cas_hash'], False, 'Valid-format hash known absent from this real CAS.'),
    ('dissent_list_stance_only', dataclasses.replace(base, dissenting_opinions=(dataclasses.replace(original_dissent, stance=CouncilVoteStance.APPROVE),)), ['dissenting_opinions[0].stance'], False, 'Vote remains DISSENT while its dissent-list copy becomes APPROVE.'),
    ('dissent_list_duplicate', dataclasses.replace(base, dissenting_opinions=(original_dissent, original_dissent)), ['dissenting_opinions'], False, 'Duplicate dissent entry; original whole-record CAS retained.'),
    ('nonobject_presupplied_payload', nonobject_record, ['votes[2].dissent_cas_hash'], False, 'Real recorder accepts pre-supplied existing CAS payload [] and creates a fresh whole-record hash.'),
    ('argument_mismatch_rejection_control', with_dissent_field(argument='A different argument.'), ['votes[2].argument','dissenting_opinions[0].argument'], False, 'Known checked field changed while original CAS retained.'),
    ('omission_rejection_control', dataclasses.replace(base, dissenting_opinions=()), ['dissenting_opinions'], False, 'Dissent voter omitted from list.'),
    ('missing_dissent_blob_rejection_control', with_dissent_field(dissent_cas_hash=absent), ['votes[2].dissent_cas_hash','dissenting_opinions[0].dissent_cas_hash'], False, 'Dissent digest points to absent CAS blob.'),
]
reopened = CAS(FilesystemCasStore(ROOT/'cas'))
results=[]
for name, record, fields, valid, explanation in case_specs:
    violations = verify_council_deliberation_invariants(record, cas=cas)
    after_reopen = verify_council_deliberation_invariants(record, cas=reopened)
    results.append({'case':name,'expected_valid':valid,'violations':violations,'accepted':not violations,'reopened_violations':after_reopen,'reopen_agrees':violations==after_reopen,'changed_fields':fields,'explanation':explanation,'record':dataclasses.asdict(record)})
raw_record=cas.get(base.vote_cas_hash)
stored_record=json.loads(raw_record)
raw_dissent=cas.get(original_dissent.dissent_cas_hash)
canonical=base.to_dict(); canonical['vote_cas_hash']=''
expected_accepted={name for name, *_ in case_specs[:8]}
for item in results:
    assert item['accepted'] == (item['case'] in expected_accepted), item['case']
    assert item['reopen_agrees'], item['case']
assert stored_record['vote_cas_hash']==''
assert raw_record == json.dumps(canonical, sort_keys=True).encode('utf-8')
assert hashlib.sha256(raw_record).hexdigest()==base.vote_cas_hash
assert hashlib.sha256(raw_dissent).hexdigest()==original_dissent.dissent_cas_hash
final_pins=pins()
assert initial_pins==final_pins
result={
    'evidence_kind':'Offline baseline regression; not implementation, actual Council decision, admission, provider qualification, or runtime success.',
    'imports': {name: str(Path(sys.modules[name].__file__).resolve()) for name in ['kernel.cas','runtime.critique']},
    'source_unchanged':initial_pins==final_pins,
    'temporary_cas_root':str(ROOT/'cas'),
    'network_or_process_attempts_blocked':blocked_events,
    'canonical_self_hash_field':'vote_cas_hash="" in stored whole-record bytes',
    'whole_record_hash':base.vote_cas_hash,
    'dissent_hash':original_dissent.dissent_cas_hash,
    'stored_dissent_payload':json.loads(raw_dissent),
    'whole_record_cas_verified':hashlib.sha256(raw_record).hexdigest()==base.vote_cas_hash,
    'dissent_cas_verified':hashlib.sha256(raw_dissent).hexdigest()==original_dissent.dissent_cas_hash,
    'whole_record_dissent_list_omits_risks_and_alternatives': all(k not in stored_record['dissenting_opinions'][0] for k in ['risks_identified','suggested_alternatives']),
    'invalid_cases_accepted':sum(not x['expected_valid'] and x['accepted'] for x in results),
    'rejection_controls_rejected':sum(x['case'].endswith('rejection_control') and not x['accepted'] for x in results),
    'cases':results,
}
(ROOT/'result.json').write_text(json.dumps(result, indent=2)+'\n')
for item in results:
    print(item['case']+': '+('ACCEPTED' if item['accepted'] else 'REJECTED')+' '+json.dumps(item['violations']))
print('INVALID_CASES_ACCEPTED='+str(result['invalid_cases_accepted']))
print('REJECTION_CONTROLS_REJECTED='+str(result['rejection_controls_rejected']))
print('SOURCE_UNCHANGED='+str(result['source_unchanged']))
print('NETWORK_OR_PROCESS_ATTEMPTS_BLOCKED='+json.dumps(blocked_events))
print('RESULT='+str(ROOT/'result.json'))
