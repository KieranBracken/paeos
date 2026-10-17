from pathlib import Path
import hashlib,json,sqlite3
root=Path(__file__).resolve().parent
sha=lambda b:hashlib.sha256(b).hexdigest()
for e in json.loads((root/"ARCHIVE_SOURCES.json").read_text()):
 p=root/e["archive"]; assert p.stat().st_size==e["size"] and sha(p.read_bytes())==e["sha256"]
v=json.loads((root/"VERIFICATION.json").read_text())
s=json.loads((root/"SOURCE_VERIFICATION.json").read_text())
assert s["declared_file_count"]==903 and s["verified_match_count"]==903
assert all(x["match"] for x in s["files"])
con=sqlite3.connect((root/"state/ledger.db").as_uri()+"?mode=ro&immutable=1",uri=True); con.row_factory=sqlite3.Row
assert con.execute("pragma integrity_check").fetchone()[0]=="ok"
rows=list(con.execute("select * from ledger_rows order by seq")); prev=sha(b"PAEOS-LEDGER-GENESIS/v1")
for i,row in enumerate(rows,1):
 r=dict(row); assert r["seq"]==i and r["prev_hash"]==prev
 body={k:r[k] for k in ("prev_hash","seq","timestamp","schema_ver","kind","domain_tag")}; body["payload"]=json.loads(r["payload"])
 prev=sha(json.dumps(body,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode("ascii")); assert prev==r["row_hash"] and r["domain_tag"]=="PRODUCTION"
assert len(rows)==v["ledger_rows"] and prev==v["ledger_head"]
for p in (root/"state/cas").rglob("*"):
 if p.is_file(): assert "".join(p.relative_to(root/"state/cas").parts)==sha(p.read_bytes())
print(json.dumps({"result":"PASS","archive_files":len(json.loads((root/"ARCHIVE_SOURCES.json").read_text())),"source_hashes":903,"ledger_rows":len(rows),"ledger_head":prev,"cas_objects":v["cas_objects"]}))
