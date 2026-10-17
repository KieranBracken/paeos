"""Independent source-only verifier; no candidate or canonical source writes."""
import dataclasses
import hashlib
import importlib
import json
import multiprocessing
from pathlib import Path
import sys
import tempfile

ROOT = Path('/private/tmp/paeos-source-construction-v4.J5rMbO/state/workspaces/paeos-t-c42817849cc7-bridge-zptqjx58')
sys.path.insert(0, str(ROOT))
t = importlib.import_module('tests.runtime.test_scope_supersession')
api = importlib.import_module('runtime.scope_supersession')
from kernel.capability import CapabilityVerifier
from kernel.cas import CAS, FilesystemCasStore
from kernel.ledger import Ledger
from kernel.ledger_sqlite import SqliteLedgerStore
from kernel.types import DomainTag

for name in ('runtime.scope_supersession','runtime.implementation_contract','kernel.ledger','kernel.ledger_sqlite','kernel.capability','kernel.cas','kernel.types'):
    assert Path(importlib.import_module(name).__file__).resolve().is_relative_to(ROOT)

def files(path):
    return {str(p.relative_to(path)):hashlib.sha256(p.read_bytes()).hexdigest() for p in path.rglob('*') if p.is_file()}

def run_case(base, name, check):
    path=base/name
    path.mkdir()
    setup=t.case.__wrapped__(path)
    c=next(setup)
    try:
        check(c)
        print(json.dumps({'control':name,'result':'PASS'}),flush=True)
    finally:
        try: next(setup)
        except StopIteration: pass

def future_capability(c):
    before=files(c.path.parent/'cas')
    authority=t.token(c, issued_seq=2)
    try: t.service(c).consume(c.request, authority)
    except api.SupersessionError: pass
    else: raise AssertionError('future-issued capability accepted')
    assert c.ledger.read()==[]
    assert files(c.path.parent/'cas')==before

def refreshed_replay(c):
    prior=files(c.path.parent/'cas')
    t.service(c).consume(c.request,t.token(c))
    c.ledger.close(); c.store.close()
    c.store=SqliteLedgerStore(c.path)
    c.ledger=Ledger(c.store,writer_id='scope-test')
    request=dataclasses.replace(c.request,expected_head_hash=c.ledger.head_hash())
    try: t.service(c).consume(request,t.token(c,request))
    except api.SupersessionError: pass
    else: raise AssertionError('same transaction accepted after refresh and resign')
    assert len(c.ledger.read())==1
    after=files(c.path.parent/'cas')
    assert all(after.get(p)==h for p,h in prior.items())
    c.ledger.verify_chain()

def corrupted_chain(c):
    t.service(c).consume(c.request,t.token(c))
    import sqlite3
    with sqlite3.connect(c.path) as db:
        db.execute("UPDATE ledger_rows SET row_hash = ? WHERE seq = 1",('f'*64,))
    before=files(c.path.parent/'cas')
    request=dataclasses.replace(c.request,transaction_id='next',expected_head_hash='f'*64)
    try: t.service(c).consume(request,t.token(c,request))
    except api.SupersessionError: pass
    else: raise AssertionError('corrupt historical chain accepted')
    assert len(c.ledger.read())==1
    assert files(c.path.parent/'cas')==before

def controller(path, request, authority, key, barrier, queue):
    store=SqliteLedgerStore(path)
    class SynchronizedLedger(Ledger):
        def append_once_if_new(self,*args,**kwargs):
            barrier.wait(10)
            return super().append_once_if_new(*args,**kwargs)
    ledger=SynchronizedLedger(store,writer_id='scope-test')
    try:
        service=api.ScopeSupersessionService(cas=CAS(FilesystemCasStore(Path(path).parent/'cas')),
            ledger=ledger,verifier=CapabilityVerifier(bytes.fromhex(key)),goal_id='goal-1',
            run_id='run-1',session='ratifier-session',domain=DomainTag.TEST,policy_ref=request.policy_ref)
        try:
            receipt=service.consume(request,authority)
            queue.put(('consumed',receipt.row.seq))
        except api.SupersessionError as exc: queue.put(('denied',type(exc).__name__))
        except Exception as exc: queue.put(('unexpected',repr(exc)))
    finally:
        ledger.close();store.close()

def process_race(c):
    prior=files(c.path.parent/'cas')
    authority=t.token(c)
    key=c.broker.verify_key_hex
    c.ledger.close();c.store.close()
    ctx=multiprocessing.get_context('fork')
    barrier=ctx.Barrier(2); queue=ctx.Queue()
    children=[ctx.Process(target=controller,args=(str(c.path),c.request,authority,key,barrier,queue)) for _ in range(2)]
    for child in children: child.start()
    for child in children: child.join(20)
    assert all(not child.is_alive() and child.exitcode==0 for child in children)
    results=[queue.get(timeout=5) for _ in children]
    assert sorted(result[0] for result in results)==['consumed','denied'],results
    c.store=SqliteLedgerStore(c.path);c.ledger=Ledger(c.store,writer_id='scope-test')
    rows=c.ledger.read()
    assert len(rows)==1 and rows[0].domain_tag=='TEST'
    assert rows[0].event.payload['status']==api.PENDING
    c.ledger.verify_chain()
    after=files(c.path.parent/'cas')
    assert all(after.get(p)==h for p,h in prior.items())
    for field in ('request_ref','authority_token_ref'):
        assert c.cas.get(rows[0].event.payload[field])
    print(json.dumps({'race':'separate_processes_separate_sqlite_and_filesystem_cas','results':results}),flush=True)

with tempfile.TemporaryDirectory(prefix='paeos-independent-supersession-data-') as temp:
    base=Path(temp)
    run_case(base,'future_capability_no_effect',future_capability)
    run_case(base,'reopen_refreshed_head_same_transaction_denied',refreshed_replay)
    run_case(base,'corrupted_history_no_effect',corrupted_chain)
    run_case(base,'real_process_race',process_race)
print(json.dumps({'mode':'SOURCE_CONSTRUCTION_ONLY','independent_controls_passed':4,'production_qualification':False,'candidate_root':str(ROOT)}))
