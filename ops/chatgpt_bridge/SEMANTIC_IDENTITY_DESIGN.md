# Semantic Transaction Identity — Design Proposal (NON-MUTATING)

> `# PROPOSAL — §8 APPROVED FOR IMPLEMENTATION (isolated tests 1–18 first; Gate 1 still HOLD).`
> Non-mutating design pass only (per VERDICT: FINAL REJECT — IMPLEMENTATION NOT
> AUTHORIZED). No code in `monitor_loop.py` is modified by this document. No edit to
> production `.tx_state.json`. No Probe B. No TCC experimentation.

**Author of this pass:** current active worker = **Laguna S 2.1 (free) (xhigh)**.
**Author of the prior live-dedupe evidence:** DeepSeek V4 Flash (17:23–17:45).
The model transition occurred during this flow (see §6).

**Target file (when approved):** `ops/chatgpt_bridge/monitor_loop.py`
**Current live fixture:** `ops/chatgpt_bridge/.tx_state.json` = `outbound SUBMITTED
(61068cb9a89fc825)` + `inbound CAPTURED` whose `response_pending` holds the architect's
verbatim `VERDICT: HOLD` text. This is the failed-return test fixture (test 3).

---

## 1. The defect (reconciled hash identity)

Two samples in the prior artifact were used as if they were the same identity:

| hash (old framebuffer-viewport scheme) | object it actually represents | verdict |
|---|---|---|
| `0b483ab0a2281b7f` | `outbound.canonical_hash` persisted during the restart proof (PID 24495→25339→26606) | the SUBMITTED identity of that held-pause epoch, OLD scheme |
| `3c8ebd48bbd22e8b` | a *different framebuffer-viewport frame* of the **same** held pause (content above the last-4-line tail differed at read time) | a distinct FRAME, wrongly aliased as "live stable canonical hash" — the artifact's internal inconsistency |
| `61068cb9a89fc825` | current live `outbound.canonical_hash` (worker has advanced; inbound now holds the architect HOLD verdict, CAPTURED) | a **different logical worker state** → legitimately a different H |
| `a52e9f2d…`, `a0bb380c…`, `113ce750…` | later viewport samples as the terminal re-rendered / worker advanced | frames; same M → same NEW H, different M → different H |

**Why they disagree even for the "same" pause:** the old `canonical_state_hash`
hashes the *framebuffer viewport* (`last 4 stable lines` after a regex that still
encoded a literal provider name). The Cline TUI framebuffer re-renders every frame
(spinner glyphs, cursor redraws, history scroll, queued-message panel, token
counter width). The viewport therefore drifts even while the worker's answer text
is frozen → two different hashes for one logical message. The literal
`DeepSeek V4 Flash` in the regex is the additional silent-substitution trigger the
verdict flagged: a provider change leaks straight into `H`.

**Root defect:** identity is derived from a *rendering*, not from the *message*.

---

## 2. Historical note — rejected framebuffer identity (superseded by §8)

