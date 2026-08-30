"""
PAEOS Model Router — Real-Time Observability & Diagnostic Engine
Zero-Secret Leakage Guarantee
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional

from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.state import RouterStateDB
from paeos.model_router.types import ProviderId

# Canonical Free Tier Quota Limits (RPD: Requests Per Day)
FREE_TIER_DAILY_LIMITS: Dict[ProviderId, Optional[int]] = {
    ProviderId.GOOGLE: 1500,       # Google AI Studio Free Tier: 1500 RPD
    ProviderId.CLINE: None,        # Cline API zero-cost routes (e.g. minimax-m2.5): Unmetered / non-negative balance
    ProviderId.NVIDIA: 1000,       # NVIDIA NIM developer tier: ~1000 RPD
    ProviderId.KILO: 500,          # Kilo Auto Free tier ceiling: 500 RPD
    ProviderId.OPENROUTER: 200,    # OpenRouter Free tier ceiling: 200 RPD
}


def time_to_next_utc_midnight() -> tuple[int, str]:
    """Calculates remaining seconds and human-formatted time until 00:00:00 UTC daily quota reset."""
    now_utc = datetime.now(timezone.utc)
    # Target next 00:00:00 UTC
    seconds_since_midnight = now_utc.hour * 3600 + now_utc.minute * 60 + now_utc.second
    seconds_remaining = 86400 - seconds_since_midnight
    hours = seconds_remaining // 3600
    minutes = (seconds_remaining % 3600) // 60
    return seconds_remaining, f"{hours}h {minutes:02d}m"


class ObservabilityDiagnostics:
    def __init__(
        self,
        state_db: RouterStateDB,
        catalog: ModelCatalog,
        credentials: CredentialStore,
    ):
        self.state_db = state_db
        self.catalog = catalog
        self.credentials = credentials

    def get_mesh_status(self) -> Dict[str, Any]:
        """Produces comprehensive structured telemetry dictionary with quota tracking & reset times."""
        now = time.time()
        seconds_to_reset, reset_countdown = time_to_next_utc_midnight()
        providers_status = {}

        for p in ProviderId:
            st = self.state_db.get_provider_state(p)
            rpm, tpm, rpd, tpd = self.state_db.get_window_usage(p)
            metrics = self.state_db.get_recent_metrics(p, window_seconds=300.0)
            has_key = self.credentials.has_key(p)
            models = [m.model_id for m in self.catalog.list_models(p)]
            live_models = [m.model_id for m in self.catalog.list_models(p) if m.live_verified and m.available]

            cooldown_rem = 0.0
            if st["cooldown_until"] and st["cooldown_until"] > now:
                cooldown_rem = st["cooldown_until"] - now

            try:
                quota_limit = self.catalog.provider_registry.resolve(p).max_rpd
            except KeyError:
                quota_limit = FREE_TIER_DAILY_LIMITS.get(p)
            if quota_limit is not None and quota_limit > 0:
                quota_pct = round((rpd / quota_limit) * 100.0, 1)
            else:
                quota_pct = 0.0  # Unmetered / zero-cost model

            providers_status[p.value] = {
                "credential_configured": has_key,
                "health_status": st["health_status"] if has_key else "UNCONFIGURED",
                "current_concurrency": st["current_concurrency"],
                "active_requests": st["active_requests"],
                "cooldown_remaining_seconds": round(cooldown_rem, 1),
                "last_error": st["last_error_type"],
                "rpm": rpm,
                "tpm": tpm,
                "rpd": rpd,
                "daily_limit_rpd": quota_limit,
                "quota_used_pct": quota_pct,
                "recent_429_rate_pct": round(metrics["recent_429_rate"] * 100, 1),
                "avg_latency_ms": round(metrics["avg_latency_ms"], 1),
                "registered_models": models,
                "live_verified_models": live_models,
            }

        return {
            "timestamp": now,
            "quota_reset_in_seconds": seconds_to_reset,
            "quota_reset_countdown": reset_countdown,
            "providers": providers_status,
        }

    def format_markdown_table(self) -> str:
        """Renders diagnostic table for Antigravity oversight."""
        status = self.get_mesh_status()
        reset_time = status["quota_reset_countdown"]
        lines = [
            f"**Daily Quota Reset In:** `{reset_time}` (at `00:00:00 UTC`)\n",
            "| Provider | Credential | Health | Concurrency | Today (RPD) | % Quota Used | Live Models | Last Error |",
            "|---|:---:|:---:|:---:|:---:|:---:|---|---|",
        ]

        for p_name, p_data in status["providers"].items():
            cred = "✅" if p_data["credential_configured"] else "❌"
            health = p_data["health_status"]
            if health == "HEALTHY":
                health_fmt = "🟢 HEALTHY"
            elif health in ("THROTTLED", "COOLDOWN"):
                health_fmt = f"🟡 {health} ({p_data['cooldown_remaining_seconds']}s)"
            elif health == "EXHAUSTED":
                health_fmt = "🔴 EXHAUSTED"
            else:
                health_fmt = f"⚪ {health}"

            conc = f"{p_data['active_requests']}/{p_data['current_concurrency']}"
            live = ", ".join(p_data["live_verified_models"]) if p_data["live_verified_models"] else "None"
            err = p_data["last_error"] or "None"

            limit = p_data["daily_limit_rpd"]
            rpd_str = f"{p_data['rpd']} / {limit}" if limit else f"{p_data['rpd']} (free)"
            pct_str = f"{p_data['quota_used_pct']}%" if limit else "0.0% (unmetered)"

            lines.append(
                f"| **{p_name.upper()}** | {cred} | {health_fmt} | {conc} | {rpd_str} | **{pct_str}** | `{live}` | {err} |"
            )

        return "\n".join(lines)

    def format_terminal_dashboard(self) -> str:
        """Renders a beautiful rich ANSI terminal dashboard for CLI monitoring."""
        status = self.get_mesh_status()
        reset_time = status["quota_reset_countdown"]
        border = "═" * 84
        div = "─" * 84
        out = [
            f"\n\033[1;36m╔{border}╗\033[0m",
            f"\033[1;36m║\033[0m \033[1;37mPAEOS INFERENCE MESH — REAL-TIME QUOTA & HEALTH MONITOR\033[0m               \033[1;36m║\033[0m",
            f"\033[1;36m║\033[0m \033[2mDaily Free Tier Reset: \033[1;33m{reset_time}\033[0m\033[2m until 00:00 UTC\033[0m                                 \033[1;36m║\033[0m",
            f"\033[1;36m╠{border}╣\033[0m",
            f"\033[1;36m║\033[0m \033[1;37m{'PROVIDER':<12} {'HEALTH':<12} {'RPD / LIMIT':<14} {'% USED':<12} {'CONC':<8} {'LIVE MODELS':<21}\033[0m\033[1;36m║\033[0m",
            f"\033[1;36m╟{div}╢\033[0m",
        ]

        for p_name, p_data in status["providers"].items():
            health = p_data["health_status"]
            if health == "HEALTHY":
                h_str = "\033[1;32m● HEALTHY\033[0m"
            elif health in ("THROTTLED", "COOLDOWN"):
                h_str = f"\033[1;33m▲ {health}\033[0m"
            elif health == "EXHAUSTED":
                h_str = "\033[1;31m✖ EXHAUST\033[0m"
            else:
                h_str = f"\033[2m{health}\033[0m"

            limit = p_data["daily_limit_rpd"]
            rpd_str = f"{p_data['rpd']} / {limit}" if limit else f"{p_data['rpd']} (free)"
            pct = p_data["quota_used_pct"]
            if pct > 80.0:
                pct_str = f"\033[1;31m{pct:5.1f}%\033[0m"
            elif pct > 50.0:
                pct_str = f"\033[1;33m{pct:5.1f}%\033[0m"
            else:
                pct_str = f"\033[1;32m{pct:5.1f}%\033[0m" if limit else "\033[2m0.0%\033[0m"

            conc_str = f"{p_data['active_requests']}/{p_data['current_concurrency']}"
            models = ", ".join(p_data["live_verified_models"]) if p_data["live_verified_models"] else "none"
            if len(models) > 20:
                models = models[:18] + ".."

            out.append(
                f"\033[1;36m║\033[0m {p_name.upper():<12} {h_str:<21} {rpd_str:<14} {pct_str:<21} {conc_str:<8} {models:<21}\033[1;36m║\033[0m"
            )

        out.append(f"\033[1;36m╚{border}╝\033[0m\n")
        return "\n".join(out)
