# PAEOS Runtime-State Migration (DEBT-0057) Implementation Plan

> **Execution control:** Cline receives one bounded implementation task at a time and performs no
> skill or subagent routing. Codex applies the execution-plan discipline, independently verifies
> each task, and accepts or remands it. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the historical `.paeos_state` evidence outside source control, establish a new
external signing trust domain, eliminate repository-relative runtime writes, and prove that a
clean checkout contains no runtime state.

**Architecture:** Runtime persistence is explicit at composition roots. Historical state is copied
to a create-only external archive and verified from byte manifests before Git tracking changes.
The old signing key remains forensic-only; a fresh external state root receives a new key, empty
ledger genesis, and a public-fingerprint trust-cutoff record. Unit paths are either fixture-owned
or explicitly non-persistent.

**Tech Stack:** Python 3.13, pathlib, hashlib, shutil, dataclasses, PyNaCl Ed25519, SQLite ledger,
pytest, Git.

**Spec:** `docs/superpowers/specs/2026-08-25-paeos-control-plane-recovery-design.md` sections 5.1,
5.5, 10, and 13; `ledger/debt/DEBT-0057.md`.

## Global Constraints

- Work only in `/private/tmp/paeos-control-plane-recovery-s1-clean` on
  `codex/control-plane-recovery-s1-clean`.
- Cline is implementation-only. Codex supervises, runs independent verification, and accepts or
  remands each bounded task.
- Do not edit, clean, reset, merge, rebase, push, or promote `/Users/bob/GitHub/paeos`.
- The source tree `/Users/bob/GitHub/paeos/.paeos_state` is read-only during archival.
- Never print signing-key bytes, credential values, provider settings, database contents, Court
  row contents, or CAS blob contents.
- Do not rewrite Git history. Removal from tracking occurs only in the recovery branch index.
- An existing archive or new-state destination causes a fail-closed error; no overwrite flag
  exists.
- The old key may verify the frozen archive but may never be copied to or used by the new active
  state root.
- TDD is mandatory: one failing behavioral test, observed RED, minimal GREEN, then refactor.
- Preserve raw stdout, stderr, exit status, commit IDs, manifests, and hashes independently of
  worker summaries.
- No controlled canary, SAKG work, or live adapter activation is part of this plan.
- The retired GUI/clipboard scripts under `ops/chatgpt_bridge/` remain forensic compatibility
  history and are not activated here. Their replacement is Subproject 2; this plan removes the
  repository-relative default from every canonical live runtime composition path.

---

### Task 1: Make Sidecar Persistence Explicit and Hermetic

**Files:**

- Modify: `runtime/sidecar_scorer.py`
- Modify: `runtime/orchestrator/__init__.py`
- Modify: `runtime/selfhost.py`
- Modify: `ops/autonomous_run.py`
- Modify: `tests/runtime/test_sidecar_scorer.py`
- Modify: `tests/runtime/test_selfhost.py`
- Modify: `tests/runtime/test_transport.py`
- Modify: `tests/runtime/test_claude_cli_transport.py`
- Modify: `tests/runtime/test_soft_loop.py`
- Modify: `tests/runtime/test_r4_full_chain_proof.py`
- Modify: `tests/runtime/test_mcp_transport.py`

**Interfaces:**

- Produces: `SidecarStageScorer(storage_dir: Path | str | None)` where `None` means
  explicitly non-persistent scoring.
- Produces: required keyword-only `SoftLoop(..., sidecar_scorer: SidecarStageScorer)`.
- Consumes: production composition roots pass `SidecarStageScorer(state_dir / "evaluations")`;
  unit/self-host paths pass `SidecarStageScorer(None)` or a fixture-owned directory.

- [ ] **Step 1.1: Add the RED tests**

Add this behavior to `tests/runtime/test_sidecar_scorer.py`:

```python
import pytest


def test_nonpersistent_scorer_creates_no_runtime_tree(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    scorer = SidecarStageScorer(storage_dir=None)

    result = scorer.score_stage(
        run_id="r-hermetic",
        stage=StageId.RESEARCH,
        artifact_content="objective test assertion",
    )

    assert result.stage == StageId.RESEARCH.name
    assert not (tmp_path / ".paeos_state").exists()
```

