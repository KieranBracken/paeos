# Phase 5 Substrate Capability Completion Design

**Date:** 2026-09-07  
**Status:** Founder-approved, self-reviewed, implementation-ready design; execution gated by P0 takeover reconciliation and a fresh P1 completeness qualification  
**Scope:** PAEOS and Orca-strator substrate capabilities only

## Goal

Complete the five Phase 5 substrate capabilities with physically persistent state, deterministic and evidence-bound processing, read-only external inspection, fail-closed model-output handling, and a non-vacuous Verification Court gate.

## Precondition

This design does not authorize implementation by itself. Before any P5 code change, PAEOS must complete a read-only takeover reconciliation, record `CURRENT_REMEDIATION_STATE.md`, and re-qualify Phase 1 completeness assurance. The P1 gate must prove actual L11 manifest freezing, L13/L16 runtime enforcement, artifact-bound physical Court evidence, negative CANARY `REMAND` discrimination, and a valid candidate/report-bound heterogeneous Layer 14 audit. Until then, P5 remains `BLOCKED` and prior Phase 1–4 seal claims remain historical/unverified.

## Constitutional constraints

- The canonical PAEOS L01–L19 lifecycle remains unchanged; no synthetic layer or stage bypass is introduced.
- PAEOS owns canonical state, evidence, checkpoints, graph stores, and acquisition records. Models are stateless compute only.
- PAEOS Layer 2 owns routing, retry, fallback, quota, and provider policy. Any Layer 14 review uses a different model family from the builder.
- Sentium code, models, credentials, live trading state, capital state, order state, and execution authority are outside the Phase 5 source and evidence scope.
- The Orca legacy credential-bearing acquisition area is not read, changed, ingested, or hashed into Phase 5 evidence.
- SAKG and Concept OS writes are append-only and idempotent. No UPDATE or DELETE path is added to a canonical substrate.
- PAEOS architectural code and tests are changed only inside the Chat-Bridge workspace supplied by the governed SoftLoop. If the bridge cannot supply a builder workspace/artifact, the PAEOS implementation stops and records a remand; no host-root architectural edit is substituted.
- Court claims are backed by physically executed subprocesses whose stdout, stderr, and exit codes are captured. The Court runner includes a deliberate failing CANARY and requires `REMAND`.

## Existing seams and selected approach

The implementation reuses the existing deterministic SAKG AST probe, append-only graph store, Concept OS typed WAL store, KAE citation CAS boundary, and Orca Idea OS event store. New orchestration is added around those seams rather than creating a second graph, a second concept authority, or a provider-specific pipeline.

The selected approach is a local, checkpointed extraction runner plus read-only MCP query facade; a canonical Concept OS store opener; a deterministic research-note distiller with explicit contradiction states; a strict Orca synthesis parser; and a durable KAE acquisition ledger backed by local CAS. Cross-repository interaction is through the versioned `research-distillation/v1` JSON contract and explicit operational subprocess/HTTP seams, never by sharing a mutable database connection. The exact changed-file allowlist is recorded in the Court bundle and excludes all Orca credential files, Sentium-named paths, trading state, and unrelated repository artifacts.

## P5.1 — SAKG continuous extraction and graph queries

`sakg/store.py` will configure persistent GraphStore connections with SQLite WAL, `synchronous=FULL`, foreign keys, and a 5-second busy timeout. The `:memory:` test path remains supported without claiming WAL because SQLite cannot provide a durable WAL file there.

`sakg/continuous.py` will provide these exact interfaces:

```python
@dataclass(frozen=True, slots=True)
class ExtractionProbe:
    name: str
    root: Path
    database: Path
    checkpoint: Path
    namespace: str = "paeos-history"

@dataclass(frozen=True, slots=True)
class ExtractionRunReport:
    probe_name: str
    source_digest: str
    previous_source_digest: str | None
    scanned_files: int
    changed_files: int
    attempted_nodes: int
    appended_nodes: int
    replayed_nodes: int
    attempted_edges: int
    appended_edges: int
    replayed_edges: int
    skipped: bool
    snapshot_hash: str

class ExtractionRunner:
    def run_once(self, probe: ExtractionProbe) -> ExtractionRunReport: ...
    def watch(self, probe: ExtractionProbe, interval_seconds: float,
              stop_event: threading.Event) -> Iterator[ExtractionRunReport]: ...
```

