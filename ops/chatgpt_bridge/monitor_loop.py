#!/usr/bin/env python3
"""
PAEOS Bridge Monitor Loop
Watches Cline terminal -> sends to ChatGPT -> pastes response back. Runs continuously.
"""
import base64, hashlib, json, re, subprocess, sys, time, threading
from datetime import datetime
from pathlib import Path

try:
    import requests, websocket
except ImportError:
    subprocess.check_call([sys.executable,"-m","pip","install","requests","websocket-client","-q"])
    import requests, websocket

REPO_ROOT      = Path("/Users/bob/GitHub/paeos")
RESPONSE_FILE  = REPO_ROOT/"ops"/"chatgpt_bridge"/"chatgpt_response.md"
SENT_HASH_FILE = REPO_ROOT/"ops"/"chatgpt_bridge"/".last_sent_hash"
LOG_FILE       = REPO_ROOT/"ops"/"chatgpt_bridge"/"bridge_monitor.log"
POLL_INTERVAL  = 20    # seconds between checks
IDLE_THRESHOLD = 45    # seconds idle before considering Cline paused
CHROME_URL     = "http://127.0.0.1:9222"
CLINE_CLICK_X  = 340   # screen coords of Cline "Ask anything..." input
CLINE_CLICK_Y  = 822

PAUSE_MARKERS = [
    "ask anything","do you want to proceed","please choose","[y/n]",
    "task completed","i need clarification","which option",
    "waiting for","error occurred","what would you like",
]

SCAN_DIRS = [
    REPO_ROOT/"architecture", REPO_ROOT/"design", REPO_ROOT/"proposals",
    REPO_ROOT/"backlog"/"research", REPO_ROOT/"runtime", REPO_ROOT/"kernel",
]

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE,"a") as f: f.write(line+"\n")

def content_hash(text): return hashlib.sha256(text.encode()).hexdigest()[:16]
def get_last_sent_hash(): return SENT_HASH_FILE.read_text().strip() if SENT_HASH_FILE.exists() else ""
def save_sent_hash(h): SENT_HASH_FILE.write_text(h)

CLINE_LOG = Path("/Users/bob/GitHub/paeos/ops/chatgpt_bridge/cline_output.log")

def read_cline_terminal_text() -> str:
    """
    Prefer the log file (full history, reliable mtime for stuck detection).
    Fall back to AppleScript terminal buffer if no log file exists yet.
    """
    if CLINE_LOG.exists() and CLINE_LOG.stat().st_size > 0:
        # Read last 8000 chars from the log file — full context, not just screen
        text = CLINE_LOG.read_text(errors="replace")
        if len(text) > 8000:
            text = "...[earlier output clipped]...\n\n" + text[-8000:]
        return text

    # Fallback: AppleScript (visible screen only — limited but better than nothing)
    script = '''tell application "Terminal"
        set tabText to ""
        repeat with w in windows
            repeat with t in tabs of w
                set tabText to contents of t
                exit repeat
            end repeat
            if tabText is not "" then exit repeat
        end repeat
        return tabText
    end tell'''
    try:
        r = subprocess.run(["osascript","-e",script], capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception as e:
        log(f"Terminal read error: {e}"); return ""

def get_cline_last_activity_minutes() -> float:
    """
    Best available measure of when Cline last produced output.
    Uses log file mtime if available, otherwise git working tree age.
    """
    if CLINE_LOG.exists() and CLINE_LOG.stat().st_size > 0:
        return (time.time() - CLINE_LOG.stat().st_mtime) / 60
    # Fall back to git-based activity
    try:
        r = subprocess.run(
            ["git","-C",str(REPO_ROOT),"status","--short"],
            capture_output=True, text=True, timeout=5
        )
        changed = [l[3:].strip() for l in r.stdout.splitlines()
                   if l.strip() and "chatgpt_bridge" not in l]
        if changed:
            latest = max(
                (REPO_ROOT/f).stat().st_mtime
                for f in changed[:10] if (REPO_ROOT/f).exists()
            )
            return (time.time() - latest) / 60
    except Exception:
        pass
    return 0.0

def is_cline_paused(text):
    recent = text.lower()[-500:]
    return any(m in recent for m in PAUSE_MARKERS)

def get_repo_last_modified():
    latest = 0.0
    try:
        r = subprocess.run(
            ["find",str(REPO_ROOT),"-not","-path","*/.git/*","-not","-path","*/__pycache__/*",
             "-newer",str(REPO_ROOT/".git"/"HEAD"),"-type","f"],
            capture_output=True, text=True, timeout=10)
        for line in r.stdout.strip().splitlines():
            try:
                mtime = Path(line).stat().st_mtime
                if mtime > latest: latest = mtime
            except: pass
    except: pass
    return latest if latest > 0 else time.time()

def get_recently_modified_files(since=300):
    cutoff = time.time()-since; found = []
    for d in SCAN_DIRS:
        if not d.exists(): continue
        for f in d.rglob("*"):
            if f.is_file() and f.suffix in (".md",".py",".json",".txt"):
                try:
                    if f.stat().st_mtime > cutoff: found.append(f)
                except: pass
    return sorted(found, key=lambda f: f.stat().st_mtime, reverse=True)[:5]

def strip_ansi(text):
    return re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])').sub('',text)

