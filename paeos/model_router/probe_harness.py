"""
PAEOS Model Router — Zero-Cost Live Provider Probe Harness
Safely tests active provider endpoints with minimal token overhead.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.transport import LiteLLMTransport
from paeos.model_router.types import (
    DataClass,
    ModelCatalogEntry,
    NormalizedError,
    ProviderId,
    TaskClass,
    TaskRequest,
)


def _provider_key(provider_id: ProviderId | str) -> str:
    """Render enum and extensible provider identities uniformly in probe evidence."""

    return provider_id.value if isinstance(provider_id, ProviderId) else provider_id


def probe_single_model(
    model_entry: ModelCatalogEntry,
    credentials: CredentialStore,
    transport: LiteLLMTransport,
    timeout: float = 20.0,
) -> Dict[str, Any]:
    """Runs a minimal live inference probe on a single candidate model."""
    req = TaskRequest(
        messages=[{"role": "user", "content": "Say hello!"}],
        task_class=TaskClass.ROUTINE,
        data_class=DataClass.PUBLIC,
        max_tokens=25,
        temperature=0.7,
    )

    start_time = time.time()
    try:
        resp = transport.dispatch(model_entry, req, timeout=timeout)
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "model_id": model_entry.model_id,
            "provider_id": _provider_key(model_entry.provider_id),
            "family": model_entry.family.value,
            "success": True,
            "latency_ms": round(latency_ms, 1),
            "response_snippet": resp.content.strip().replace("\n", " ")[:40],
            "tokens_used": resp.total_tokens,
            "cost_tier": model_entry.cost_tier.value,
            "pricing_verified_free": model_entry.pricing_verified_free,
            "live_verified": True,
            "available": True,
            "error": None,
        }
    except NormalizedError as e:
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "model_id": model_entry.model_id,
            "provider_id": _provider_key(model_entry.provider_id),
            "family": model_entry.family.value,
            "success": False,
            "latency_ms": round(latency_ms, 1),
            "response_snippet": None,
            "tokens_used": 0,
            "cost_tier": model_entry.cost_tier.value,
            "pricing_verified_free": model_entry.pricing_verified_free,
            "live_verified": False,
            "available": False,
            "error": f"[{e.error_type.value}] {e.message[:80]}",
        }
    except Exception as e:
        latency_ms = (time.time() - start_time) * 1000.0
        return {
            "model_id": model_entry.model_id,
            "provider_id": _provider_key(model_entry.provider_id),
            "family": model_entry.family.value,
            "success": False,
            "latency_ms": round(latency_ms, 1),
            "response_snippet": None,
            "tokens_used": 0,
            "cost_tier": model_entry.cost_tier.value,
            "pricing_verified_free": model_entry.pricing_verified_free,
            "live_verified": False,
            "available": False,
            "error": f"[UNCLASSIFIED] {str(e)[:80]}",
        }


def run_all_probes(
    credentials: Optional[CredentialStore] = None,
    catalog: Optional[ModelCatalog] = None,
) -> List[Dict[str, Any]]:
    """Runs probes across primary model candidates for each configured provider."""
    creds = credentials or CredentialStore()
    cat = catalog or ModelCatalog()
    transport = LiteLLMTransport(creds, cat)

    results = []
    # The registry is the source of provider identity.  Catalog entries are selected by their
    # normalized key, so adding a future provider does not require editing this harness.
    targets = [
        entry
        for descriptor in cat.provider_registry.snapshot()
        for entry in cat.list_models()
        if _provider_key(entry.provider_id) == descriptor.key
    ]

    for entry in targets:
        provider_id = _provider_key(entry.provider_id)
        if not creds.has_key(provider_id):
            results.append({
                "model_id": entry.model_id,
                "provider_id": provider_id,
                "family": "unknown",
                "success": False,
                "latency_ms": 0.0,
                "response_snippet": None,
                "tokens_used": 0,
                "cost_tier": "FREE",
                "pricing_verified_free": False,
                "live_verified": False,
                "available": False,
                "error": "[AUTH_FAILED] Missing or unconfigured API credential",
            })
            continue

        res = probe_single_model(entry, creds, transport)
        results.append(res)

    return results


if __name__ == "__main__":
    print("Executing PAEOS Model Router Live Provider Probes...")
    probe_results = run_all_probes()
    for r in probe_results:
        status = "✅ PASS" if r["success"] else "❌ FAIL"
        print(f"{status} [{r['provider_id'].upper()}] model={r['model_id']} cost={r['cost_tier']} live={r['live_verified']} latency={r['latency_ms']}ms snippet='{r['response_snippet']}' error={r['error']}")
