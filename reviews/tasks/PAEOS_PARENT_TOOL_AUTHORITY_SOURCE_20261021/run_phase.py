import fcntl,hashlib,json,os,pathlib,subprocess,sys,time
out=pathlib.Path(__file__).resolve().parent
scope=json.loads((out/'SCOPE.json').read_text());root=pathlib.Path(scope['workspace'])
phase=sys.argv[1];assert phase in ('red','green','corrective')
record=out/(phase+'.json')
if record.exists():raise SystemExit('Phase already recorded; reconcile, do not retry')
scratch=out/('scratch-'+phase);scratch.mkdir();(scratch/'home').mkdir();(scratch/'tmp').mkdir()
profile='(version 1) (allow default) (deny network*) (deny file-write*) (allow file-write* (subpath '+json.dumps(str(scratch))+')) (allow file-write* (literal "/dev/null"))'
(out/(phase+'.sb')).write_text(profile+'\n')
args=['/usr/bin/sandbox-exec','-p',profile,str(root/'.venv/bin/python'),'-B','-m','pytest','-o','addopts=','-q','-p','no:cacheprovider','--noconftest','tests/runtime/autonomy/test_admission_authority.py']
if phase=='red':args+=['-k','parent_tool_claim_requires_dedicated_versioned_authority']
env=dict(os.environ,HOME=str(scratch/'home'),TMPDIR=str(scratch/'tmp'),XDG_CACHE_HOME=str(scratch/'home'),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONPATH=str(root))
meta={'phase':phase,'command':args,'cwd':str(root),'environment_overrides':{k:env[k] for k in ('HOME','TMPDIR','XDG_CACHE_HOME','PYTHONDONTWRITEBYTECODE','PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONPATH')},'source_sha256':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in scope['mutable_product_manifest']}}
with pathlib.Path(scope['budget']['heavy_test_lock']).open('a') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:raise SystemExit('HEAVY_TEST_LOCK_BUSY; no test started')
 meta['state']='STARTED';record.write_text(json.dumps(meta,indent=2)+'\n');t=time.monotonic()
 try:
  result=subprocess.run(args,cwd=root,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
  output=result.stdout;code=result.returncode
 except subprocess.TimeoutExpired as e:output=str(e.stdout);code='TIMEOUT'
 (out/(phase+'.log')).write_text(output);meta.update(state='FINISHED',exit_code=code,seconds=round(time.monotonic()-t,3));record.write_text(json.dumps(meta,indent=2)+'\n')
print(output[-7000:]);print('EXIT',code);sys.exit(code if isinstance(code,int) else 1)
