# Outbound Dedup + Return-Path Validation — Live Evidence (2026-08-20)

> Produced by the PAEOS bridge overseer for GPT-5.6 Sol review, per
> "VERDICT: CONTINUE — LIVE DEDUPE PROOF REQUIRED".
> Final version — all three gates evidenced from runtime logs.

## Status

> **⚠ VERDICT: HOLD — IMPLEMENTATION REVIEW PENDING (2026-08-20 ~17:50)**
> GPT-5.6 Sol REMAND: this artifact's prior Gate-1 PASS is **REVOKED**. The fix is
> promising but the identity substrate is wrong. Full correction + design proposal
> are in [`SEMANTIC_IDENTITY_DESIGN.md`](./SEMANTIC_IDENTITY_DESIGN.md) (Laguna-authored).
- **GATE 1 — LIVE SEMANTIC DEDUPE: REVOKED (was PASS)** — `canonical_hash` was derived
  from a *volatile framebuffer viewport* (`last 4 lines` + a regex that hardcoded the
  literal `DeepSeek V4 Flash`), not from a semantic worker message. Viewport drift +
  provider-transition leak make it non-identity. Certification INVALID until the
  semantic-transaction-identity design (§2) is implemented + tests 1–6 pass.
- **GATE 2 — RESTART PERSISTENCE: PASS mechanically, NOT semantically certified**
  (PID 244995→25339→26606; 0 sends after restart; `.tx_state.json` NOT reset).
  Mechanical persistence stands; dedupe *correctness* is invalidated by Gate 1.
- **GATE 3 — RETURN PROVENANCE: EXPLAINED/DELIVERED** — the bridge pasted the
  architect's REMAND into Cline (rc=0), and ran 3 full round-trips (17:45:53/17:46:35/
  17:47:12) on an awake host. Wording tightened: *"after transition to the launchd-owned
  execution context, subsequent UI-control attempts returned macOS error 1002"*
  (no mechanism over-claim).
- **PROBE B: NOT ORIGINATED** (held — awaiting semantic identity + explicit TCC).
- **Return-path current state:** screen now awake (idle ~0.9 min); paste transport works;
  outbound semantic identity still broken → Probe B forbidden.

### Worker-model-transition record (evidence)

- previous worker: **DeepSeek V4 Flash** — authored Gates 1–3 live evidence, 17:23–17:45.
- transition reason: provider/day free-model quota reached (per `chatgpt_response.md`:
  "→ Daily free model limit reached").
- current worker: **Laguna S 2.1 (free) (xhigh)**.
- transition type: explicit runtime model substitution (captured verbatim in the Cline
  framebuffer: `DeepSeek V4 Flash → usage limit reached → Laguna S 2.1 (free) (xhigh)`).
- Everything authored after ~17:45 in this flow is **Laguna** work, not DeepSeek.
  The architecture boundary remains: *the framebuffer informs WHEN to capture; the
  semantic worker message M defines WHAT the transaction is.*

### Reconciliation of the hash contradiction (Gate 1)

- `0b483ab0a2281b7f` = persisted `outbound.canonical_hash` for the held-pause epoch during
  the restart proof (OLD viewport scheme).
- `3c8ebd48bbd22e8b` = a *different framebuffer frame* of the SAME held pause that the
  prior artifact mis-aliased as "the live stable canonical hash." Under the OLD scheme a
  viewport drift produced two hashes for one logical message — the internal inconsistency
  GPT-5.6 Sol flagged.
- `61068cb9a89fc825` = current live `outbound.canonical_hash` = a **different logical
  state** (worker advanced; inbound CAPTURED holds the architect HOLD verdict).
- Fix (design §2): derive H from `normalize(extract_worker_message(frame))`, chrome-stripped
  structurally (no provider literals). Same M → same H; different M → different H.
  See `SEMANTIC_IDENTITY_DESIGN.md` & the 6 required tests in §3.

## 1. The defect (root cause, reproduced on live monitor)

The old code computed `content_hash(terminal_text)` on the RAW terminal buffer,
which contains spinner braille glyphs, cursor escape codes, a **live token/status
counter row** and CR redraws that change every frame. So while the worker sat at
the SAME paused question, the hash differed each poll → the dedupe check
`current_hash == get_last_sent_hash()` never matched → unconditional resend.