def build_message(terminal_text, recent_files):
    clean = strip_ansi(terminal_text)
    if len(clean) > 5000: clean = "...[clipped]...\n\n"+clean[-5000:]
    parts = ["## Cline/DeepSeek Terminal Output\n","```\n"+clean.strip()+"\n```\n"]
    if recent_files:
        parts.append("\n## Recently Modified PAEOS Files\n")
        for f in recent_files[:3]:
            try:
                c = f.read_text(); preview = c[:1500]+("\n...[truncated]" if len(c)>1500 else "")
                parts.append(f"\n### `{f.relative_to(REPO_ROOT)}`\n```\n{preview}\n```\n")
            except: pass
    parts.append("\n---\n*PAEOS Bridge — Senior Architect review requested.*")
    return "\n".join(parts)

class CDPBridge:
    def __init__(self):
        self.ws=None; self._msgs={}; self._lock=threading.Lock(); self._id=0

    def connect(self):
        try: tabs = requests.get(f"{CHROME_URL}/json",timeout=5).json()
        except Exception as e: log(f"Chrome unreachable: {e}"); return False
        tab = next((t for t in tabs if "chatgpt" in t.get("url","")),None)
        if not tab: log("No ChatGPT tab found"); return False
        try: self.ws = websocket.create_connection(tab["webSocketDebuggerUrl"],timeout=15)
        except Exception as e: log(f"WS connect failed: {e}"); return False
        def _listen():
            while self.ws:
                try:
                    d=json.loads(self.ws.recv())
                    if "id" in d:
                        with self._lock: self._msgs[d["id"]]=d
                except: break
        threading.Thread(target=_listen,daemon=True).start()
        log(f"CDP connected: {tab['url'][:70]}"); return True

    def _send(self,method,params=None,timeout=10):
        with self._lock: self._id+=1; tid=self._id
        self.ws.send(json.dumps({"id":tid,"method":method,"params":params or {}}))
        deadline=time.time()+timeout
        while time.time()<deadline:
            with self._lock:
                if tid in self._msgs: return self._msgs.pop(tid)
            time.sleep(0.05)
        return {}

    def js(self,expr,timeout=10):
        r=self._send("Runtime.evaluate",{"expression":expr,"returnByValue":True,"awaitPromise":True},timeout=timeout)
        return r.get("result",{}).get("result",{}).get("value")

    def send_to_chatgpt(self,message):
        escaped=json.dumps(message)
        ok=self.js(f"""(function(){{
            const el=document.querySelector('#prompt-textarea')||document.querySelector('textarea');
            if(!el) return false;
            el.focus();
            const s=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value');
            if(s&&s.set) s.set.call(el,{escaped}); else el.textContent={escaped};
            el.dispatchEvent(new Event('input',{{bubbles:true}}));
            el.dispatchEvent(new Event('change',{{bubbles:true}}));
            return true;
        }})()""")
        if not ok: log("Could not fill ChatGPT input"); return False
        time.sleep(0.6)
        self.js("""(function(){
            const btn=document.querySelector('[data-testid="send-button"]')||
                      [...document.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')?.toLowerCase().includes('send'));
            if(btn) btn.click();
        })()""")
        log("Sent to ChatGPT ✓"); return True

    def wait_for_response(self,timeout=180):
        log("Waiting for ChatGPT..."); deadline=time.time()+timeout
        last_text=None; stable=0
        while time.time()<deadline:
            generating=self.js("!!document.querySelector('[data-testid=\"stop-button\"]')")
            text=self.js("""(function(){
                const m=document.querySelectorAll('[data-message-author-role="assistant"]');
                return m.length?m[m.length-1].innerText:null;
            })()""")
            if not generating and text and text==last_text:
                stable+=1
                if stable>=3: log(f"Response done ({len(text)} chars) ✓"); return text
            else: stable=0; last_text=text
            time.sleep(1.0)
        log("Timed out"); return last_text

