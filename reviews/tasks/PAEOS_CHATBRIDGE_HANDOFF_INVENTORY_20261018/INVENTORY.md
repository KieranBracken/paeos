# ChatBridge and native-chat handoff inventory

**Disposition:** `SOURCE_TRACE_COMPLETE_HANDOFF_NOT_ESTABLISHED`  
**Inspection date:** 2026-10-18  
**Repository:** `/Users/bob/.codex/worktrees/p1-bound-source-recovery/paeos`  
**Branch / base:** `codex/p1-bound-source-recovery-20261018` at `9241febef77028d638ed0da1444d029b73d998b7`  
**Method:** read-only source and coordination-record inspection; no PAEOS source was imported or executed.

## Finding

There are two different mechanisms that should not be conflated:

1. The native-chat completion protocol is an instructed coordinator loop. A worker is told to send one completion, blocker, or correction message to the coordinator after a material terminal result. The coordinator then validates the evidence and may send a bounded follow-up. An hourly reconciliation is a safety net. The protocol record labels the loop `ACTIVE_CALLBACK_LOOP_OBSERVED`, but it is not a PAEOS lifecycle event hook and does not itself prove that a PAEOS worker started, completed, passed review, or qualified.
2. The source-bound `ChatBridgeRuntime` writes an immutable prompt file and waits for a correlated response filename. In the inspected source tree, no UI receiver or external producer was found that writes that response file. The only located producer is a synthetic test helper. Therefore, a reply in a native chat cannot currently be joined to this runtime's response path from the inspected source alone.

The UI uploader is a separate, callable path: if invoked, it inserts caller-supplied text into the active Chrome tab and clicks its send button. It does not bind the active conversation to a PAEOS exchange, and its `files_to_attach` parameter is unused. Its command-line entrypoint only lists recent evidence filenames. The Codex authorization relay is another separate UI path: it watches a temporary prompt for a hash and submits application-generated “I authorize…” text into the active ChatGPT window. That text is not evidence of a human authorization, and the relay does not attach the bundle or bind a conversation.

## Source trace

### PAEOS runtime path

- `ops/autonomous_run.py:843-851` selects `ChatBridgeRuntime` only when `runtime_type` is `chat-bridge` or `antigravity`. `main()` defaults to `claude` when no runtime type is supplied (`:999-1024`), so ChatBridge is opt-in through this entrypoint.
- `runtime/integrations/chat_bridge.py:125-163` checks the package's capability binding, derives an exchange ID from run/task/stage, and chooses `state_root/bridge/requests/<exchange>.prompt.md` plus `state_root/bridge/responses/<exchange>.response.md`.
- `runtime/integrations/chat_bridge.py:181-218` constructs the task prompt, including the workspace path and response-file instruction, then writes the request once. This class does not invoke a browser, native chat API, or provider.
- `runtime/integrations/chat_bridge.py:220-290` polls for the response file, accepts any nonempty strict UTF-8 bytes, and returns `TaskStatus.COMPLETE`. The inspected code does not authenticate the response producer or validate a signed response envelope. A nonempty file is transport input, not proof of actual worker start or lifecycle qualification.
- `runtime/integrations/bridge_protocol.py:107-141` defines the request/response directories under the explicit state root; `:545-562` implements write-once file publication.

### Native UI paths

- `ops/chatgpt_bridge/upload_evidence.py:27-72` writes JavaScript to fixed `/tmp` files, activates Google Chrome, inserts `text_content` into the active front-window tab, then clicks a matching send button. It does not select or verify a conversation. The `files_to_attach` argument is unused. `:74-76` only prints recently found evidence filenames; it does not call the submit function.
- `ops/codex_auth_relay.py:18-36,56-88,97-98` finds a hash in a temporary prompt and, when it changes, sends a generated authorization-shaped message through AppleScript to the active ChatGPT window. This is not a human-origin authorization receipt and is not bound to the PAEOS response exchange.
- `ops/chatgpt_bridge/bridge.py:1-24`, `monitor_loop.py:1-23`, `cron_bridge.sh:1-7`, and `launch_chrome_debug.sh:1-7` are retired/disabled legacy bridge entrypoints. `watchdog_cron.sh:1-9` calls the run-once control-plane watchdog, not the old GUI bridge.
- `ops/chatgpt_bridge/watchdog.py:133-184` observes a compatibility file named `chatgpt_response.md`; this is not the canonical `state_root/bridge/responses/<exchange>.response.md` path.
- `ops/control_plane_watchdog.py:1-6,119-165` is a read-only liveness observer that emits a recovery proposal. It does not drive a browser, receive a native-chat response, or write the ChatBridge response file.

