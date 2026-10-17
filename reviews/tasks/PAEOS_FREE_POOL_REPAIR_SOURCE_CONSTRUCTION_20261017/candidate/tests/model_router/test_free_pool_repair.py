"""Provider-free regression tests for retired routes and quota reset handling."""
from __future__ import annotations
import importlib
import sys
import time
import types
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[2]
PAEOS_ROOT = ROOT / "paeos"
def install_namespace(name: str, directory: Path) -> None:
    module = types.ModuleType(name)
    module.__path__ = [str(directory)]
    module.__package__ = name
    sys.modules[name] = module
install_namespace("paeos", PAEOS_ROOT)
install_namespace("paeos.model_router", PAEOS_ROOT / "model_router")
catalog = importlib.import_module("paeos.model_router.catalog")
errors = importlib.import_module("paeos.model_router.errors")
policy = importlib.import_module("paeos.model_router.intelligence_tier")
aimd = importlib.import_module("paeos.model_router.aimd")
state = importlib.import_module("paeos.model_router.state")
types_module = importlib.import_module("paeos.model_router.types")
RETIRED = "meta/llama-3.1-8b-instruct"
def quota(body):
    return errors.normalize_error(429, body, provider_id=types_module.ProviderId.GOOGLE, model_id="gemini-3.6-flash")
def test_retired_model_is_absent_from_catalog_pools_and_fallbacks():
    assert all(entry.model_id != RETIRED for entry in catalog.INITIAL_MODEL_CATALOG)
    assert RETIRED not in policy.ADMITTED_FREE_WORKER_POOL
    assert RETIRED not in policy.QUALIFIED_FREE_WORKER_POOL
    router = policy.IntelligencePolicyRouter()
    assert RETIRED not in router.assign_model(policy.TaskContext()).fallback_models
    for tier in (policy.IntelligenceTier.ROUTINE_MECHANICAL, policy.IntelligenceTier.ARCHITECTURAL_HIGH_CONSEQUENCE):
        assigned = router._assign_heterogeneous_auditor(tier, policy.TaskContext(role="auditor"))
        assert RETIRED not in assigned.fallback_models
def test_google_retry_info_duration_is_preserved():
    err = quota({"error": {"message": "Quota exceeded", "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "24461s"}]}})
    assert err.error_type is types_module.NormalizedErrorType.QUOTA_EXHAUSTED
    assert err.retry_after == 24461.0
@pytest.mark.parametrize("details", [[], [{"@type": "type.googleapis.com/google.rpc.RetryInfo"}], [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "bad"}], [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "0s"}], [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "-1s"}], [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "NaNs"}], [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "Infinitys"}]])
def test_invalid_retry_info_has_no_synthetic_reset(details):
    err = quota({"error": {"message": "Daily free limit reached", "details": details}})
    assert err.error_type is types_module.NormalizedErrorType.QUOTA_EXHAUSTED
    assert err.retry_after is None
def test_valid_reset_cools_down_then_recovers_without_provider_call(tmp_path):
    db = state.RouterStateDB(tmp_path / "router.sqlite3")
    controller = aimd.AIMDController(db)
    err = quota({"error": {"message": "Quota exceeded", "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "0.05s"}]}})
    controller.on_error(types_module.ProviderId.GOOGLE, err)
    row = db.get_provider_state(types_module.ProviderId.GOOGLE)
    assert row["health_status"] == types_module.ProviderHealth.COOLDOWN.value
    assert row["cooldown_until"] > time.time()
    admitted, reason = controller.check_admission(types_module.ProviderId.GOOGLE)
    assert not admitted and "COOLDOWN" in reason
    time.sleep(0.07)
    admitted, reason = controller.check_admission(types_module.ProviderId.GOOGLE)
    assert admitted and reason is None
def test_missing_reset_stays_exhausted(tmp_path):
    db = state.RouterStateDB(tmp_path / "router.sqlite3")
    controller = aimd.AIMDController(db)
    controller.on_error(types_module.ProviderId.GOOGLE, quota({"error": {"message": "Quota exceeded"}}))
    row = db.get_provider_state(types_module.ProviderId.GOOGLE)
    assert row["health_status"] == types_module.ProviderHealth.EXHAUSTED.value
    admitted, reason = controller.check_admission(types_module.ProviderId.GOOGLE)
    assert not admitted and "EXHAUSTED" in reason
def test_focused_imports_resolve_inside_workspace():
    for module in (catalog, errors, policy, aimd, state):
        assert Path(module.__file__).resolve().is_relative_to(ROOT)