The probe root must contain only the explicit `paeos/` and `kernel/` extraction scopes. The runner computes a sorted relative-path/byte-hash manifest, compares it with the last successful checkpoint, and invokes the existing deterministic AST extraction only when the source digest changes. The checkpoint is written with a same-directory temporary file, `fsync`, and atomic replace only after extraction completes; extraction or checkpoint failure leaves the prior checkpoint intact. The indexer reports attempted and inserted node/edge counts so replay counts are empirical, not inferred from a hardcoded expected total.

The runner will reject missing roots, empty probe scopes, malformed source files, namespace mismatches, and source paths that enter the Sentium or credential-bearing scope. It will return machine-readable counts for scanned files, changed files, appended nodes, replayed nodes, and the resulting graph snapshot. Existing append-only identity rules remain authoritative.

`sakg/mcp_server.py` will expose the exact `build_live_sakg_mcp_server(database, namespace="paeos-history", tier="SUMMARY")` constructor. It opens a read-only SQLite URI connection, verifies `query_only=ON`, and registers one `sakg_query` tool with `object_kind` (`"nodes"` or `"edges"`), optional typed filters (`node_type`, `family`, `relation`), and positive `max_nodes`/`max_tokens` limits. The result is `{provenance, trust, tier, namespace, snapshot_hash, nodes, edges, truncated, omitted}` with deterministic ordering and explicit token accounting. The live facade exposes no SQL, filesystem path, writer, promotion, evidence minting, or mutation tool.

## P5.2 — Concept OS persistent canonical state

`concept/canonical.py` will define `CANONICAL_NAMESPACE = "core"`, `CANONICAL_DATABASE = Path(__file__).resolve().parents[1] / "concept.db"`, and `open_canonical_store(database: str | Path | None = None, *, read_pool_size: int = 4) -> ConceptStore`. The helper will open the selected durable path through the existing `ConceptStore`, then verify the writer's `WAL`, `synchronous=FULL`, foreign-key, busy-timeout, and read-pool `query_only=ON` invariants. It will not create a second Concept database or import any Orca database.

All canonical node identities will continue to derive from the existing `node_uri("core", ...)` implementation, producing `concept://core/concept/...` for Concept nodes with fixed-width 128-bit Crockford Base32 tokens. Reopen tests will prove that an appended node survives process/store closure and that identity collisions fail closed.

## P5.3 — Inspiration distillation and contradiction pipeline

`concept/distillation.py` will define immutable research-note inputs and a deterministic `distill_notes(notes: Sequence[ResearchNote]) -> DistillationReport` result. `ResearchNote` contains `source_uri: str`, `source_path: str`, `content: bytes`, and optional `declared_sha256: str`; the implementation verifies the digest before parsing. The accepted markdown grammar is explicit: the first H1 is the theme title; `## Summary` contributes non-empty paragraphs; `## Claims` contributes `- ` bullet lines; and `## Contradictions` contributes lines of the form `- [STATE] KEY :: DESCRIPTION`, where `STATE` is `OPEN` or `RESOLVED`. A `RESOLVED` entry must include a non-empty `## Resolution` paragraph or `::` resolution text. Other content is retained only through the note's source hash and is not semantically inferred.

The serialized `research-distillation/v1` result is validated by the shared JSON Schema at `contracts/research-distillation-v1.schema.json` and has this shape (the zero hash is illustrative only; implementations validate a lowercase 64-character SHA-256 digest):

```json
{
  "schema_version": 1,
  "themes": [{
    "theme_key": "stable-key",
    "title": "Explicit H1 title",
    "summary": "Deterministically collected summary text.",
    "claims": ["Explicit claim"],
    "source_refs": [{"uri": "note://one", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}]
  }],
  "contradictions": [{
    "key": "explicit-key",
    "state": "OPEN",
    "description": "Explicit description.",
    "resolution": null,
    "source_refs": [{"uri": "note://one", "sha256": "0000000000000000000000000000000000000000000000000000000000000000"}]
  }]
}
```

Themes with the same normalized title are merged by sorted source URI; claims and source references are deduplicated by canonical bytes. Contradictions with only `OPEN` observations remain `OPEN`; a complete, consistent explicit resolution becomes `RESOLVED`; missing, conflicting, or mixed `OPEN`/`RESOLVED` observations become `UNRESOLVED`. `UNRESOLVED` is never silently promoted. Empty notes, missing source identity, invalid hashes, malformed states, and absent provenance fail closed.

