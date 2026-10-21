import fcntl,json,pathlib,subprocess,sys,time
out=pathlib.Path(__file__).parent
name,*args=sys.argv[1:]
start=time.time()
with (out.parent.parent/'heavy-test.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 r=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
(out/(name+'.log')).write_text(r.stdout)
(out/(name+'.json')).write_text(json.dumps({'command':args,'exit_code':r.returncode,'seconds':round(time.time()-start,3)},indent=2)+'\n')
print(r.stdout[-3500:]);print('EXIT',r.returncode)
sys.exit(r.returncode)