A source search across `ops/`, `runtime/`, and `tests/` found no caller of `submit_payload_to_chatgpt` or `check_and_authorize` outside their own script entrypoints, and no writer of the canonical `.response.md` path outside the ChatBridge test helper. This is bounded to the inspected source tree; it does not rule out an external manual invocation, launch agent, or untracked process.

### Test proof boundary

`tests/runtime/test_chat_bridge_fail_closed.py:73-85` implements `_respond_after_prompt`, a local synthetic thread that writes supplied bytes after seeing the prompt file. `:98-136` exercises that helper and confirms the runtime reports `COMPLETE`. Other tests cover stale responses, duplicate exchanges, capability/session mismatch, timeout without retry, and malformed response quarantine (`:182-328`). These tests establish local file-protocol behavior only. They do not exercise ChatGPT/Codex UI, a real provider, attachments, the uploader, the authorization relay, or authenticated receiver-start evidence. No `tests/ops/test_chatgpt_evidence_upload_denial.py` exists in this tree.

## Ownership and overlap

The completion-loop protocol assigns DEBT-0258 integration to **Chat 1 — DEBT-0258 implementation recovery** (`01a147d5-525b-7e31-9fb1-80de3a325e51`). Its current source-construction scope permits writes only to `runtime/scope_supersession.py` and `tests/runtime/test_scope_supersession.py`. Its candidate manifest also pins `runtime/integrations/chat_bridge.py` at SHA-256 `1b77af40b05d4ec54723386c8366d66546c260cfc1db7402583252a609daac38` as a read-only dependency. Editing that runtime file could invalidate Chat 1's captured candidate and requires serial coordination. The uploader and an uploader-specific test are outside that listed write scope, but this inventory grants no authority to change them.

The DEBT-0258 handoff remains `SOURCE_CAPTURED_TESTED_HETEROGENEOUS_REVIEW_PENDING`; it records no independent review, Court adjudication, integration permission, production activation, baseline qualification, or debt closure. Native-chat messages cannot change those states.

## Coordination answer and next gate

The completion loop is **event-driven by a worker's explicit native-chat message after a material result**, with coordinator validation and an hourly fallback. It is not currently a demonstrated automatic callback from PAEOS runtime completion. A coordinator can use the Codex thread messaging tools to follow up, but the source trace does not show a PAEOS event automatically waking that coordinator.

- **ALLOWED_NOW:** this read-only inventory and coordinator notification with the evidence path/hash.
- **HELD:** any claim that a native-chat reply completes a PAEOS run; end-to-end ChatBridge receiver binding; production activation, Builder qualification, or D0258 closure.
- **AUTHORITY_OR_IMPLEMENTATION_GAP:** no inspected source-bound component writes the canonical response file and binds the response to the exact exchange, worker session, and authenticated receiver-start evidence. The independent UI uploader is unbound to that exchange.
- **Exact wake condition:** identify and authorize the actual receiver/response producer and its transaction binding, or issue a distinct bounded scope for a helper-only denial. If the approved fix touches `runtime/integrations/chat_bridge.py`, coordinate serially with Chat 1 before changing its pinned dependency. End-to-end work then needs a synthetic integration test proving exact exchange/session binding and fail-closed behavior for an unbound or stale response; native UI activity alone is not acceptance evidence.

## Inspection limits

No tests, PAEOS source, provider calls, browser/UI, AppleScript, credential or runtime-state reads were performed. No source or test files were edited. The base checkout was clean before the evidence folder was created. This inventory does not prove that no external scheduler or manual process invokes the separate UI scripts.