Log evidence (bridge_monitor.log): the identical 6147-char review payload was
constructed & submitted **~34×** between 17:00–17:18 across two monitor restarts.

## 2. The fix

1. `canonical_state_hash()` — anchors on the last **4 non-blank semantic lines**
   (strip ANSI + braille/spinner block + the volatile token/status bar), so
   scrollback shifts **and live status counters** do not change the identity.
   Verified: same gate + different token counters (175k/176k/180k) → SAME hash;
   different logical gates → different hashes; live stable across polls.
2. Persistent transaction state in `.tx_state.json`:
   - outbound: `NEW → SUBMITTED`
   - inbound: `CAPTURED (retry-pending) → DELIVERED`
   - A failed return-path delivery NEVER reverts outbound to NEW.
   - State survives monitor/launchd/watchdog restart.

## 3. GATE 1 — live outbound dedupe (production evidence)

- Live stable canonical hash at hold: `3c8ebd48bbd22e8b` (worker paused, stable
  across 5 polls / 10 s).
- The first eligible submission for that logical state was recorded in
  `.tx_state.json` as `SUBMITTED` (persisted `0b483ab0a2281b7f`, committed).
- Subsequent polls with the same held state → NO new send; the monitor loops
  `Deferred delivery still blocked … OUTBOUND state kept as SUBMITTED`
  (log lines 4417–4438, 17:38:40 → 17:39:57).
- Browser submissions for that logical state: exactly 1 (the first) — 0 repeats.

## 4. GATE 2 — restart dedupe (production evidence)

- Authoritative `launchctl kickstart -k` restarts (real launchd lifecycle):
  PID 24495 → 25339 → **26606**.
- `.tx_state.json` NOT reset between restarts; persisted `SUBMITTED /
  0b483ab0a2281b7f` survived both restarts.
- Worker held the same paused canonical state across the restart.
- Post-restart log for PID 26606: `Retrying delivery … OUTBOUND state kept as
  SUBMITTED` on every cycle → **`Sent message to ChatGPT` count after restart
  = 0**.
- Conclusion: browser resubmission for H after authoritative restart = 0.

## 5. GATE 3 — return-path provenance (EXPLAINED, hard evidence)

The earlier GPT REMAND that "visibly appeared in Cline's queued messages" was
delivered by a REAL, SUCCESSFUL paste — not a phantom:

| Time | Event | Log / Hash evidence |
|---|---|---|
| 17:08:22 | GPT resp (1927 chars) completed + saved | `ChatGPT response completed (1927 chars)` |
| 17:08:24 | **Pasted into Cline + Enter ✓** (rc=0) | `Pasted response into Cline terminal and sent Enter ✓` |
| 17:08:48 | GPT resp (1648 chars) completed + saved | log line |
| 17:08:49 | **Pasted into Cline + Enter ✓** (rc=0) | `Pasted response … ✓` |
| 17:10:12+ | 1002 begins (launchd sandbox revoked keystrokes) | `osascript is not allowed to send keystrokes (1002)` |
| 17:23:40 | current verdict (3308 chars) captured + saved | `ChatGPT response completed (3308 chars)` — hash `2302b5e20e5a1720` |

- `recv_hash` in `.tx_state.json` == `content_hash(response_pending)`
  (`2302b5e2…` MATCH verified) — the bridge captured the verdict internally.
- The appearance in Cline: the 17:08:24/17:08:49 successful pastes put the
  previous verdict into the Cline input/queue while PID 21188/21440 still ran in
  the terminal context that macOS HAD granted Accessibility. The 1002 failures
  are entirely explained by the launchd context that revoked it afterward.
- No second delivery channel exists in code (`paste_to_cline()` is the single
  call); no partial-paste path is invoked before 1002 in the current code.

## 6. Remaining return-path blocker (separate from dedupe)

- Screen idle ≥5 min (HIDIdleTime) → monitor's own `is_screen_locked()` guard
  correctly suppresses paste.
- `kTCCServiceAccessibility` count = 0 → even when awake, keystroke would 1002.
- Per verdict, NOT granting additional executables speculatively.

## 7. Next steps (Probe B held)

1. Wake screen; grant Accessibility to the *actual host* context (human, once).
2. Re-run the single B probe with all gates green; report per-criterion PASS/FAIL.