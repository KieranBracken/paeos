"""
Adversarial Unit Tests: SQLite WAL Concurrency, State Persistence, and AIMD Engine
"""
import threading
import time
from pathlib import Path

from paeos.model_router.aimd import AIMDController
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import (
    ModelFamily,
    NormalizedError,
    NormalizedErrorType,
    ProviderHealth,
    ProviderId,
)


def test_sqlite_wal_concurrent_mutations(tmp_path: Path):
    """Multiple threads updating provider usage and active slots in WAL mode without database locked errors."""
    db_file = tmp_path / "state.sqlite3"
    state_db = RouterStateDB(db_file)

    def worker_task(thread_id: int):
        for _ in range(25):
            state_db.record_usage(ProviderId.NVIDIA, prompt_tokens=100, completion_tokens=50)
            state_db.log_observation(
                task_class="IMPLEMENTATION",
                logical_model="paeos-code",
                model_id="meta/llama-3.1-8b-instruct",
                provider_id=ProviderId.NVIDIA,
                family=ModelFamily.LLAMA,
                latency_ms=120.0,
                prompt_tokens=100,
                completion_tokens=50,
                success=True,
            )

    threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    state = state_db.get_provider_state(ProviderId.NVIDIA)
    assert state["total_requests_today"] == 8 * 25
    assert state["total_tokens_today"] == 8 * 25 * 150


def test_state_restart_persistence(tmp_path: Path):
    """State and cooldowns persist across database restarts."""
    db_file = tmp_path / "state.sqlite3"
    db1 = RouterStateDB(db_file)
    db1.set_health(
        ProviderId.GOOGLE,
        health=ProviderHealth.COOLDOWN,
        error_type=NormalizedErrorType.RATE_LIMITED,
        cooldown_seconds=45.0,
    )
    db1.update_concurrency(ProviderId.GOOGLE, 4)

    db2 = RouterStateDB(db_file)
    state = db2.get_provider_state(ProviderId.GOOGLE)
    assert state["health_status"] == ProviderHealth.COOLDOWN.value
    assert state["current_concurrency"] == 4
    assert state["cooldown_until"] is not None
    assert state["last_error_type"] == NormalizedErrorType.RATE_LIMITED.value


def test_aimd_multiplicative_decrease_on_429(tmp_path: Path):
    """AIMD halves concurrency on 429 and sets cooldown."""
    db_file = tmp_path / "state.sqlite3"
    state_db = RouterStateDB(db_file)
    aimd = AIMDController(state_db)

    state_db.update_concurrency(ProviderId.NVIDIA, 6)

    err = NormalizedError(
        error_type=NormalizedErrorType.RATE_LIMITED,
        message="Too many requests",
        provider_id=ProviderId.NVIDIA,
        retry_after=20.0,
    )
    cooldown = aimd.on_rate_limit(ProviderId.NVIDIA, err)

    assert cooldown == 20.0
    st = state_db.get_provider_state(ProviderId.NVIDIA)
    assert st["current_concurrency"] == 3
    assert st["health_status"] == ProviderHealth.COOLDOWN.value


def test_aimd_cooldown_recovery_and_reentry(tmp_path: Path):
    """After cooldown expiration, admission check recovers provider at concurrency=1."""
    db_file = tmp_path / "state.sqlite3"
    state_db = RouterStateDB(db_file)
    aimd = AIMDController(state_db)

    state_db.set_health(
        ProviderId.NVIDIA,
        health=ProviderHealth.COOLDOWN,
        error_type=NormalizedErrorType.RATE_LIMITED,
        cooldown_seconds=0.1,
    )
    state_db.update_concurrency(ProviderId.NVIDIA, 4)

    time.sleep(0.2)

    admitted, reason = aimd.check_admission(ProviderId.NVIDIA)
    assert admitted is True
    assert reason is None

    st = state_db.get_provider_state(ProviderId.NVIDIA)
    assert st["health_status"] == ProviderHealth.HEALTHY.value
    assert st["current_concurrency"] == 1
