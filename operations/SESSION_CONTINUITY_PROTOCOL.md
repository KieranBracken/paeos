# PAEOS Session Continuity & Rotation Protocol

**Document Version:** 1.0 (Operational Runtime Rule)  
**Scope:** Browser Architect sessions (ChatGPT) and Worker sessions (Cline)  
**Purpose:** Prevent context saturation, ineffective compaction, stale-context reasoning, and long-session degradation without losing canonical PAEOS state.  
**Principle:**
> *Conversations are disposable execution contexts. PAEOS canonical state is persistent and must survive conversation replacement.*

Browser ChatGPT and Cline sessions MUST therefore be rotated automatically when their context health becomes materially degraded. This protocol does NOT modify the PAEOS constitutional lifecycle or source hierarchy.

---

## 1. Session Roles

```
                 CHATGPT BROWSER
                 GPT-5.6 Sol
                 ARCHITECT
                      │
                      │ Bridge Watchdog & Continuity Handoff
                      ▼
                ANTIGRAVITY
             supervisor / overseer
                      │
                      ▼
                    CLINE
               EXECUTION WORKER
                      │
                      │ model="paeos-code"
                      ▼
                PAEOS ROUTER
              127.0.0.1:4000/v1
           ┌──────────┼──────────┐
           ▼          ▼          ▼
        Gemini     MiniMax     Kilo / etc.
```

* **Architect Session (Browser ChatGPT GPT-5.6 Sol):** Responsible for architectural reasoning, bounded instructions, review, remand, sealing decisions, and architectural ambiguity resolution.
* **Overseer (Antigravity):** Owns session-health monitoring, handoffs, bridge control, rotation, evidence packaging, and continuity verification.
* **Worker Session (Cline):** Executes bounded work using `model = paeos-code` on `http://127.0.0.1:4000/v1`. Physical inference models are dynamically selected by the PAEOS router.

---

## 2. Core Continuity Invariant

**No architectural or worker state may exist ONLY inside a conversation.**

Before any session can be discarded, all material state required to continue must exist in repository/runtime artifacts. At minimum preserve:
* Repository HEAD & working-tree status;
* Canonical authority hierarchy;
* Currently sealed steps & active bounded step;
* Exact current objective;
* Architectural decisions already made;
* Invariants relevant to the current work;
* Files changed & test/evidence state;
* Unresolved questions, remands, and debt;
* Next intended action;
* Bridge/session identifiers.

A new conversation must never be expected to reconstruct these from memory.

---

## 3. Session Health States & Signals

Antigravity independently tracks health for `ARCHITECT_SESSION` and `WORKER_SESSION`:
* **`HEALTHY`**: Normal execution context.
* **`ROTATE_AFTER_STEP`**: Degraded or saturated; complete current bounded step, checkpoint, and rotate before the next step.
* **`ROTATE_NOW`**: Immediate context limit or severe degradation; checkpoint partial state and rotate immediately.
* **`FAILED`**: Session unrecoverable/corrupted; halt affected lane, preserve the other lane, and rotate.

### Rotation Signals:
1. **Context Saturation:** Explicit context-window warning, compression notifications, aggressive truncation.
2. **Compression Degradation:** Previously settled decisions repeatedly need re-explaining; important constraints disappear from summaries.
3. **Reasoning Degradation:** Reopening settled questions without new evidence, confusing superseded vs canonical artifacts, repeated forgetting of active instructions.
4. **Operational Degradation:** Unreliable browser DOM, bridge extraction slowdowns, tool history bloat.
5. **Hard Failure:** Context limit prevents continuation, bridge response identification failure.

---

## 4. Rotation Execution Rules

1. **Never Rotate Mid-Boundary Without Need:** Preferred rotation boundary is after a bounded task completes, evidence is collected, and the state checkpoint is written.
2. **One Side at a Time:** Rotate Architect and Worker independently (never simultaneously unless both have independently failed).
3. **Architect Handoff Artifact:** Must write `.paeos_state/architect/ARCHITECT_HANDOFF_CURRENT.md` before rotating Browser ChatGPT.
4. **Worker Handoff Artifact:** Must write `.paeos_state/worker/WORKER_HANDOFF_CURRENT.md` before rotating Cline.
5. **Acceptance & Continuity Check:** A new session must explicitly acknowledge canonical lifecycle authority, current sealed step, active step, and next action with a sentinel probe before retirement of the predecessor.
6. **Session Registry:** Maintained in `.paeos_state/session_registry.json`.

---

## 5. Critical Separation

Conversation rotation changes **EXECUTION CONTEXT only**. It does NOT change:
* Constitutional authority (`ENGINEERING_LIFECYCLE.md` v1.3 prevails);
* Repository state;
* Lifecycle stage / step progress;
* Certification status;
* Architectural decisions or debt ledger;
* Founder authority.
