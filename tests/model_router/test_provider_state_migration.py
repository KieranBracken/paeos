"""Compatibility tests for extensible provider keys in durable router state."""

import sqlite3
from pathlib import Path

import pytest

from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.observability import ObservabilityDiagnostics
from paeos.model_router.probe_harness import run_all_probes
from paeos.model_router.providers import ProviderDescriptor, ProviderRegistry, build_builtin_provider_registry
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    LogicalModel,
    ModelCatalogEntry,
    ModelFamily,
    ProviderHealth,
    ProviderId,
    TaskClass,
)


def _future_registry() -> ProviderRegistry:
    descriptors = list(build_builtin_provider_registry().snapshot())
    descriptors.append(
        ProviderDescriptor(
            key="future-provider",
            credential_env="FUTURE_PROVIDER_KEY",
            transport_adapter_id="future-adapter",
            trains_on_inputs=False,
            retains_prompts=False,
            allows_internal=True,
            allows_confidential=True,
            max_rpm=7,
            max_tpm=10_000,
            max_rpd=99,
            preference_rank={model: 9 for model in LogicalModel},
            task_fit={TaskClass.ROUTINE: 0.5},
            quality_bias=0.5,
            latency_bias=0.5,
        )
    )
    return ProviderRegistry(descriptors)


def test_legacy_rows_survive_restart_and_future_key_round_trips(tmp_path: Path) -> None:
    db_file = tmp_path / "state.sqlite3"
    state = RouterStateDB(db_file, provider_registry=_future_registry())
    state.set_health(ProviderId.GOOGLE, ProviderHealth.COOLDOWN, cooldown_seconds=45.0)
    state.update_concurrency(ProviderId.GOOGLE, 4)

    # Simulate a row created by a newer provider descriptor without changing the schema.
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            "UPDATE providers SET health_status = ?, current_concurrency = ?, total_requests_today = ? "
            "WHERE provider_id = ?",
            (ProviderHealth.THROTTLED.value, 3, 11, "future-provider"),
        )

    reopened = RouterStateDB(db_file, provider_registry=_future_registry())
    google = reopened.get_provider_state("google")
    future = reopened.get_provider_state("future-provider")
    assert google["health_status"] == ProviderHealth.COOLDOWN.value
    assert google["current_concurrency"] == 4
    assert future["health_status"] == ProviderHealth.THROTTLED.value
    assert future["current_concurrency"] == 3
    assert future["total_requests_today"] == 11


def test_unknown_valid_key_is_persistable_without_enum_member(tmp_path: Path) -> None:
    db_file = tmp_path / "state.sqlite3"
    state = RouterStateDB(db_file, provider_registry=_future_registry())
    state.record_usage("future-provider", prompt_tokens=4, completion_tokens=6)
    state.log_observation(
        task_class="ROUTINE",
        logical_model="paeos-auto",
        model_id="future/model",
        provider_id="future-provider",
        family=ModelFamily.UNKNOWN,
        latency_ms=12.0,
        prompt_tokens=4,
        completion_tokens=6,
        success=True,
    )
    assert state.get_window_usage("future-provider")[0] == 1
    assert state.get_recent_metrics("future-provider")["total"] == 1


def test_invalid_provider_key_fails_closed_and_never_aliases(tmp_path: Path) -> None:
    db_file = tmp_path / "state.sqlite3"
    state = RouterStateDB(db_file)
    with pytest.raises(ValueError):
        state.get_provider_state("Future_Provider")
    with pytest.raises(ValueError):
        state.record_usage("../google", 1, 1)
    with sqlite3.connect(db_file) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM providers WHERE provider_id IN ('Future_Provider', '../google')"
        ).fetchone()[0] == 0

    with sqlite3.connect(db_file) as conn:
        conn.execute("INSERT INTO providers (provider_id) VALUES ('Future_Provider')")
    with pytest.raises(ValueError, match="invalid provider identities"):
        RouterStateDB(db_file)


def test_observability_and_probe_harness_use_registry_snapshot(tmp_path: Path) -> None:
    registry = _future_registry()
    future_entry = ModelCatalogEntry(
        model_id="future/model",
        provider_id="future-provider",  # extensible key; no ProviderId enum member
        family=ModelFamily.UNKNOWN,
    )
    catalog = ModelCatalog(entries=[future_entry], provider_registry=registry)
    state = RouterStateDB(tmp_path / "state.sqlite3", provider_registry=registry)
    credentials = CredentialStore(env_file=tmp_path / "missing.env", provider_registry=registry)
    status = ObservabilityDiagnostics(state, catalog, credentials, provider_registry=registry).get_mesh_status()
    assert "future-provider" in status["providers"]

    # No credential means no network call; the registry-derived target still appears in evidence.
    results = run_all_probes(credentials=credentials, catalog=catalog)
    future_result = next(item for item in results if item["provider_id"] == "future-provider")
    assert future_result["success"] is False
    assert future_result["error"].startswith("[AUTH_FAILED]")