Add a regression test to `tests/runtime/test_selfhost.py` using the existing scripted runtime and
fixture construction:

```python
import pytest

from runtime.selfhost import run_backlog


def test_selfhost_default_run_creates_no_repository_relative_evaluations(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    outcomes = run_backlog(
        [_intake(_GOOD)],
        ledger=Ledger(InMemoryLedgerStore()),
        signing_key=SigningKey.generate(),
        cas=CAS(InMemoryCasStore()),
        agent_runtime=ScriptedRuntime(),
    )
    assert outcomes
    assert not (tmp_path / ".paeos_state").exists()
```

Merge the imports into the file's existing import groups. Do not change the asserted behavior.

- [ ] **Step 1.2: Run RED and preserve output**

Run:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pytest -q \
  tests/runtime/test_sidecar_scorer.py \
  tests/runtime/test_selfhost.py
```

Expected: the new non-persistent constructor behavior fails because `Path(None)` is invalid, or
the self-host test exposes `.paeos_state/evaluations`. Record the exact failing assertion and exit
status once. Do not repeat RED before implementation.

- [ ] **Step 1.3: Implement explicit persistence**

In `runtime/sidecar_scorer.py`, use this shape:

```python
class SidecarStageScorer:
    def __init__(self, storage_dir: Path | str | None) -> None:
        self._storage_dir = None if storage_dir is None else Path(storage_dir).resolve()
        if self._storage_dir is not None:
            self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _persist(self, run_id: str, stage: StageId, payload: dict[str, Any]) -> None:
        if self._storage_dir is None:
            return
        out_path = self._storage_dir / f"{run_id}_{stage.name}_score.json"
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
```

Call `_persist(run_id, stage, score_obj.to_dict())` after score calculation. Scoring results must
remain identical whether or not persistence is enabled.

In `runtime/orchestrator/__init__.py`, add the required
`sidecar_scorer: SidecarStageScorer` keyword-only parameter immediately after
`budget_by_class`, and replace the hidden construction with the injected object:

```python
self._sidecar_scorer = sidecar_scorer
```

Update every `SoftLoop(` call. Production `ops/autonomous_run.py` must pass:

```python
sidecar_scorer=SidecarStageScorer(state_dir.resolve() / "evaluations"),
```

`runtime/selfhost.py` must pass `SidecarStageScorer(None)` unless an explicit scorer is added to
the `run_backlog` API. Tests pass `SidecarStageScorer(None)` except tests that assert files, which
pass `tmp_path / "evaluations"`.

- [ ] **Step 1.4: Run GREEN and the affected suite**

Run:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pytest -q \
  tests/runtime/test_sidecar_scorer.py \
  tests/runtime/test_selfhost.py \
  tests/runtime/test_transport.py \
  tests/runtime/test_claude_cli_transport.py \
  tests/runtime/test_soft_loop.py \
  tests/runtime/test_r4_full_chain_proof.py \
  tests/runtime/test_mcp_transport.py
```

Expected: exit 0, no repository-local `.paeos_state/evaluations` creation, and no warning output.

- [ ] **Step 1.5: Review and commit**

Review every `SoftLoop(` caller with `rg -n 'SoftLoop\(' --glob '*.py'`. Every caller must show an
explicit `sidecar_scorer=` binding. Commit:

```bash
git add runtime/sidecar_scorer.py runtime/orchestrator/__init__.py runtime/selfhost.py \
  ops/autonomous_run.py tests/runtime
git commit -m "fix(runtime): make sidecar persistence explicit"
```

---

### Task 2: Implement a Create-Only Historical-State Migration Utility

**Files:**

- Create: `ops/runtime_state_migration.py`
- Create: `tests/runtime/test_runtime_state_migration.py`

**Interfaces:**

- Produces: `manifest_tree(root: Path) -> tuple[ManifestEntry, ...]`.
- Produces: `manifest_digest(entries: tuple[ManifestEntry, ...]) -> str`.
- Produces:
  `freeze_historical_state(*, source_root: Path, archive_root: Path, archive_id: str, source_commit: str) -> FrozenArchive`.
- Produces:
  `initialize_fresh_state(*, new_state_root: Path, historical_key_path: Path, archive_manifest_hash: str) -> TrustDomain`.
- Produces: CLI requiring `--source-repo`, `--source-state`, `--archive-root`, `--archive-id`, and
  `--new-state-root`.

- [ ] **Step 2.1: Write discriminative RED tests**

Create `tests/runtime/test_runtime_state_migration.py` with literal fixtures and these behaviors:

```python
from __future__ import annotations

import json
import stat
from dataclasses import replace
from pathlib import Path

import pytest
from nacl.signing import SigningKey

from ops.runtime_state_migration import (
    ManifestEntry,
    MigrationError,
    fingerprint_signing_key,
    freeze_historical_state,
    initialize_fresh_state,
    manifest_digest,
    manifest_tree,
)


def _historical_state(root: Path) -> bytes:
    (root / "court").mkdir(parents=True)
    (root / "court" / "r-1.jsonl").write_text('{"evidence":"kept"}\n')
    (root / "ledger.db").write_bytes(b"historical-ledger")
    old_seed = bytes(SigningKey.generate())
    (root / "seal.key").write_bytes(old_seed)
    return old_seed


def test_archive_is_byte_exact_and_manifest_contains_no_secret_bytes(tmp_path: Path) -> None:
    source = tmp_path / "source"
    old_seed = _historical_state(source)
    frozen = freeze_historical_state(
        source_root=source,
        archive_root=tmp_path / "archives",
        archive_id="baseline",
        source_commit="a" * 40,
    )
    assert manifest_digest(manifest_tree(source)) == frozen.manifest_hash
    assert manifest_digest(manifest_tree(frozen.state_root)) == frozen.manifest_hash
    metadata = frozen.metadata_path.read_bytes()
    assert old_seed not in metadata
    assert json.loads(metadata)["source_commit"] == "a" * 40


def test_archive_refuses_existing_destination_and_source_symlink(tmp_path: Path) -> None:
    source = tmp_path / "source"
    _historical_state(source)
    archives = tmp_path / "archives"
    freeze_historical_state(
        source_root=source,
        archive_root=archives,
        archive_id="baseline",
        source_commit="b" * 40,
    )
    with pytest.raises(MigrationError, match="already exists"):
        freeze_historical_state(
            source_root=source,
            archive_root=archives,
            archive_id="baseline",
            source_commit="b" * 40,
        )
    (source / "escape").symlink_to(tmp_path / "outside")
    with pytest.raises(MigrationError, match="symlink"):
        manifest_tree(source)


def test_new_trust_domain_never_reuses_historical_seed(tmp_path: Path) -> None:
    historical = tmp_path / "historical.key"
    old_seed = bytes(SigningKey.generate())
    historical.write_bytes(old_seed)
    trust = initialize_fresh_state(
        new_state_root=tmp_path / "runtime-v2",
        historical_key_path=historical,
        archive_manifest_hash="c" * 64,
    )
    new_seed = (trust.state_root / "seal.key").read_bytes()
    assert new_seed != old_seed
    assert trust.old_public_fingerprint == fingerprint_signing_key(historical)
    assert trust.new_public_fingerprint == fingerprint_signing_key(trust.state_root / "seal.key")
    assert stat.S_IMODE((trust.state_root / "seal.key").stat().st_mode) == 0o600
    assert old_seed not in (trust.state_root / "trust-domain.json").read_bytes()
```

Add this exact source-drift test. It changes the third manifest result without mutating the fixture:

```python
def test_source_drift_fails_closed_and_preserves_partial_archive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import ops.runtime_state_migration as migration

    source = tmp_path / "source"
    _historical_state(source)
    real_manifest_tree = migration.manifest_tree
    calls = 0

    def drifting_manifest(root: Path) -> tuple[ManifestEntry, ...]:
        nonlocal calls
        calls += 1
        entries = real_manifest_tree(root)
        if calls == 3:
            return (replace(entries[0], sha256="0" * 64), *entries[1:])
        return entries

    monkeypatch.setattr(migration, "manifest_tree", drifting_manifest)
    archive = tmp_path / "archives" / "baseline"
    with pytest.raises(MigrationError, match="source changed during archival"):
        migration.freeze_historical_state(
            source_root=source,
            archive_root=tmp_path / "archives",
            archive_id="baseline",
            source_commit="d" * 40,
        )
    assert archive.is_dir()
    assert (archive / "state").is_dir()
```

The first call is the initial source manifest and the second is the copied archive manifest.

- [ ] **Step 2.2: Run RED once**

Run:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pytest -q \
  tests/runtime/test_runtime_state_migration.py
```

Expected: collection fails with `ModuleNotFoundError: ops.runtime_state_migration`.

- [ ] **Step 2.3: Implement immutable manifests and archive verification**

Create `ops/runtime_state_migration.py` with frozen records:

```python
@dataclass(frozen=True, slots=True)
class ManifestEntry:
    path: str
    size: int
    mode: int
    sha256: str


@dataclass(frozen=True, slots=True)
class FrozenArchive:
    archive_root: Path
    state_root: Path
    metadata_path: Path
    manifest_hash: str
    file_count: int


@dataclass(frozen=True, slots=True)
class TrustDomain:
    state_root: Path
    old_public_fingerprint: str
    new_public_fingerprint: str
    archive_manifest_hash: str


class MigrationError(RuntimeError):
    pass
```

`manifest_tree` must resolve the root once, reject missing/non-directory roots, reject symlinks and
non-regular files, sort relative POSIX paths, and hash file bytes without returning them.
`manifest_digest` canonicalizes only `path`, `size`, `mode`, and `sha256` using sorted compact JSON.

`freeze_historical_state` must:

1. validate `archive_id` as `[A-Za-z0-9._-]+`;
2. create `<archive_root>/<archive_id>` with no overwrite path;
3. calculate the source manifest;
4. copy into `<archive>/state` with `shutil.copy2`, preserving directories and never following
   symlinks;
5. calculate archive and second source manifests;
6. fail if either differs from the first source manifest;
7. write `manifest.json` and `metadata.json` with create-only file descriptors;
8. include source commit, manifest hash, file count, and UTC timestamp in metadata; and
9. return only paths, counts, and hashes.

No exception path may delete a partial archive.

- [ ] **Step 2.4: Implement new trust-domain initialization and CLI**

`fingerprint_signing_key` reads exactly a 32-byte Ed25519 seed, derives `SigningKey(seed).verify_key`,
and returns SHA-256 of the public verify-key bytes.

`initialize_fresh_state` must refuse an existing destination, create it with mode `0700`, call
`load_or_create_signing_key(new_state_root / "seal.key")`, initialize
`SqliteLedgerStore(new_state_root / "ledger.db")`, wrap it in `Ledger`, require both
`ledger.head() is None` and `ledger.verify_chain() == GENESIS_HASH`, then close the `Ledger` and
SQLite store. It writes
`trust-domain.json` containing:

```json
{
  "schema_version": 1,
  "status": "active",
  "historical_status": "forensic-only",
  "archive_manifest_hash": "<64 lowercase hex>",
  "old_public_fingerprint": "<64 lowercase hex>",
  "new_public_fingerprint": "<64 lowercase hex>",
  "created_at": "<UTC RFC3339>"
}
```

The CLI resolves the source Git commit with:

```python
completed = subprocess.run(
    ["git", "-C", str(source_repo), "rev-parse", "HEAD"],
    check=True,
    capture_output=True,
    text=True,
)
source_commit = completed.stdout.strip()
```

It validates that the result is 40 lowercase hexadecimal characters, freezes the archive,
then initializes the new trust domain using `frozen.state_root / "seal.key"` as the historical-key
source. It prints one compact JSON object containing only archive path, new-state path, commit,
file count, manifest hash, and public fingerprints. It never prints file contents or seeds.

- [ ] **Step 2.5: Run GREEN, lint, type-check, and commit**

Run:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pytest -q \
  tests/runtime/test_runtime_state_migration.py
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run ruff check \
  ops/runtime_state_migration.py tests/runtime/test_runtime_state_migration.py
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pyright \
  ops/runtime_state_migration.py
```

Expected: all exit 0 with no stderr. Commit:

```bash
git add ops/runtime_state_migration.py tests/runtime/test_runtime_state_migration.py
git commit -m "feat(ops): add evidence-aware runtime-state migration"
```

---

### Task 3: Freeze Production Evidence, Start a New Trust Domain, and Untrack Runtime State

**Files:**

- Modify: `.gitignore`
- Modify: `.github/workflows/ci.yml`
- Create: `tests/runtime/test_source_tree_state_hygiene.py`
- Remove from Git tracking only: every tracked `.paeos_state/**` path
- Create externally through the tested utility:
  `/Users/bob/.local/share/paeos/forensic-archives/2026-08-25-main-pre-recovery`
- Create externally through the tested utility:
  `/Users/bob/.local/share/paeos/runtime-v2`

**Interfaces:**

- Produces: a verified external historical archive and new external trust domain.
- Produces: repository invariant `git ls-files .paeos_state` is empty.
- Produces: CI fails if future runtime state is tracked.

- [ ] **Step 3.1: Write the RED source-hygiene test**

Create `tests/runtime/test_source_tree_state_hygiene.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def test_runtime_state_is_untracked_and_ignored() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "--", ".paeos_state"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    )
    assert tracked.stdout == ""

    ignored = subprocess.run(
        ["git", "check-ignore", "--no-index", ".paeos_state/runtime-hygiene-probe"],
        cwd=REPO,
        check=False,
        capture_output=True,
        text=True,
    )
    assert ignored.returncode == 0
```

- [ ] **Step 3.2: Run RED once**

Run:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pytest -q \
  tests/runtime/test_source_tree_state_hygiene.py
```

Expected: failure showing tracked `.paeos_state` paths.

- [ ] **Step 3.3: Execute the create-only external migration**

First verify that no `autonomous_run.py`, `monitor_loop.py`, PAEOS bridge, or PAEOS watchdog
process can be writing the Founder checkout state. If any matching writer is live, halt and report
it; do not terminate it under this plan. Then run the tested utility outside the filesystem sandbox
because the destinations are beneath
`/Users/bob/.local/share/paeos`:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run python \
  ops/runtime_state_migration.py \
  --source-repo /Users/bob/GitHub/paeos \
  --source-state /Users/bob/GitHub/paeos/.paeos_state \
  --archive-root /Users/bob/.local/share/paeos/forensic-archives \
  --archive-id 2026-08-25-main-pre-recovery \
  --new-state-root /Users/bob/.local/share/paeos/runtime-v2
```

Expected: exit 0 and compact metadata-only JSON. Preserve stdout/stderr verbatim. Independently
recalculate source and archive manifests with the same utility API and require equal hashes before
continuing. If either destination already exists, halt and inspect; do not delete or reuse it.

- [ ] **Step 3.4: Ignore and remove runtime state from the recovery-branch index**

Replace the partial runtime ignore block in `.gitignore` with:

```gitignore
# Runtime state and evidence live under an explicit external state root.
.paeos_state/
.state/
state_sakg/
```

Add a CI F3 check in `.github/workflows/ci.yml` immediately after the existing key-material check:

```bash
if git ls-files -- .paeos_state | grep -q .; then
  echo "runtime state committed beneath .paeos_state"; exit 1
fi
```

Use Git index removal that preserves the working files:

```bash
git rm --cached -r .paeos_state
```

Do not run filesystem deletion. Verify `.paeos_state/seal.key` still exists in the worktree and is
ignored, without reading or printing it.

- [ ] **Step 3.5: Run GREEN and commit the source-hygiene boundary**

Run:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pytest -q \
  tests/runtime/test_source_tree_state_hygiene.py
git ls-files .paeos_state
git check-ignore --no-index .paeos_state/runtime-hygiene-probe
```

Expected: pytest exit 0; `git ls-files` exit 0 with empty stdout; `git check-ignore` exit 0.

Commit the index changes, `.gitignore`, CI gate, and test together:

```bash
git add .gitignore .github/workflows/ci.yml tests/runtime/test_source_tree_state_hygiene.py
git commit -m "fix(state): remove runtime evidence from source control"
```

---

### Task 4: Verify Migration, Falsify Safety Checks, and Record Disposition

**Files:**

- Modify: `ledger/debt/DEBT-0057.md`
- Create: `reviews/tasks/PAEOS_RUNTIME_STATE_MIGRATION_DEBT_0057_review.md`
- Modify in the Founder checkout only as an audit log append:
  `/Users/bob/GitHub/paeos/PAEOS_HALLUCINATION_CHECKER_NOTEBOOK.md`

**Interfaces:**

- Consumes: Tasks 1-3 commits and external archive metadata.
- Produces: raw L13 evidence, mutation evidence, L17 review, and honest debt status.

- [ ] **Step 4.1: Capture manifests and repository state before verification**

Record without reading secret contents:

```bash
git status --short --branch
git rev-parse HEAD
git ls-files .paeos_state
df -h /private/tmp
```

Use `ops.runtime_state_migration.manifest_tree` to record the main source-state and external archive
manifest hashes. They must match the frozen metadata. Record the new trust-domain public
fingerprints and require they differ. Do not output key bytes.

- [ ] **Step 4.2: Run focused and full verification**

Run focused:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pytest -q \
  tests/runtime/test_sidecar_scorer.py \
  tests/runtime/test_selfhost.py \
  tests/runtime/test_runtime_state_migration.py \
  tests/runtime/test_source_tree_state_hygiene.py
```

Run the full suite outside the restrictive socket sandbox:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pytest -q
```

Then run:

```bash
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run ruff check .
env UV_CACHE_DIR=/tmp/paeos-recovery-spec-uv-cache uv run pyright
```

Require exit 0, empty stderr, and exact raw output. If free space is below 300 MiB before the full
suite, remove only rebuildable caches or verified duplicate extraction directories; preserve logs,
archives, worktrees, and runtime evidence.

- [ ] **Step 4.3: Run four reversible seeded mutations**

For each mutation, alter one condition, run only the named test, preserve the expected failure,
and restore the file before the next mutation:

1. Restore the old `SidecarStageScorer()` repository-relative default; run
   `test_nonpersistent_scorer_creates_no_runtime_tree` and require failure.
2. Permit an existing archive destination; run
   `test_archive_refuses_existing_destination_and_source_symlink` and require failure.
3. Copy the historical seed into the fresh-state initializer in the test sandbox; run
   `test_new_trust_domain_never_reuses_historical_seed` and require failure.
4. Remove `.paeos_state/` from `.gitignore`; run `test_runtime_state_is_untracked_and_ignored` and
   require failure.

After restoration, require `git diff --check` and rerun the focused suite once.

- [ ] **Step 4.4: Update debt and L17 review honestly**

Update `DEBT-0057.md` with implementation commit IDs, external archive path, manifest hash, new
state-root path, old/new public fingerprints, and verification anchors. Do not mark it closed if
the Founder/operator has not confirmed Cline credential rotation; record
`IMPLEMENTATION_REPAID_OPERATOR_ACTION_OPEN` and name the remaining action exactly.

Write `reviews/tasks/PAEOS_RUNTIME_STATE_MIGRATION_DEBT_0057_review.md` using the mandatory
constitutional review checklist. Distinguish tracked-state remediation from the unrelated Cline
transport and live adapter. Append the same concise finding and evidence anchors to the main
notebook without modifying any other dirty main-checkout file.

- [ ] **Step 4.5: Commit audit artifacts and stop at the next gate**

```bash
git add ledger/debt/DEBT-0057.md \
  reviews/tasks/PAEOS_RUNTIME_STATE_MIGRATION_DEBT_0057_review.md
git commit -m "docs(review): record runtime-state migration disposition"
```

Report exact test counts, stderr sizes, exit codes, manifest hashes, mutation outcomes, and current
debt status. Do not begin a canary, live adapter, SAKG work, or promotion. The next permitted plan
is Subproject 3 worker admission.

## Execution Handoff

Execute inline with `superpowers:executing-plans`. The current recovery rules prohibit unrequested
subagents. Cline remains the sole implementation worker; Codex reviews each task and performs
independent verification. Stop immediately on an unclear plan step, credential exposure, source
state mutation, archive mismatch, identical failed-command repetition, or write outside the
allowlist.
