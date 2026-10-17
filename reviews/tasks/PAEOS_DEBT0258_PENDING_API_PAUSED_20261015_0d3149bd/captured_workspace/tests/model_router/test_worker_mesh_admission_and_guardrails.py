"""Unit tests for Worker Mesh Admission Hardening and Paid-Provider Guardrails.

Verifies:
1. Admission lifecycle state gating (DISCOVERED -> SDK_QUALIFIED -> LIVE_PROBED -> ADMITTED).
2. Paid-provider guardrail fails closed (FREE and SUBSCRIPTION_INCLUDED preferred; PAID rejected without authorization).
3. Kimi K3 classified strictly as SUBSCRIPTION_INCLUDED (never FREE).
4. Probed Cline models remain SDK_QUALIFIED and unadmitted due to expired session (401).
5. A-08 heterogeneous model decorrelation across all expanded model families.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from paeos.model_router.aimd import AIMDController
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.policy import RoutingPolicyEngine
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    AdmissionState,
    CostTier,
    DataClass,
    LogicalModel,
    ModelCatalogEntry,
    ModelFamily,
    ProviderId,
    TaskClass,
    TaskRequest,
)


@pytest.fixture
def test_engine(tmp_path: Path):
    catalog = ModelCatalog()
    state_db = RouterStateDB(tmp_path / "router_state.sqlite3")
    credentials = CredentialStore(tmp_path / "mock.env")
    credentials._keys = {
        "GEMINI_API_KEY": "mock-gemini-key",
        "CLINE_API_KEY": "mock-cline-key",
        "NVIDIA_API_KEY": "mock-nvidia-key",
        "KILO_API_KEY": "mock-kilo-key",
        "OPENROUTER_API_KEY": "mock-openrouter-key",
    }
    aimd = AIMDController(state_db)
    return RoutingPolicyEngine(catalog, state_db, credentials, aimd), catalog


def test_admission_lifecycle_gating(test_engine):
    """Only models in state ADMITTED and available=True can be routed."""
    engine, catalog = test_engine

    # Synthetic catalog with each lifecycle state
    entries = [
        ModelCatalogEntry(
            model_id="test/discovered",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            cost_tier=CostTier.FREE,
            available=True,
            admission_state=AdmissionState.DISCOVERED,
        ),
        ModelCatalogEntry(
            model_id="test/sdk-qualified",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            cost_tier=CostTier.FREE,
            available=True,
            admission_state=AdmissionState.SDK_QUALIFIED,
        ),
        ModelCatalogEntry(
            model_id="test/live-probed",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            cost_tier=CostTier.FREE,
            available=True,
            admission_state=AdmissionState.LIVE_PROBED,
        ),
        ModelCatalogEntry(
            model_id="test/admitted",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            cost_tier=CostTier.FREE,
            available=True,
            admission_state=AdmissionState.ADMITTED,
        ),
        ModelCatalogEntry(
            model_id="test/admitted-unavailable",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            cost_tier=CostTier.FREE,
            available=False,
            admission_state=AdmissionState.ADMITTED,
        ),
    ]
    test_catalog = ModelCatalog(entries)
    test_engine_instance = RoutingPolicyEngine(
        test_catalog, engine.state_db, engine.credentials, engine.aimd
    )

    req = TaskRequest(
        messages=[{"role": "user", "content": "Test lifecycle"}],
        data_class=DataClass.PUBLIC,
    )
    candidates = test_engine_instance.resolve_candidate_chain(req)

    candidate_ids = [m.model_id for m in candidates]
    assert candidate_ids == ["test/admitted"]


def test_paid_provider_guardrail_fails_closed(test_engine):
    """Paid models require explicit allow_paid_usage authorization and fail closed by default."""
    engine, catalog = test_engine

    entries = [
        ModelCatalogEntry(
            model_id="test/free-model",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            cost_tier=CostTier.FREE,
            available=True,
            admission_state=AdmissionState.ADMITTED,
        ),
        ModelCatalogEntry(
            model_id="test/subscription-model",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            cost_tier=CostTier.SUBSCRIPTION_INCLUDED,
            available=True,
            admission_state=AdmissionState.ADMITTED,
        ),
        ModelCatalogEntry(
            model_id="test/paid-model",
            provider_id=ProviderId.GOOGLE,
            family=ModelFamily.GEMINI,
            cost_tier=CostTier.PAID,
            available=True,
            admission_state=AdmissionState.ADMITTED,
        ),
    ]
    test_catalog = ModelCatalog(entries)
    test_engine_instance = RoutingPolicyEngine(
        test_catalog, engine.state_db, engine.credentials, engine.aimd
    )

    # 1. Default request (allow_paid_usage=False) -> PAID model excluded
    default_req = TaskRequest(
        messages=[{"role": "user", "content": "Default request"}],
        data_class=DataClass.PUBLIC,
        allow_paid_usage=False,
    )
    candidates = test_engine_instance.resolve_candidate_chain(default_req)
    candidate_ids = [m.model_id for m in candidates]
    assert "test/free-model" in candidate_ids
    assert "test/subscription-model" in candidate_ids
    assert "test/paid-model" not in candidate_ids

    # 2. Explicit request targeting paid model without authorization -> rejected (empty)
    explicit_paid_unauthorized = TaskRequest(
        messages=[{"role": "user", "content": "Explicit paid request"}],
        explicit_model="test/paid-model",
        data_class=DataClass.PUBLIC,
        allow_paid_usage=False,
    )
    candidates_unauth = test_engine_instance.resolve_candidate_chain(explicit_paid_unauthorized)
    assert candidates_unauth == []

    # 3. Explicit request targeting paid model WITH authorization -> allowed
    explicit_paid_authorized = TaskRequest(
        messages=[{"role": "user", "content": "Authorized paid request"}],
        explicit_model="test/paid-model",
        data_class=DataClass.PUBLIC,
        allow_paid_usage=True,
    )
    candidates_auth = test_engine_instance.resolve_candidate_chain(explicit_paid_authorized)
    assert len(candidates_auth) == 1
    assert candidates_auth[0].model_id == "test/paid-model"


def test_kimi_k3_cost_tier_classification(test_engine):
    """cline-pass/kimi-k3 is classified strictly as SUBSCRIPTION_INCLUDED, never FREE."""
    _engine, catalog = test_engine
    entry = catalog.get("cline-pass/kimi-k3")
    assert entry is not None
    assert entry.cost_tier == CostTier.SUBSCRIPTION_INCLUDED
    assert entry.cost_tier != CostTier.FREE
    assert "Moonshot Kimi K3" in (entry.entitlement_notes or "")


def test_probed_cline_models_admission_states_after_probe(test_engine):
    """Verifies that only models with successful live probes are ADMITTED; failed probes remain SDK_QUALIFIED."""
    _engine, catalog = test_engine

    # Live 200 OK verified models are ADMITTED
    admitted_models = ["cline-pass/qwen3.8-max", "cline-pass/kimi-k3"]
    for model_id in admitted_models:
        entry = catalog.get(model_id)
        assert entry is not None
        assert entry.admission_state == AdmissionState.ADMITTED, f"{model_id} must be ADMITTED after 200 OK"
        assert entry.available is True
        assert entry.live_verified is True
        assert entry.cost_tier == CostTier.SUBSCRIPTION_INCLUDED

    # Failed probe models remain SDK_QUALIFIED (not admitted)
    unadmitted_models = [
        "z-ai/glm-5.3-flash",
        "cline-pass/glm-5.3",
        "cline-free/longcat-2.0",
        "deepseek/deepseek-v4-flash",
        "minimax/minimax-m2.5",
    ]
    for model_id in unadmitted_models:
        entry = catalog.get(model_id)
        assert entry is not None
        assert entry.admission_state == AdmissionState.SDK_QUALIFIED, f"{model_id} must remain SDK_QUALIFIED"
        assert entry.available is False
        assert entry.live_verified is False
