from pathlib import Path
import hashlib, json, shutil, subprocess, tempfile, time
base = Path(__file__).resolve().parent
run = Path(tempfile.mkdtemp(prefix="replay-", dir=base))
shutil.copy2(base / "baseline.py", run / "baseline.py")
shutil.copytree(base / "data-gym-cache", run / "data-gym-cache")
argv = ["/Users/bob/GitHub/paeos/.venv/bin/python", "-I", "-B", str(run / "baseline.py"), str(run)]
env = {"PATH":"/usr/bin:/bin:/usr/sbin:/sbin", "TMPDIR":str(run), "XDG_CACHE_HOME":str(run / "cache"), "LITELLM_LOCAL_MODEL_COST_MAP":"True", "LITELLM_TELEMETRY":"False", "DO_NOT_TRACK":"1"}
receipt = {"argv":argv, "cwd":str(run), "environment":env, "started_unix":time.time()}
with (run / "stdout.txt").open("wb") as out, (run / "stderr.txt").open("wb") as err:
    completed = subprocess.run(argv, cwd=run, env=env, stdout=out, stderr=err, timeout=90)
receipt.update(exit_code=completed.returncode, ended_unix=time.time())
for name in ("stdout.txt", "stderr.txt", "baseline.py"):
    receipt[name + "_sha256"] = hashlib.sha256((run / name).read_bytes()).hexdigest()
(run / "RUN.receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
print((run / "stdout.txt").read_text())
print("Evidence:", run)
raise SystemExit(completed.returncode)
