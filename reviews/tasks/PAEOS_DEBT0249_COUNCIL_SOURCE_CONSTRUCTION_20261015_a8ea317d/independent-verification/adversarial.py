import ast, dataclasses, hashlib, importlib, json, pathlib, sys, tempfile
root=pathlib.Path('/private/tmp/paeos-source-construction-d0249-p2z_vhfs/state/candidate')
sys.path.insert(0,str(root))
import pytest
import kernel.cas as kc
import runtime.critique as cr
from dataclasses import replace
from kernel.cas import CAS, FilesystemCasStore, InMemoryCasStore
from runtime.critique import *
origins={m.__name__:str(pathlib.Path(m.__file__).resolve()) for m in (kc,cr)}
assert all(pathlib.Path(v).is_relative_to(root) for v in origins.values())
print(json.dumps({'import_origins':origins},sort_keys=True))
source=pathlib.Path('/Users/bob/GitHub/paeos/tests/runtime/test_executable_law_canaries.py')
s=source.read_text(); f=next(n for n in ast.parse(s).body if isinstance(n,ast.FunctionDef) and n.name=='test_nc_council_01_dissension_suppression_and_consensus_as_evidence_rejected')
exec(compile(ast.Module(body=[f],type_ignores=[]),str(source),'exec'),globals())
globals()[f.name]()
print('NC-COUNCIL-01 AST-only: PASS; source sha256='+hashlib.sha256(source.read_bytes()).hexdigest())
def rebind(cas,r):
    payload=r.to_dict(); payload['vote_cas_hash']=''
    return replace(r,vote_cas_hash=cas.put(json.dumps(payload,sort_keys=True).encode()))
with tempfile.TemporaryDirectory(prefix='council-independent-cas-') as t:
    cas=CAS(FilesystemCasStore(pathlib.Path(t)))
    votes=(CouncilVote('a',CouncilVoteStance.APPROVE,'f1','accept'),CouncilVote('b',CouncilVoteStance.REJECT,'f2','risk B',('B',),('fix B',)),CouncilVote('c',CouncilVoteStance.DISSENT,'f3','risk C',('C',),('fix C',)))
    r=record_council_deliberation('v','p','topic',votes,cas)
    cas=CAS(FilesystemCasStore(pathlib.Path(t)))
    assert verify_council_deliberation_invariants(r,cas)==[]
    assert verify_council_deliberation_invariants(rebind(cas,replace(r,dissenting_opinions=tuple(reversed(r.dissenting_opinions)))),cas)==[]
    changed=replace(r,votes=(replace(r.votes[0],argument='tampered approve'),*r.votes[1:]))
    assert any('VOTE_CAS_CONTENT_MISMATCH' in x for x in verify_council_deliberation_invariants(changed,cas))
    for mode in ('missing_key','extra_key','bool_risk','swap_hash'):
        d=r.votes[1]
        if mode=='swap_hash': d=replace(d,dissent_cas_hash=r.votes[2].dissent_cas_hash)
        else:
            payload=json.loads(cas.get(d.dissent_cas_hash))
            if mode=='missing_key': del payload['alternatives']
            elif mode=='extra_key': payload['unbound']='extra'
            else: payload['risks']=[True]
            d=replace(d,dissent_cas_hash=cas.put(json.dumps(payload).encode()))
        forged=rebind(cas,replace(r,votes=(r.votes[0],d,r.votes[2]),dissenting_opinions=(d,r.votes[2])))
        assert verify_council_deliberation_invariants(forged,cas),mode
        with pytest.raises(CouncilDissensionViolationError): record_council_deliberation('v','p','topic',forged.votes,cas)
print('Independent FS CAS: reopen, mixed reject/dissent and reordering controls, approve tampering, missing/extra keys, boolean risk, swapped dissent hashes: PASS')
