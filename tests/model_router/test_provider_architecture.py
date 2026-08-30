"""Architecture and decorrelation invariants for the provider-neutral router core."""

import ast
from pathlib import Path

from paeos.model_router.a08_enforcer import A08Enforcer, A08Verdict
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.providers import ProviderDescriptor, ProviderRegistry, build_builtin_provider_registry
from paeos.model_router.types import CostTier, LogicalModel, ModelCatalogEntry, ModelFamily, TaskClass


ROOT = Path(__file__).parents[2]


def test_core_modules_do_not_branch_on_provider_enum_or_builtin_names() -> None:
    modules = (
        ROOT / "paeos/model_router/router.py",
        ROOT / "paeos/model_router/policy.py",
        ROOT / "paeos/model_router/transport.py",
        ROOT / "runtime/control_plane/coordinator.py",
        ROOT / "kernel/lifecycle.py",
        ROOT / "paeos/model_router/audit.py",
    )
    forbidden_names = {"ProviderId", "google", "cline", "nvidia", "kilo", "openrouter"}
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert node.id != "ProviderId", f"provider enum branch remains in {path}"
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value.casefold() not in forbidden_names, (
                    f"built-in provider literal remains in {path}: {node.value!r}"
                )


def test_synthetic_provider_uses_family_inequality_not_provider_identity() -> None:
    registry = ProviderRegistry(
        list(build_builtin_provider_registry().snapshot())
        + [
            ProviderDescriptor(
                key="future-provider",
                credential_env="FUTURE_PROVIDER_KEY",
                transport_adapter_id="future-adapter",
                trains_on_inputs=False,
                retains_prompts=False,
                allows_internal=True,
                allows_confidential=True,
                max_rpm=5,
                max_tpm=5_000,
                max_rpd=50,
                preference_rank={model: 1 for model in LogicalModel},
                task_fit={TaskClass.AUDIT: 1.0},
                quality_bias=0.5,
                latency_bias=0.5,
            )
        ]
    )
    catalog = ModelCatalog(
        entries=[
            ModelCatalogEntry(
                model_id="future/auditor",
                provider_id="future-provider",  # type: ignore[arg-type]
                family=ModelFamily.GLM,
                cost_tier=CostTier.FREE,
            )
        ],
        provider_registry=registry,
    )
    enforcer = A08Enforcer(catalog)
    passed = enforcer.enforce(
        builder_provider="future-provider",
        builder_model_id="builder/unknown",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="future-provider",
        auditor_model_id="future/auditor",
        auditor_family=ModelFamily.GLM,
    )
    assert passed.verdict is A08Verdict.PASS

    unknown = enforcer.enforce(
        builder_provider="future-provider",
        builder_model_id="builder/unknown",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="future-provider",
        auditor_model_id="future/auditor",
        auditor_family=ModelFamily.UNKNOWN,
    )
    assert unknown.verdict is A08Verdict.FAIL_UNKNOWN_AUDITOR

    conflicting = enforcer.enforce(
        builder_provider="future-provider",
        builder_model_id="builder/unknown",
        builder_family=ModelFamily.GEMINI,
        auditor_provider="future-provider",
        auditor_model_id="future/auditor",
        auditor_family=ModelFamily.MINIMAX,
    )
    assert conflicting.verdict is A08Verdict.FAIL_CONFLICTING_EVIDENCE
