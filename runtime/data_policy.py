"""Data policy, context provenance tagging, and egress manifest compilation (Gate E)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from kernel.types import ArtifactRef
from paeos.model_router.types import DataClass


class EgressPolicyViolationError(ValueError):
    """Raised when an egress manifest violates privacy or data class policy."""


@dataclass(frozen=True, slots=True)
class ContextEntry:
    ref: ArtifactRef
    source: str
    source_hash: str
    data_class: DataClass
    trust: str
    purpose: str


@dataclass(frozen=True, slots=True)
class PrivacyPolicySnapshot:
    provider: str
    policy_version: str
    policy_hash: str
    observed_at: str
    expires_at: str
    allows_internal: bool
    allows_confidential: bool
    trains_on_inputs: bool
    retains_prompts: bool


@dataclass(frozen=True, slots=True)
class EgressManifest:
    provider: str
    policy_hash: str
    entries: tuple[tuple[str, int, str], ...]  # (content_hash, byte_length, data_class)
    total_bytes: int


def compile_egress_manifest(
    entries: Sequence[ContextEntry], policy: PrivacyPolicySnapshot
) -> EgressManifest:
    manifest_entries: list[tuple[str, int, str]] = []
    total_bytes = 0

    for entry in entries:
        if entry.data_class == DataClass.SECRET:
            raise EgressPolicyViolationError(
                f"DataClass.SECRET forbidden from leaving local host (entry {entry.ref.type})"
            )
        if entry.data_class == DataClass.CONFIDENTIAL and not policy.allows_confidential:
            raise EgressPolicyViolationError(
                f"Provider {policy.provider} does not allow CONFIDENTIAL data "
                f"(entry {entry.ref.type})"
            )
        if entry.data_class == DataClass.INTERNAL and not policy.allows_internal:
            raise EgressPolicyViolationError(
                f"Provider {policy.provider} does not allow INTERNAL data (entry {entry.ref.type})"
            )

        # Approximate content byte length or use hash length
        byte_len = len(entry.source_hash.encode("utf-8"))
        manifest_entries.append((entry.source_hash, byte_len, entry.data_class.value))
        total_bytes += byte_len

    return EgressManifest(
        provider=policy.provider,
        policy_hash=policy.policy_hash,
        entries=tuple(manifest_entries),
        total_bytes=total_bytes,
    )
