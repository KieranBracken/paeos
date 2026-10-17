from __future__ import annotations

import pytest
from kernel.types import ArtifactRef
from paeos.model_router.types import DataClass


def test_egress_manifest_compilation_and_validation() -> None:
    from runtime.data_policy import (
        ContextEntry,
        EgressManifest,
        PrivacyPolicySnapshot,
        compile_egress_manifest,
    )

    policy = PrivacyPolicySnapshot(
        provider="google",
        policy_version="2026.1",
        policy_hash="p" * 64,
        observed_at="2026-08-30T00:00:00Z",
        expires_at="2026-09-30T00:00:00Z",
        allows_internal=True,
        allows_confidential=False,
        trains_on_inputs=False,
        retains_prompts=False,
    )

    entry1 = ContextEntry(
        ref=ArtifactRef("design", "1" * 64),
        source="repo",
        source_hash="1" * 64,
        data_class=DataClass.PUBLIC,
        trust="HIGH",
        purpose="architecture",
    )
    entry2 = ContextEntry(
        ref=ArtifactRef("plan", "2" * 64),
        source="repo",
        source_hash="2" * 64,
        data_class=DataClass.INTERNAL,
        trust="HIGH",
        purpose="plan",
    )

    manifest = compile_egress_manifest([entry1, entry2], policy)
    assert isinstance(manifest, EgressManifest)
    assert manifest.provider == "google"
    assert manifest.policy_hash == "p" * 64
    assert len(manifest.entries) == 2


def test_egress_manifest_rejects_secret_data() -> None:
    from runtime.data_policy import (
        ContextEntry,
        EgressPolicyViolationError,
        PrivacyPolicySnapshot,
        compile_egress_manifest,
    )

    policy = PrivacyPolicySnapshot(
        provider="google",
        policy_version="2026.1",
        policy_hash="p" * 64,
        observed_at="2026-08-30T00:00:00Z",
        expires_at="2026-09-30T00:00:00Z",
        allows_internal=True,
        allows_confidential=False,
        trains_on_inputs=False,
        retains_prompts=False,
    )

    secret_entry = ContextEntry(
        ref=ArtifactRef("credentials", "3" * 64),
        source="env",
        source_hash="3" * 64,
        data_class=DataClass.SECRET,
        trust="LOCAL_ONLY",
        purpose="auth",
    )

    with pytest.raises(EgressPolicyViolationError, match="SECRET"):
        compile_egress_manifest([secret_entry], policy)


def test_egress_manifest_rejects_confidential_when_disallowed() -> None:
    from runtime.data_policy import (
        ContextEntry,
        EgressPolicyViolationError,
        PrivacyPolicySnapshot,
        compile_egress_manifest,
    )

    policy = PrivacyPolicySnapshot(
        provider="openrouter",
        policy_version="2026.1",
        policy_hash="p" * 64,
        observed_at="2026-08-30T00:00:00Z",
        expires_at="2026-09-30T00:00:00Z",
        allows_internal=True,
        allows_confidential=False,
        trains_on_inputs=False,
        retains_prompts=False,
    )

    confidential_entry = ContextEntry(
        ref=ArtifactRef("proprietary", "4" * 64),
        source="customer",
        source_hash="4" * 64,
        data_class=DataClass.CONFIDENTIAL,
        trust="HIGH",
        purpose="domain",
    )


    with pytest.raises(EgressPolicyViolationError, match="CONFIDENTIAL"):
        compile_egress_manifest([confidential_entry], policy)
