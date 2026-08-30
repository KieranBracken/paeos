from __future__ import annotations

from pathlib import Path

from paeos.model_router.aimd import AIMDController
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.policy import RoutingPolicyEngine
from paeos.model_router.providers import ProviderDescriptor, ProviderRegistry
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    CostTier,
    DataClass,
    LogicalModel,
    ModelCatalogEntry,
    ModelFamily,
    ProviderId,
    TaskClass,
    TaskRequest,
)


def provider_descriptor(
    key: str,
    credential_env: str,
    *,
    strong_rank: int,
    allows_internal: bool = True,
    trains_on_inputs: bool = False,
) -> ProviderDescriptor:
    return ProviderDescriptor(
        key=key,
        credential_env=credential_env,
        transport_adapter_id=f"{key}-adapter",
        trains_on_inputs=trains_on_inputs,
        retains_prompts=trains_on_inputs,
        allows_internal=allows_internal,
        allows_confidential=allows_internal,
        max_rpm=17,
        max_tpm=20_000,
        max_rpd=90,
        preference_rank={LogicalModel.PAEOS_STRONG: strong_rank},
        task_fit={TaskClass.ROUTINE: 0.8, TaskClass.ARCHITECTURE: 0.9},
        quality_bias=0.1,
        latency_bias=0.1,
    )


def test_catalog_privacy_and_credentials_consume_descriptor_facts(tmp_path: Path) -> None:
    registry = ProviderRegistry(
        [
            provider_descriptor(
                "kilo",
                "SYNTHETIC_KILO_KEY",
                strong_rank=0,
                allows_internal=True,
                trains_on_inputs=False,
            )
        ]
    )
    catalog = ModelCatalog(
        [
            ModelCatalogEntry(
                model_id="synthetic/kilo",
                provider_id=ProviderId.KILO,
                family=ModelFamily.LLAMA,
                cost_tier=CostTier.FREE,
            )
        ],
        provider_registry=registry,
    )
    credentials = CredentialStore(tmp_path / "missing.env", provider_registry=registry)
    credentials._keys = {"SYNTHETIC_KILO_KEY": "test-only-key"}

    policy = catalog.get_data_policy(ProviderId.KILO)
    assert policy.allows_internal is True
    assert policy.trains_on_inputs is False
    assert credentials.get_key("kilo") == "test-only-key"


def test_descriptor_preference_controls_strong_tier_order(tmp_path: Path) -> None:
    registry = ProviderRegistry(
        [
            provider_descriptor("google", "GOOGLE_TEST_KEY", strong_rank=1),
            provider_descriptor("nvidia", "NVIDIA_TEST_KEY", strong_rank=0),
        ]
    )
    catalog = ModelCatalog(
        [
            ModelCatalogEntry(
                model_id="google/model",
                provider_id=ProviderId.GOOGLE,
                family=ModelFamily.GEMINI,
                cost_tier=CostTier.FREE,
            ),
            ModelCatalogEntry(
                model_id="nvidia/model",
                provider_id=ProviderId.NVIDIA,
                family=ModelFamily.LLAMA,
                cost_tier=CostTier.FREE,
            ),
        ],
        provider_registry=registry,
    )
    credentials = CredentialStore(tmp_path / "missing.env", provider_registry=registry)
    credentials._keys = {
        "GOOGLE_TEST_KEY": "google-test-key",
        "NVIDIA_TEST_KEY": "nvidia-test-key",
    }
    state_db = RouterStateDB(tmp_path / "router.sqlite3")
    aimd = AIMDController(state_db, provider_registry=registry)
    engine = RoutingPolicyEngine(catalog, state_db, credentials, aimd)

    candidates = engine.resolve_candidate_chain(
        TaskRequest(
            messages=[{"role": "user", "content": "architecture"}],
            logical_model=LogicalModel.PAEOS_STRONG,
            task_class=TaskClass.ARCHITECTURE,
            data_class=DataClass.PUBLIC,
        )
    )
    assert [candidate.provider_id for candidate in candidates] == [
        ProviderId.NVIDIA,
        ProviderId.GOOGLE,
    ]


def test_aimd_limits_are_loaded_from_descriptor_for_unlisted_legacy_defaults(
    tmp_path: Path,
) -> None:
    registry = ProviderRegistry([provider_descriptor("nvidia", "NVIDIA_TEST_KEY", strong_rank=0)])
    aimd = AIMDController(
        RouterStateDB(tmp_path / "router.sqlite3"),
        provider_registry=registry,
    )
    assert aimd.limits_for(ProviderId.NVIDIA) == {
        "max_rpm": 17,
        "max_tpm": 20_000,
        "max_rpd": 90,
    }
