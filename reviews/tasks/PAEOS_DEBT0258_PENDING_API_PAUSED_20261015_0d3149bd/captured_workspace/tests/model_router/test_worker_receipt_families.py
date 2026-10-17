from __future__ import annotations

from paeos.model_router.a08_enforcer import derive_family_from_actual_model
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.types import ModelFamily


def test_qwen_receipt_resolves_to_qwen_family() -> None:
    assert (
        derive_family_from_actual_model("cline-pass/qwen3.8-max", ModelCatalog())
        is ModelFamily.QWEN
    )


def test_gpt_receipt_resolves_to_gpt_family() -> None:
    assert (
        derive_family_from_actual_model("openai/gpt-5.6-sol", ModelCatalog())
        is ModelFamily.GPT
    )


def test_free_router_selected_model_remains_unknown() -> None:
    assert (
        derive_family_from_actual_model(
            "free-router-selected-model", ModelCatalog()
        )
        is ModelFamily.UNKNOWN
    )


def test_openai_gptcompatible_remains_unknown() -> None:
    assert (
        derive_family_from_actual_model("openai/gptcompatible", ModelCatalog())
        is ModelFamily.UNKNOWN
    )
