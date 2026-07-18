# Worker Package: F-SPI — Adapter SPI Freeze

## Purpose
Freeze the five-function adapter boundary as both human-readable contract and
machine-readable signature file. After merge this surface changes only via the K4 §14.2
ceremony (same as syscalls).

## Forcing kernel clause
K4 §12 (adapter contract) · K4 §14.2 (runtime ABI stability) · R §10, §1.11–1.12.

## Dependencies
None. Binding inputs: SC-03 (Ed25519), SC-01/SC-02 (encodings).

## Owned files
```
adapters/spi/SPI.md          # normative prose contract (≤ 2 pages)
adapters/spi/spi.json        # machine-readable signatures (the frozen artifact)
```

## File contents that must already exist
`spec/PAEOS-4-kernel.md` §11–§12 · SPEC-CLARIFICATIONS.md.

## Interfaces (the deliverable itself — transcribe, do not design)
`spi.json` MUST define exactly these five functions, with JSON-typed params/returns/errors:

```
invoke_model(rendered: string, params: {max_tokens: uint, temperature?: number,
             model_hint?: string}) → {output: string, usage: {tokens_in: uint, tokens_out: uint}}
  errors: MODEL_UNAVAILABLE, BUDGET_EXCEEDED

sandbox_exec(cmd: [string], input_refs: [HASH], limits: {exec_seconds: uint,
             mem_mb: uint, net: "none"|"declared"}) → {exit_code: int,
             stdout_ref: HASH, stderr_ref: HASH, env_hash: HASH}
  errors: TIMEOUT, SANDBOX_VIOLATION

sign(payload_hash: HASH) → {alg: "ed25519", sig: base64url, key_id: string}
  errors: KEY_UNAVAILABLE

capabilities() → {adapter_id: string, model_families: [string],
                  concurrent_spawn: bool, sandbox_class: "process"|"container"|"vm",
                  max_context_tokens: uint, preamble_hash: HASH}
  errors: none

lower(context: {manifest: [...], rendered: string, truncation: [...]})
  → {native_files: {path: string → content: string}, preamble_hash: HASH}
  errors: LOWERING_UNSUPPORTED
```

`SPI.md` MUST additionally transcribe (not restate in new words — quote K4):
§12.1 MUSTs, §12.2 MUST NOTs, §12.3 degradation modes, and the rule that isolation,
validation, and evidence authorship are KERNEL-side (adapters never touch them).

## Invariants
- Exactly five functions; a sixth is a K9 violation and a review-reject.
- `sign` input is a hash, never a payload (adapters must not see a need to parse evidence).
- `capabilities().preamble_hash` must equal `lower().preamble_hash` (single source).
- All errors from the K4 §11/§12 taxonomy; no adapter-invented error codes.

## Acceptance tests
- `spi.json` validates against a JSON-schema meta-check (include it in the deliverable).
- Clause trace table at the bottom of SPI.md: every §12.1–12.3 sentence → the SPI element or kernel-side owner that discharges it. Zero unmapped sentences.

## Conformance tests validated downstream
C2 (sign path), C4 (isolation stays kernel-side), all of C1–C8 execute through this boundary via T-HARNESS.

## Commit boundaries
1 commit: `spi: freeze adapter boundary v1 (F-SPI)`.

## Expected outputs
2 files. Small is correct — bulk here is a defect.

## Forbidden modifications
Adding functions, options, or "future-proofing" fields · moving any kernel-side duty
(validation, isolation, evidence writing) into the SPI · touching `spec/**`.

## Review checklist
- [ ] Five functions, byte-for-byte signature match with this package
- [ ] Clause trace table complete (mechanically checked: grep §12 sentences)
- [ ] No adapter-side judgment surface introduced (esp. in lower())
- [ ] Ed25519 per SC-03; encodings per SC-01/02