Contradiction states are a closed vocabulary: `OPEN`, `RESOLVED`, and `UNRESOLVED`. `RESOLVED` is accepted only when the source explicitly declares a resolution; conflicting or incomplete declarations become `UNRESOLVED`; no contradiction is silently discarded or treated as resolved by frequency.

Orca's synthesis pipeline will emit the same field names and contradiction-state vocabulary when converting a caller-supplied batch of genuine, non-Sentium Idea OS notes. The parser validates source references against the batch's `{idea_id: sha256}` map, and the Court runner validates the resulting JSON against the PAEOS contract without importing Orca state into PAEOS.

## P5.4 — Idea OS synthesis output hardening

`backend/app/company/synthesis_parser.py` will expose:

```python
class SynthesisParseError(ValueError): ...

def parse_synthesis_response(
    text: str,
    *,
    allowed_note_ids: Collection[str],
    note_source_hashes: Mapping[str, str],
) -> SynthesisOutput: ...
```

`SynthesisOutput` requires `category` (`RESEARCH_THEME` or `KNOWLEDGE_BANK`), non-empty bounded `theme_title`, `hypothesis_or_summary`, `domain`, a contradiction map whose values contain `state`, `description`, and optional `resolution`, a unique `linked_note_ids` array, and `source_refs` containing exactly the linked note IDs and their lowercase SHA-256 values. It accepts strict JSON, one valid JSON object inside one markdown fence, or one valid JSON object surrounded by prose. A `json.JSONDecoder.raw_decode` scan identifies exactly one outermost object; nested objects are allowed, multiple top-level objects are rejected. Empty output, malformed JSON, wrong top-level types, missing fields, unknown categories, malformed contradiction maps, invalid states, duplicate IDs, unknown note IDs, and mismatched source hashes all raise `SynthesisParseError` without including raw model text in the exception.

`SynthesisEngine` will gather and validate every model response for the current classified-note run before mutating any theme, knowledge file, or note lifecycle. Each batch is then applied through one database transaction and one same-directory atomic knowledge-file replace. A rejected response appends only a safe `SYNTHESIS_REJECTED` event containing the output SHA-256 and error class, then raises the typed error; raw model output is never persisted or logged. `scripts/run_pipeline.py` will allow the typed error to propagate and exit non-zero; its top-level failure output contains only the safe error class and digest.

## P5.5 — KAE acquisition ingestion

`kae/acquisition.py` will provide these exact interfaces:

```python
class LocalAcquisitionStore:
    def acquire(self, request: AcquisitionRequest) -> AcquisitionReceipt: ...
    def get_bytes(self, content_hash: str) -> bytes: ...
    def inspect(self, source_id: str) -> AcquisitionReceipt: ...
    def revoke(self, source_id: str) -> None: ...
```

`AcquisitionRequest` contains `source_id`, `canonical_uri`, an absolute `source_path`, `source_type`, `RightsPolicy`, optional bibliographic metadata, and optional expected SHA-256. Before opening the file, the store requires a regular non-symlink file under one configured allowed root and rejects path components matching the restricted-scope policy (`sentium`, `trading`, `orders`, `positions`, `credentials`, `secrets`, `.env`, `token`, `cookies`, case-insensitive). This path policy is checked before any read and is the quarantine proof; no content scan is used to discover secrets. CAS bytes are written to `cas/<first-two-hash>/<hash>` using a same-directory temporary file, `fsync`, mode `0600`, and atomic replace.

The ledger will contain immutable `sources` rows and an append-only `source_events` table, both with update/delete rejection triggers. The latest event supplies status (`STORED`, `REVOKED`, `REJECTED`, or `QUARANTINED`); a repeated `(source_id, content_hash, canonical_uri)` is an idempotent no-op, while a conflicting identity raises `AcquisitionConflictError`. `get_bytes()` re-hashes CAS content and refuses revoked or corrupt records. The ledger will not fetch from the network, dispatch content to a model, promote knowledge, or modify LOF or Sentium stores. Existing citation extraction will consume the verified CAS reader without becoming the sole acquisition capability.