The original §§2–5 of this document proposed deriving identity from the **terminal
framebuffer** using: a 64-line viewport window, a `CHROME_RE` to strip rendered chrome,
a `normalize()` that stripped ANSI, collapsed CR-redraw rows, and trimmed trailing
whitespace, `message_hash(frame) = H(normalize(extract_worker_message(frame)))`, and a
`NEW → SUBMITTED → send` dispatch. That approach was **REJECTED** by GPT-5.6 Sol
(remand #1–#3) for the reasons below, each now enforced in §8. The executable-looking
bodies of the old §2–§5 are intentionally NOT repeated here; this section is
non-normative history only.

- Viewport/hash as identity ⇒ viewport drift changes H for one message; a literal
  provider name (`DeepSeek V4 Flash`) leaked into `H` ⇒ false collisions across the
  DeepSeek→Laguna substitution.
- `NEW → SUBMITTED → send` is crash-unsafe: a kill after persist, before send,
  silently loses the transaction.
- Substring/PAUSE_MARKER and "TUI structural-fallback" gave the framebuffer semantic
  authority it must have only as a readiness sensor.
- Framebuffer-only hashing provided no correlation to a captured GPT response, so
  stale/unbound responses could not be quarantined.

## 6. Worker-model-transition evidence (recorded per verdict)

- previous worker: **DeepSeek V4 Flash** (authored the live-dedupe evidence, 17:23–17:45).
- transition reason: **provider/day free-model quota reached** (per
  `chatgpt_response.md`: "→ Daily free model limit reached").
- current worker: **Laguna S 2.1 (free) (xhigh)**.
- transition type: **explicit runtime model substitution** (captured verbatim in
  the Cline framebuffer: `DeepSeek V4 Flash → usage limit reached → Laguna S 2.1
  (free) (xhigh)`).
- Attribution: everything authored after transition time (~17:45) in this pass is
  **Laguna** work, not DeepSeek. The prior live-dedupe evidence is cited verbatim
  from DeepSeek-era logs where referenced.


---

## 7. Gate status (corrected per VERDICT: HOLD)

- **GATE 1 — LIVE SEMANTIC DEDUPE: REVOKED** (previously and erroneously marked PASS).
  Fails until §8 is implemented + tests pass, because the old
  `canonical_state_hash` derived `H` from a volatile viewport + provider literal.
  Current live fixture (test 3) is in place: `outbound SUBMITTED(61068cb9)`,
  `inbound CAPTURED`.
- **GATE 2 — RESTART PERSISTENCE MECHANISM: PASS mechanically** (24495→25339→26606;
  0 sends after restart; `.tx_state.json` not reset by us), but **semantic
  certification INVALID** until Gate 1 identity is rebuilt.
- **GATE 3 — RETURN PROVENANCE: EXPLAINED/DELIVERED** — the bridge pasted the
  architect's REMAND into Cline (rc=0; `Pasted response … ✓ / Cycle complete ✓`),
  and additionally completed 3 full round-trips (17:45:53, 17:46:35, 17:47:12) on
  an awake host. Per verdict wording: *"after transition to the launchd-owned
  execution context, subsequent UI-control attempts returned macOS error 1002"*
  (screen-idle/TCC) — mechanism not over-claimed.
- **PROBE B: NOT ORIGINATED** (held — awaiting semantic identity + explicit TCC).
- **Return-path current state:** screen is awake (idle ~0.9 min) and paste
  transport demonstrably works; however outbound semantic identity is still
  broken, so Probe B remains forbidden.

---

## 8. Revised design — structured-transaction protocol (IMPLEMENT §8 ONLY)

### 8.1 Grounded identity substrate (inspected, not assumed)
- Cline persists `~/.cline/data/sessions/<session_id>/*.json`. Session record keys:
  `session_id, pid, started_at, ended_at, status, provider, model, cwd,
  workspace_root, messages_path, compaction_path`. Provider/model attribution is
  structured and decoupled from the rendered footer.
- `<session_id>.messages.json` = `{version, updated_at, agent, sessionId, origin,
  messages, system_prompt}`; `messages[]` is append-only; each message:
  `{ id:"msg_<8alphanum>", role, content:[...], ts, ... }`. `id` is server-assigned
  and unique; **use `id` for identity, NOT array index and NOT `ts` for identity**
  (ts is provenance/ordering metadata only).

### 8.2 eventRef + complete-turn atomicity (points 1, 6)
- `eventRef = (sessionId, last_assistant_message.id)` — `ts` retained as provenance/
  ordering only, never in identity.
- BEFORE PREPARED, a turn must be proven **complete and stable** (fail-closed):
  `is_turn_complete(sessionId, messageId)`:
  (a) a structured completion flag if the schema exposes one (no `in_progress`/partial
      marker); else
  (b) **stable double-read**: re-read `messages[]` and require ALL of:
      - same `sessionId`
      - same last assistant `messageId`
      - same exact structured-content hash of that message
      - no newer assistant message inserted
  If anything changes between the two reads → `TURN_INCOMPLETE` → NO PREPARED.
- Session resolution is fail-closed: exact correlation of `tty + live worker PID /
  process ancestry + session.pid + status == running + cwd/workspace match +
  messages_path`. `0 matches` or `>1 matches` → `AMBIGUOUS_SESSION` → zero submission
  (the framebuffer is a readiness sensor only; it never provides message content).

### 8.3 transactionKey (deterministic logical identity) + response correlation (points 1, 2)
```
transactionKey = H( identityVersion
                   + reviewType
                   + eventRef                   # sessionId + stableMsgId
                   + semanticHash               # = H(canonicalStructured(M))   (8.4)
                   + evidenceHash               # = H(E)                        (8.5)
                   )
```
- **Invariant:** same eventRef + semanticHash + evidenceHash → same `transactionKey`,
  regardless of restart or dispatch-attempt bookkeeping. `reviewRequestId` and
  `dispatchSeq` do NOT participate in `transactionKey`.
- `reviewRequestId`: generated EXACTLY ONCE at PREPARED, persisted, reused across
  restart/resume of that PREPARED transaction; correlation only.
- `dispatchSeq`: transport/attempt sequencing; never changes `transactionKey`.

- Outbound record stores `transactionKey` + `reviewRequestId` + `dispatchSeq` +
  `eventRef` + hashes + `transitionLog`.
- Response binding is derived from the **browser conversation structure**, not from
  GPT echoing markers: the confirmed outbound USER turn (containing `reviewRequestId`
  + `transactionKey`) ⇒ the immediately following assistant turn attributable to it
  ⇒ capture its text and store `binding = {reviewRequestId, transactionKey,
  dispatchSeq, response_hash, response_pending}`.
```
inbound = { state, recv_hash, reviewRequestId, transactionKey, dispatchSeq,
            response_hash, response_pending }
```
- If conversation ancestry/DOM ordering cannot establish that association ⇒
  `UNBOUND_RESPONSE` ⇒ `QUARANTINE` ⇒ NEVER PASTE. A captured response is pasted only
  if ALL THREE of `reviewRequestId`, `transactionKey`, AND `dispatchSeq` match the
  live outbound record exactly;
  any mismatch (stale response A while B is current) ⇒ `QUARANTINE` ⇒ NEVER PASTE.

### 8.4 structured-content semanticHash (point 4)
- `semanticHash = H(canonicalStructured(M))` over the **structured** message content,
  NOT framebuffer-cleaned text. There is no ANSI-strip / CR-collapse / trailing-ws
  normalize() applied to structured data.
- Canonical form: JSON-canonical serialization of the selected content blocks, with
  `role`, `type`, and exact `text` preserved byte-for-byte — indentation, repeated
  lines, and spaces included, exactly as authored.
- Included block types: `role == assistant && type == "text"` (author turns).
  Excluded: `thinking` (reasoning, not authored to the user), `system_prompt`,
  tool-call artifacts.
- "Framebuffer = sensor" applies to readiness/idle only; terminal redraw cleanup
  never touches structured M.

### 8.5 evidenceHash — non-circular resolver (point 7)
```
reviewScope + eventRef  → deterministic evidence resolver → frozen E
freeze(E) → evidenceHash = H(E) → build payload(M, E)
```
- `E = { canonical_artifacts:[{artifact_id, content_sha256, evidence_version}],
        reviewed_tree_sha256, selection_policy }`, where `selection_policy` is a pure
        function of `reviewScope` + `eventRef`; `reviewed_tree_sha256` is the git-tree
        sha of the scope tied explicitly to what GPT is actually reviewing.
- Evidence is frozen BEFORE the payload is built (never inferred from payload previews).
- Provenance (mtime, pid, cwd, workspace, host, started_at) kept separately — never in
  evidenceHash. A byte-untouched mtime change ⇒ same content_sha256 ⇒ same evidenceHash.
### 8.6 Crash-safe dispatch with positive browser ack (point 3)
```
NONE → NEW → PREPARED → DISPATCHING → SUBMITTED
```
- PREPARED: M/E/eventRef/transactionKey frozen + persisted; `reviewRequestId`
  generated EXACTLY ONCE here and persisted; persist
  `requestPayloadHash = H(canonicalBrowserRequest(requestPayload))`; NO browser send.
- `requestPayloadHash` is transport-content verification only — NEVER in
  `transactionKey`.
- `reviewRequestId` reused across restart/resume of this PREPARED transaction;
  `dispatchSeq` is transport sequencing only — neither alters `transactionKey`.
- DISPATCHING: browser send attempted; outcome AMBIGUOUS (not confirmed).
- DISPATCHING → SUBMITTED ONLY after **positive browser evidence**: the confirmed browser USER
  turn has correct `reviewRequestId`, correct `transactionKey`, AND
  `observedRequestPayloadHash == persistedRequestPayloadHash`. AppleScript/CDP returning
  success alone is NOT sufficient.
- Crash during DISPATCHING (before DOM confirmation) → `RECONCILIATION_REQUIRED` →
  FAIL CLOSED → NEVER auto-resend; cleared only by an explicit `actor=architect`
  transition-log entry.
- Inbound stays independent: NONE → CAPTURED → DELIVERY_PENDING → DELIVERED.
  A failed Cline paste never changes outbound state.
- Atomic persist (write-to-tmp + os.replace) at every transaction transition.

### 8.7 Legacy/v1 migration — fail-closed (point 9)
- v1 `canonical_hash` is NOT mapped to a structured key (no equivalence inference;
  the framebuffer-v1 and structured-v2 schemes have no hash mapping between them).
- legacy SUBMITTED/DEDUP detected → `MIGRATION_HOLD`; capture the CURRENT structured
  `eventRef` as `migrationBaseline`. The baseline event is NOT submitted.
- A later event is eligible ONLY when validated from the structured `messages[]`
  ordering (NOT messageId-string comparison — ids are non-monotonic).
- If the baseline disappears (compaction/history rewrite removes it) →
  `MIGRATION_RECONCILIATION_REQUIRED` (never auto-submit).
### 8.8 Adversarial tests (points 10, 11)
Isolated tmp `BRIDGE_DIR`; fresh tx_state seeded per test. No paste / TCC / browser.
1. **Frame invariance** — same turn M, any footer + any ANSI/spinner/viewport/CR redraw
   ⇒ identical `semanticHash` (canonical structured content).
2. **Semantic discrimination** — two turns, identical chrome tail, different text ⇒
   different `transactionKey`.
2b. **eventRef distinctness (architect's exact case)** — turns #41 & #57 both
   "All tests pass.", identical evidence ⇒ identical `semanticHash` + `evidenceHash`
   BUT different `eventRef` ⇒ different `transactionKey` ⇒ each dispatched once.
3. **Failed-return independence** — outbound SUBMITTED; inbound CAPTURED(bound, valid
   response B for the current txn); `paste_to_cline() -> False` ⇒ outbound remains
   SUBMITTED; inbound remains retryable; ZERO outbound resend.
4. **Crash before DISPATCHING** — PREPARED persisted; resume ⇒ safe retry; sends == 1.
5. **Crash during DISPATCHING** — ⇒ `RECONCILIATION_REQUIRED`; ZERO auto-resend until
   `actor=architect` clears.
6. **Crash after SUBMITTED** — restart suppresses; sends == 0.
7. **Evidence binding** — unchanged M; (a) byte-untouched mtime-only touch ⇒ SAME
   `content_sha256` ⇒ same `evidenceHash` ⇒ suppressed; (b) reviewed-byte change ⇒
   different `evidenceHash` ⇒ eligible.
8. **Restart persistence** — `launchctl kickstart -k`; schema_version + states
   byte-stable; same turn ⇒ same `transactionKey`; sends == 0.
9. **message changes between completeness reads ⇒ no PREPARED.**
10. **stale response A while B current ⇒ no paste (QUARANTINE).**
11. **response missing reviewRequestId/transactionKey ⇒ no paste.**
12. **crash after browser send, before DOM confirmation ⇒ RECONCILIATION_REQUIRED.**
13. **indentation-only content diff ⇒ different semanticHash.**
14. **ambiguous session (0 or >1 matches) ⇒ zero send.**
15. **structured source unavailable/ambiguous ⇒ zero send (no TUI fallback).**
16. **legacy v1 active ⇒ MIGRATION_HOLD, zero send; baseline lost ⇒ hold.**
17. **PREPARED restart:** same eventRef + semanticHash + evidenceHash ⇒ same `transactionKey` AND same persisted `reviewRequestId` (sentinel invariant).
18. **transport-attempt bookkeeping:** `dispatchSeq` changes ⇒ `transactionKey` UNCHANGED.

### 8.9 Minimal change set (post-approval only)
`ops/chatgpt_bridge/monitor_loop.py`:
1. Add `resolve_active_session()` — fail-closed tty/PID/cwd/workspace/messages_path
   correlation; returns `AMBIGUOUS_SESSION` on 0 or >1 matches.
2. Add `is_turn_complete()` — structured flag OR stable double-read.
3. Add `extract_worker_message()` = `canonicalStructured(last assistant message)` from
   `<sid>.messages.json`; **REMOVE** any TUI structural-fallback (fail-closed if the
   structured source is unavailable).
4. Add `semantic_hash = H(canonicalStructured(M))` (structured; indentation-preserving;
   assistant `type:"text"` blocks only).
5. Add `freeze_evidence()` — deterministic resolver from `reviewScope + eventRef`;
   provenance stored separately → `evidenceHash`.
6. Add `turn_identity()` → `eventRef` (sessionId + stable message `id`).
7. Add `transactionKey(identityVersion, reviewType, eventRef, semanticHash, evidenceHash)`; (reviewRequestId/dispatchSeq are correlation/transport only — NEVER in the key); bump tx_state to `schema_version = "semantic-v1"`
   with outbound `{transactionKey→transactionKey, reviewRequestId, dispatchSeq,
   eventRef, semanticHash, evidenceHash, transitionLog}` and inbound
   `{state, reviewRequestId, transactionKey, dispatchSeq, response_hash,
   response_pending}`.
8. Replace dispatch with `NONE→NEW→PREPARED→DISPATCHING→SUBMITTED` (positive browser
   ack gate §8.6; `RECONCILIATION_REQUIRED` fail-closed; `QUARANTINE` for unbound
   responses §8.3; `MIGRATION_HOLD` legacy path §8.7); atomic persist at every
   transition.
9. `tests/chatgpt_bridge/test_semantic_identity.py`: tests 1–18.

No change to `runtime/`, `kernel/`, existing `.tx_state.json` content, TCC, Probe B.

---

## 9. Gate status (updated per GPT-5.6 Sol FINAL REJECT → design revised)

- **AUTHORIZATION: NOT YET GRANTED.** The file previously attached was one revision
  behind the terminal remand; §8 now resolves all eleven final corrections (§8.1–8.9).
  Awaiting GPT-5.6 Sol FINAL sign-off before any `monitor_loop.py` edit, any
  `.tx_state.json` change, or Probe B.
- **GATE 1 — LIVE SEMANTIC DEDUPE: HOLD** (design correct; pending §8 implementation
  + tests 1–18 pass).
- **GATE 2 — RESTART PERSISTENCE: MECHANICAL PASS** (re-certified on v2 atomic writes).
- **GATE 3 — RETURN PROVENANCE: EXPLAINED/DELIVERED.**
- **PROBE B: HELD** (unaffected; requires Gate 1 close + explicit TCC).
- **Return-path:** idle ~1 min; paste transport working; no dispatch pending; Probe B
  remains forbidden.
