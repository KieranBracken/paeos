# Local UI disclosure-helper denial candidate

**Status:** `HELPER_PATHS_DENIED_CANDIDATE`; broader P1 remains open.
**Base:** `9241febef77028d638ed0da1444d029b73d998b7`
**Branch:** `codex/p1-bound-source-recovery-20261018`
**Scope:** two pinned legacy helper modules and one new synthetic test module.
**Evidence:** this directory plus the byte-preserved prior handoff inventory at `reviews/tasks/PAEOS_CHATBRIDGE_HANDOFF_INVENTORY_20261018/`.

## Change

Both unbound native-UI helper paths now fail locally with `LocalDisclosureDenied("local UI disclosure helper disabled; no content was sent")` before handling data:

- `ops/chatgpt_bridge/upload_evidence.py::submit_payload_to_chatgpt` denies before JSON serialization, attachment handling, temporary JavaScript writes, AppleScript, Chrome activation, or send-button interaction.
- `ops/codex_auth_relay.py::send_approval_to_chatgpt` denies before formatting the bundle hash into application-generated authorization text, clipboard/UI use, AppleScript, or local approval-state writes.
- `ops/codex_auth_relay.py::check_and_authorize` denies before scanning temporary prompts, reading the cached hash, or forwarding an authorization-shaped message.

There is no positive permit, enable flag, alternate route, or content-bearing refusal. The denial is unconditional for these helpers; no non-SECRET UI dispatch was authorized in this package. The source-bound ChatBridge runtime and Chat 1's pinned D0258 dependency are untouched.

## Verification

The new tests use only synthetic markers and side-effect spies. They check that payload serialization, temp-file access, process/UI calls, prompt/state reads, hash formatting, and output echo do not occur. On the original pinned preimages, the tests failed at the intercepted serialization, AppleScript, and prompt/state-helper calls. After the guards, the focused suite passed **3/3** under the project Python environment.

Other checks:

- New test module: Ruff lint and full-file format checks passed.
- Changed source lines: Ruff range-format checks passed; scoped source lint passed when excluding only the exact baseline violations below.
- Compilation of the two helpers and new test module passed.
- Tracked source diff whitespace check passed. The full staged diff check reports only four existing Markdown hard-break spaces in the byte-preserved prior inventory; the scoped staged check excluding that exact inventory file passed for every other path.
- Full-file Ruff on the two legacy scripts still reports pre-existing findings, reproduced against `HEAD`: `I001` and unused `os`/`sys` imports in the uploader, and `SIM105` in the authorization relay. Full-file Ruff formatting also requests unrelated formatting changes in both pinned files. Those unrelated cleanup changes were not made; baseline formatter diffs are recorded in `HARNESS_HISTORY.md`.
- A focused high-confidence secret-pattern scan of the checkpoint file set found no matches. It is not a substitute for a general secret scanner.
- The full PAEOS suite was not run, as required. The last measured full-suite result remains seven collection errors; it is not acceptance evidence for this candidate.

Failed setup/test/lint attempts and their corrections are indexed in `HARNESS_HISTORY.md`; no failed output was overwritten. No browser, UI, AppleScript, network provider, credential/runtime-state read, PAEOS admission, installation, qualification, Court action, or debt integration occurred. No formal independent review was run; it is deferred until the aggregate candidate is ready.

## Gate

`ALLOWED_NOW`: checkpoint this helper-only default-deny candidate and notify the epoch-2 overseer.
`HELD`: end-to-end ChatBridge receiver binding, production activation, Builder qualification, D0258 integration/closure, and P3.
`AUTHORITY_OR_IMPLEMENTATION_GAP`: no source-bound producer authenticates and binds a native-chat response to a PAEOS exchange/session/start receipt. This helper-only denial does not establish that missing receiver or close P1.

Next wake condition: the overseer records this checkpoint and assigns the next bounded offline scope. Any future change to `runtime/integrations/chat_bridge.py` must first coordinate serially with Chat 1. A positive egress path requires separately reviewed trusted classification, disclosure, route, and execution authority; this package creates none.
