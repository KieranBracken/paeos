from pathlib import Path
import hashlib,json,sqlite3
root=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
v=json.loads((root/'VERIFICATION.json').read_text())
con=sqlite3.connect((root/'state/ledger.db').as_uri()+'?mode=ro&immutable=1',uri=True)
con.row_factory=sqlite3.Row
assert con.execute('pragma integrity_check').fetchone()[0]=='ok'
prev=sha(b'PAEOS-LEDGER-GENESIS/v1'); rows=list(con.execute('select * from ledger_rows order by seq'))
for i,row in enumerate(rows,1):
 r=dict(row);assert r['seq']==i and r['prev_hash']==prev
 body={k:r[k] for k in ('prev_hash','seq','timestamp','schema_ver','kind','domain_tag')};body['payload']=json.loads(r['payload'])
 prev=sha(json.dumps(body,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii'))
 assert prev==r['row_hash'] and r['domain_tag']=='PRODUCTION'
con.close()
assert len(rows)==v['ledger_rows'] and prev==v['ledger_head']
for e in json.loads((root/'ARCHIVE_SOURCES.json').read_text()):assert sha((root/e['archive']).read_bytes())==e['sha256']
for p in (root/'state/cas').rglob('*'):
 if p.is_file():assert ''.join(p.relative_to(root/'state/cas').parts)==sha(p.read_bytes())
assert len(list((root/'state/bridge/requests').glob('*.md')))==2
assert len(list((root/'state/bridge/responses').glob('*.md')))==1
assert not (root/'state/bridge/responses/r-29471672--t-c77ed9cdb294--ideate.response.md').exists()
print(json.dumps({'result':'PASS','rows':len(rows),'ledger_head':prev,'archived_sources':len(json.loads((root/'ARCHIVE_SOURCES.json').read_text()))}))