## Error and authority behavior

All malformed parameters, unavailable sources, corrupt CAS bytes, namespace crossings, invalid contradiction states, invalid model output, failed checkpoint writes, failed atomic file replacement, and unexpected exceptions fail closed. Observability events contain types, counts, hashes, and safe error classes only; they do not contain credentials, raw model output, absolute credential paths, or quarantined content. The only accepted real Orca research source for Court grounding is the explicit non-Sentium allowlist entry `backend/memory/formalized_ideas/emergent_complexity_as_a_design_principle_for_computational_intelligence.md`; all other Orca memory and scripts are excluded unless separately admitted by a future phase.

The PAEOS substrate APIs are read-only to external agent inspection. Orca may submit research-note inputs and receive candidate/advisory outputs, but it cannot promote Concept OS, SAKG, or KAE records and cannot exercise Sentium authority.

## Verification and audit design

The Phase 5 Court runner will be `ops/verify_substrate_capability_court.py`. It will define exactly six claims:

1. `CLAIM-P5-01-SAKG-CONTINUOUS-EXTRACTION-AND-LIVE-QUERY`
2. `CLAIM-P5-02-CONCEPT-OS-WAL-CANONICAL-URI-PERSISTENCE`
3. `CLAIM-P5-03-DISTILLATION-CONTRADICTION-GROUNDING`
4. `CLAIM-P5-04-IDEA-OS-SYNTHESIS-FAIL-CLOSED-PARSER`
5. `CLAIM-P5-05-KAE-DURABLE-ACQUISITION-CAS-INGESTION`
6. `CLAIM-P5-06-QUARANTINE-AND-AUTHORITY-CONTAINMENT`

Each claim runs a real command with `subprocess.run(..., capture_output=True, text=True, check=False)` in an isolated temporary directory; the evidence record stores the exact argv, return code, stdout, stderr, and safe environment metadata. The runner never writes expected result strings into the captured observation. The negative CANARY executes a separate deliberately failing subprocess with exit code `17`, passes its physical observation to the Court, and asserts `VerdictOutcome.REMAND` with a non-empty unmet-claims set. The Court's final artifact allowlist contains only the PAEOS Phase 5 source/tests/runner/docs and the explicitly admitted Orca parser/synthesis files; it excludes all credential-bearing files, Sentium surfaces, generated databases, and raw research content.

After the Court passes, the evidence bundle is hashed and audited through the admitted PAEOS Model Router transport by `google:gemini-3.6-flash`, with builder identity `openai:gpt-5.6-sol`. The receipt must be physically captured and verified by kernel Ed25519 attestation. The audit report must preserve any uncertainty and must not be promoted if the receipt is missing, synthetic, family-identical, or cryptographically invalid. If the governed PAEOS bridge produces no valid builder artifact, that is a remand/debt event and not a basis for claiming a PAEOS implementation seal.

## Governed execution protocol

1. Create a Phase 5 intake under `ops/backlogs/` with the exact file/write scope and run the canonical `uv run python ops/autonomous_run.py <intake> .state 1 25 chat-bridge` flow.
2. At each bridge prompt, inspect `current_prompt.md`, work only in the supplied sandbox, run the requested tests, and write `current_output.md`; never edit the PAEOS host root as a substitute.
3. Orca-only changes may be edited in its repository, but their tests and evidence remain restricted to the explicit parser/synthesis allowlist and non-Sentium note.
4. Before any Court run, validate the changed-file allowlist, absence of raw credentials, no Sentium/trading data admission, exact six-claim coverage, and the physical subprocess record shape.
5. After Court and Layer 14, append exact `Sealed`, `Remanded`, and `Remediated` accounting to `PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md` and `MessyChangesNeedsReview.md`; never suppress or optimize away remands.

## Expected verification surfaces

- PAEOS focused tests for `sakg/continuous.py`, live SAKG MCP queries, canonical Concept OS persistence, distillation, and KAE acquisition.
- Orca focused tests for synthesis parsing, contradiction validation, and fail-closed pipeline behavior.
- Full PAEOS regression suite and full Orca backend suite, plus the frontend build if touched by the wiring.
- Physical Court runner with exact sealed/remanded accounting.
- Layer 14 receipt/report pair validated by `adjudicate_auditor_artifact_pair` and `verify_transport_attestation`.
