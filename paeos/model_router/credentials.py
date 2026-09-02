"""
PAEOS Model Router — Secure Credential Loader & Sanitizer
Strict Zero-Secret Leakage Guarantee: Never leaks any character of any secret.
Canonical Precedence: ~/.config/paeos/model-router.env takes precedence over ambient process env.
"""
from __future__ import annotations

import contextlib
import os
from pathlib import Path

from paeos.model_router.providers import ProviderRegistry, build_builtin_provider_registry
from paeos.model_router.types import ProviderId

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "paeos" / "model-router.env"

PROVIDER_ENV_MAPPING = {
    ProviderId.GOOGLE: "GEMINI_API_KEY",
    ProviderId.CLINE: "CLINE_API_KEY",
    ProviderId.NVIDIA: "NVIDIA_API_KEY",
    ProviderId.KILO: "KILO_API_KEY",
    ProviderId.OPENROUTER: "OPENROUTER_API_KEY",
}


def mask_secret(secret: str | None) -> str:
    """Safely mask secret for logging/diagnostics without leaking ANY characters."""
    if not secret or len(secret.strip()) == 0:
        return "<UNSET>"
    return "<CONFIGURED>"


class CredentialStore:
    def __init__(
        self,
        env_file: Path | None = None,
        provider_registry: ProviderRegistry | None = None,
    ):
        self.env_file = env_file or DEFAULT_CONFIG_PATH
        self.provider_registry = provider_registry or build_builtin_provider_registry()
        self._keys: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        """
        Load credentials.
        Canonical precedence: ~/.config/paeos/model-router.env is primary,
        falling back to os.environ only if key is unconfigured in file.
        """
        self._keys = {}

        # 1. Load from ambient environment as fallback defaults
        for env_var in PROVIDER_ENV_MAPPING.values():
            val = os.environ.get(env_var)
            if val and val.strip():
                self._keys[env_var] = val.strip()

        # 2. Canonical file configuration overrides ambient environment
        if self.env_file.exists():
            try:
                mode = self.env_file.stat().st_mode
                if mode & 0o077 and os.name == "posix":
                    with contextlib.suppress(Exception):
                        os.chmod(self.env_file, 0o600)

                lines = self.env_file.read_text(encoding="utf-8").splitlines()
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                            v = v[1:-1]
                        if v:
                            self._keys[k] = v
            except Exception:
                pass

    def get_key(self, provider_id: ProviderId | str) -> str | None:
        try:
            env_var = self.provider_registry.resolve(provider_id).credential_env
        except (KeyError, ValueError):
            if isinstance(provider_id, ProviderId):
                env_var = PROVIDER_ENV_MAPPING.get(provider_id)
            else:
                env_var = None
        if env_var is None:
            return None
        return self._keys.get(env_var)

    def has_key(self, provider_id: ProviderId | str) -> bool:
        key = self.get_key(provider_id)
        return bool(key and len(key.strip()) > 0)

    def get_status_matrix(self) -> dict[str, bool]:
        return {
            p.value: self.has_key(p) for p in ProviderId
        }

    def __repr__(self) -> str:
        statuses = [f"{p.value}:{'CONFIGURED' if self.has_key(p) else 'UNSET'}" for p in ProviderId]
        return f"<CredentialStore {' '.join(statuses)}>"
