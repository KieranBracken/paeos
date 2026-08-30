"""
PAEOS Model Router — Concurrent SQLite WAL State Engine
"""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from paeos.model_router.types import (
    ModelFamily,
    NormalizedErrorType,
    ProviderHealth,
    ProviderKey,
    ProviderId,
)
from paeos.model_router.providers import ProviderRegistry, build_builtin_provider_registry, normalize_provider_key


DEFAULT_DB_PATH = Path.home() / ".local" / "share" / "paeos" / "model-router" / "state.sqlite3"


class RouterStateDB:
    def __init__(
        self,
        db_path: Optional[Path] = None,
        provider_registry: Optional[ProviderRegistry] = None,
    ):
        self.db_path = db_path or DEFAULT_DB_PATH
        self.provider_registry = provider_registry or build_builtin_provider_registry()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @staticmethod
    def _provider_key(provider_id: ProviderId | ProviderKey) -> ProviderKey:
        """Normalize provider identity at the persistence boundary.

        SQLite stores canonical text keys.  The legacy ``ProviderId`` enum remains accepted for
        callers, while validated future-provider strings can be persisted without an enum change.
        """

        return normalize_provider_key(provider_id)

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS providers (
                provider_id TEXT PRIMARY KEY,
                health_status TEXT NOT NULL DEFAULT 'HEALTHY',
                current_concurrency INTEGER NOT NULL DEFAULT 2,
                max_concurrency INTEGER NOT NULL DEFAULT 10,
                min_concurrency INTEGER NOT NULL DEFAULT 1,
                active_requests INTEGER NOT NULL DEFAULT 0,
                cooldown_until REAL,
                last_error_type TEXT,
                last_error_time REAL,
                consecutive_healthy_since REAL,
                total_requests_today INTEGER DEFAULT 0,
                total_tokens_today INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS provider_windows (
                provider_id TEXT NOT NULL,
                window_type TEXT NOT NULL,
                window_start REAL NOT NULL,
                request_count INTEGER DEFAULT 0,
                token_count INTEGER DEFAULT 0,
                PRIMARY KEY (provider_id, window_type, window_start)
            );

            CREATE TABLE IF NOT EXISTS routing_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                task_class TEXT NOT NULL,
                logical_model TEXT,
                model_id TEXT NOT NULL,
                provider_id TEXT NOT NULL,
                family TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                success INTEGER NOT NULL,
                normalized_error TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_obs_time ON routing_observations(timestamp);
            CREATE INDEX IF NOT EXISTS idx_obs_prov ON routing_observations(provider_id, success);
            """)

            # Existing state is authoritative but must still satisfy the provider-key grammar.
            # Refuse startup on malformed rows rather than silently aliasing them to a valid key.
            persisted_keys = set()
            for table in ("providers", "provider_windows", "routing_observations"):
                rows = conn.execute(f"SELECT DISTINCT provider_id FROM {table}").fetchall()
                persisted_keys.update(row[0] for row in rows)
            invalid_keys = []
            for key in persisted_keys:
                try:
                    normalize_provider_key(key)
                except (TypeError, ValueError):
                    invalid_keys.append(repr(key))
            if invalid_keys:
                raise ValueError(
                    "invalid provider identities in durable state; refusing startup: "
                    + ", ".join(sorted(invalid_keys))
                )

            for descriptor in self.provider_registry.snapshot():
                conn.execute("""
                INSERT OR IGNORE INTO providers (
                    provider_id, health_status, current_concurrency, max_concurrency, min_concurrency,
                    active_requests, consecutive_healthy_since
                ) VALUES (?, 'HEALTHY', 2, 10, 1, 0, ?)
                """, (descriptor.key, time.time()))

    def get_provider_state(self, provider_id: ProviderId | ProviderKey) -> Dict[str, Any]:
        provider_key = self._provider_key(provider_id)
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM providers WHERE provider_id = ?", (provider_key,)).fetchone()
            if row:
                return dict(row)
            return {
                "provider_id": provider_key,
                "health_status": ProviderHealth.HEALTHY.value,
                "current_concurrency": 2,
                "max_concurrency": 10,
                "min_concurrency": 1,
                "active_requests": 0,
                "cooldown_until": None,
                "last_error_type": None,
                "last_error_time": None,
                "consecutive_healthy_since": time.time(),
                "total_requests_today": 0,
                "total_tokens_today": 0,
            }

    def set_health(
        self,
        provider_id: ProviderId | ProviderKey,
        health: ProviderHealth,
        error_type: Optional[NormalizedErrorType] = None,
        cooldown_seconds: Optional[float] = None,
    ) -> None:
        provider_key = self._provider_key(provider_id)
        now = time.time()
        cooldown_until = (now + cooldown_seconds) if cooldown_seconds else None

        with self._get_connection() as conn:
            if health == ProviderHealth.HEALTHY:
                conn.execute("""
                UPDATE providers
                SET health_status = 'HEALTHY',
                    cooldown_until = NULL,
                    consecutive_healthy_since = COALESCE(consecutive_healthy_since, ?)
                WHERE provider_id = ?
                """, (now, provider_key))
            else:
                conn.execute("""
                UPDATE providers
                SET health_status = ?,
                    cooldown_until = COALESCE(?, cooldown_until),
                    last_error_type = COALESCE(?, last_error_type),
                    last_error_time = CASE WHEN ? IS NOT NULL THEN ? ELSE last_error_time END,
                    consecutive_healthy_since = NULL
                WHERE provider_id = ?
                """, (
                    health.value,
                    cooldown_until,
                    error_type.value if error_type else None,
                    error_type.value if error_type else None,
                    now,
                    provider_key,
                ))

    def update_concurrency(self, provider_id: ProviderId | ProviderKey, new_concurrency: int) -> None:
        provider_key = self._provider_key(provider_id)
        with self._get_connection() as conn:
            conn.execute("""
            UPDATE providers
            SET current_concurrency = ?
            WHERE provider_id = ?
            """, (new_concurrency, provider_key))

    def acquire_slot(self, provider_id: ProviderId | ProviderKey) -> bool:
        provider_key = self._provider_key(provider_id)
        now = time.time()
        with self._get_connection() as conn:
            row = conn.execute("SELECT health_status, current_concurrency, active_requests, cooldown_until FROM providers WHERE provider_id = ?", (provider_key,)).fetchone()
            if not row:
                return False

            health = row["health_status"]
            cooldown_until = row["cooldown_until"]

            if health == ProviderHealth.COOLDOWN.value:
                if cooldown_until and now >= cooldown_until:
                    conn.execute("""
                    UPDATE providers
                    SET health_status = 'HEALTHY',
                        cooldown_until = NULL,
                        current_concurrency = 1,
                        consecutive_healthy_since = ?
                    WHERE provider_id = ?
                    """, (now, provider_key))
                    health = ProviderHealth.HEALTHY.value
                else:
                    return False

            if health not in (ProviderHealth.HEALTHY.value, ProviderHealth.THROTTLED.value):
                return False

            limit = row["current_concurrency"]
            active = row["active_requests"]
            if active < limit:
                conn.execute("UPDATE providers SET active_requests = active_requests + 1 WHERE provider_id = ?", (provider_key,))
                return True
            return False

    def release_slot(self, provider_id: ProviderId | ProviderKey) -> None:
        provider_key = self._provider_key(provider_id)
        with self._get_connection() as conn:
            conn.execute("""
            UPDATE providers
            SET active_requests = MAX(0, active_requests - 1)
            WHERE provider_id = ?
            """, (provider_key,))

    def record_usage(self, provider_id: ProviderId | ProviderKey, prompt_tokens: int, completion_tokens: int) -> None:
        provider_key = self._provider_key(provider_id)
        now = time.time()
        min_window = (now // 60) * 60
        day_window = (now // 86400) * 86400
        total_tokens = prompt_tokens + completion_tokens

        with self._get_connection() as conn:
            conn.execute("""
            UPDATE providers
            SET total_requests_today = total_requests_today + 1,
                total_tokens_today = total_tokens_today + ?
            WHERE provider_id = ?
            """, (total_tokens, provider_key))

            conn.execute("""
            INSERT INTO provider_windows (provider_id, window_type, window_start, request_count, token_count)
            VALUES (?, 'minute', ?, 1, ?)
            ON CONFLICT(provider_id, window_type, window_start) DO UPDATE SET
                request_count = request_count + 1,
                token_count = token_count + ?
            """, (provider_key, min_window, total_tokens, total_tokens))

            conn.execute("""
            INSERT INTO provider_windows (provider_id, window_type, window_start, request_count, token_count)
            VALUES (?, 'day', ?, 1, ?)
            ON CONFLICT(provider_id, window_type, window_start) DO UPDATE SET
                request_count = request_count + 1,
                token_count = token_count + ?
            """, (provider_key, day_window, total_tokens, total_tokens))

    def get_window_usage(self, provider_id: ProviderId | ProviderKey) -> Tuple[int, int, int, int]:
        provider_key = self._provider_key(provider_id)
        now = time.time()
        min_window = (now // 60) * 60
        day_window = (now // 86400) * 86400

        with self._get_connection() as conn:
            m_row = conn.execute("""
            SELECT request_count, token_count FROM provider_windows
            WHERE provider_id = ? AND window_type = 'minute' AND window_start = ?
            """, (provider_key, min_window)).fetchone()

            d_row = conn.execute("""
            SELECT request_count, token_count FROM provider_windows
            WHERE provider_id = ? AND window_type = 'day' AND window_start = ?
            """, (provider_key, day_window)).fetchone()

            rpm = m_row["request_count"] if m_row else 0
            tpm = m_row["token_count"] if m_row else 0
            rpd = d_row["request_count"] if d_row else 0
            tpd = d_row["token_count"] if d_row else 0
            return (rpm, tpm, rpd, tpd)

    def log_observation(
        self,
        task_class: str,
        logical_model: Optional[str],
        model_id: str,
        provider_id: ProviderId | ProviderKey,
        family: ModelFamily,
        latency_ms: float,
        prompt_tokens: int,
        completion_tokens: int,
        success: bool,
        normalized_error: Optional[str] = None,
    ) -> None:
        provider_key = self._provider_key(provider_id)
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO routing_observations (
                timestamp, task_class, logical_model, model_id, provider_id, family,
                latency_ms, prompt_tokens, completion_tokens, success, normalized_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                time.time(),
                task_class,
                logical_model,
                model_id,
                provider_key,
                family.value,
                latency_ms,
                prompt_tokens,
                completion_tokens,
                1 if success else 0,
                normalized_error,
            ))

    def get_recent_metrics(self, provider_id: ProviderId | ProviderKey, window_seconds: float = 300.0) -> Dict[str, Any]:
        provider_key = self._provider_key(provider_id)
        cutoff = time.time() - window_seconds
        with self._get_connection() as conn:
            rows = conn.execute("""
            SELECT success, normalized_error, latency_ms
            FROM routing_observations
            WHERE provider_id = ? AND timestamp >= ?
            """, (provider_key, cutoff)).fetchall()

            total = len(rows)
            if total == 0:
                return {
                    "total": 0,
                    "error_rate": 0.0,
                    "recent_429_rate": 0.0,
                    "avg_latency_ms": 0.0,
                    "p95_latency_ms": 0.0,
                }

            errors = sum(1 for r in rows if r["success"] == 0)
            rate_limits = sum(1 for r in rows if r["normalized_error"] == NormalizedErrorType.RATE_LIMITED.value)
            latencies = sorted(r["latency_ms"] for r in rows)
            p95_idx = int(total * 0.95)
            p95 = latencies[min(p95_idx, total - 1)]

            return {
                "total": total,
                "error_rate": errors / total,
                "recent_429_rate": rate_limits / total,
                "avg_latency_ms": sum(latencies) / total,
                "p95_latency_ms": p95,
            }