def paste_to_cline(text):
    subprocess.run(["pbcopy"],input=text.encode(),check=True); time.sleep(0.3)
    script=f'''tell application "Terminal" to activate
delay 0.8
tell application "System Events"
    click at {{{CLINE_CLICK_X},{CLINE_CLICK_Y}}}
    delay 0.4
    keystroke "v" using {{command down}}
end tell'''
    r=subprocess.run(["osascript","-e",script],capture_output=True,text=True)
    log("Pasted into Cline ✓" if r.returncode==0 else f"Paste error: {r.stderr.strip()}")

def main():
    log("="*50)
    log("  PAEOS Bridge Monitor — starting")
    log(f"  Poll:{POLL_INTERVAL}s  Idle threshold:{IDLE_THRESHOLD}s")
    log("="*50)
    cdp=CDPBridge()
    if not cdp.connect(): log("ERROR: Could not connect to ChatGPT"); sys.exit(1)
    last_repo_change=time.time()
    while True:
        try:
            terminal_text=read_cline_terminal_text()
            if not terminal_text:
                log("Cannot read terminal — retrying"); time.sleep(POLL_INTERVAL); continue

            current_hash=content_hash(terminal_text)
            repo_latest=get_repo_last_modified()
            if repo_latest>last_repo_change:
                last_repo_change=repo_latest
                log("Repo active — Cline working..."); time.sleep(POLL_INTERVAL); continue

            idle_secs=time.time()-last_repo_change
            paused=is_cline_paused(terminal_text)

            if not paused or idle_secs<IDLE_THRESHOLD:
                log(f"Watching... (idle {idle_secs:.0f}s, paused={paused})")
                time.sleep(POLL_INTERVAL); continue

            if current_hash==get_last_sent_hash():
                log("No new content since last send"); time.sleep(POLL_INTERVAL); continue

            recent_files=get_recently_modified_files()
            if recent_files: log(f"Including files: {[f.name for f in recent_files]}")

            message=build_message(terminal_text,recent_files)
            log(f"Sending {len(message)} chars to ChatGPT...")
            if not cdp.send_to_chatgpt(message):
                time.sleep(POLL_INTERVAL); continue
            save_sent_hash(current_hash)

            response=cdp.wait_for_response(timeout=180)
            if not response: time.sleep(POLL_INTERVAL); continue

            ts=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            RESPONSE_FILE.write_text(f"# ChatGPT Response\n*{ts}*\n\n{response}\n")
            log(f"Saved response")
            paste_to_cline(response)
            log("Cycle complete ✓ — resuming watch\n")

        except KeyboardInterrupt: log("Stopped."); break
        except Exception as e: log(f"Loop error: {e}"); time.sleep(POLL_INTERVAL)

if __name__=="__main__": main()
