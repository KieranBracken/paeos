"""Signed readiness gate for the fixed GPT-5.6 Luna planner transport.

This gate is intentionally separate from ``BuilderTransportReadiness``.  Luna may qualify only
for the planner stages physically listed in a supervisor-signed record; it can never qualify L12
IMPLEMENT or replace the Sol Builder qualification.
"""

from __future__ import annotations

import json
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

from kernel.types import Role, StageId
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from runtime.builder_transport import REQUIRED_CANARIES, REQUIRED_LIFECYCLE
from runtime.task_package import TaskPackage

__all__ = [
    "L10_FAMILY_AMENDMENT_ID",
    "L10_FAMILY_AMENDMENT_NORMATIVE",
    "PLANNER_STAGES",
    "LunaAdversaryBinding",
    "LunaAdversaryBindingNotReady",
    "LunaCriticBinding",
    "LunaCriticBindingNotReady",
    "PlannerTransportNotReady",
    "PlannerTransportQualification",
    "PlannerTransportReadiness",
    "canonical_planner_qualification_bytes",
    "contract_markers_for",
    "l10_amendment_definition_hash",
]

SCHEMA = "paeos-planner-transport-qualification/2"
PLANNER_STAGES = (
    "RE_DERIVE",
    "IDEATE",
    "RESEARCH",
    "TRADEOFF",
    "MITIGATION",
    "DESIGN",
    "CRITIQUE",
    "ADVERSARIAL_REVIEW",
    "PLAN",
)
_PLANNER_STAGE_SET = frozenset(PLANNER_STAGES)
PLANNER_CONTRACT_MARKERS = {
    "RE_DERIVE": ("requirements", "assumptions"),
    "IDEATE": ("options", "alternatives"),
    "RESEARCH": ("evidence", "uncertainties"),
    "TRADEOFF": ("trade offs", "decision"),
    "MITIGATION": ("safeguards", "residual"),
    "DESIGN": ("components", "interfaces"),
    "CRITIQUE": ("critique", "defects"),
    "ADVERSARIAL_REVIEW": ("attack", "failure"),
    "PLAN": ("work units", "rollback"),
}
_COMMON_CONTRACT_MARKERS = ("requirements", "boundaries", "assumptions", "risks", "next action")
_HASH_FIELDS = frozenset(
    {"request_sha256", "response_sha256", "artifact_sha256", "evidence_sha256"}
)
_BINDING_FIELDS = frozenset({*_HASH_FIELDS, "contract_markers"})
_PAYLOAD_FIELDS = frozenset(
    {
        "schema",
        "qualification_scope",
        "qualification_id",
        "supervisor_identity_sha256",
        "provider",
        "model",
        "family",
        "observed_at",
        "expires_at",
        "lifecycle",
        "canaries",
        "qualified_stages",
        "probe_bindings",
        "fallback_used",
        "manual_chat_bridge",
    }
)

L10_FAMILY_AMENDMENT_ID = "P1-L10-FAMILY-DECORRELATION-AMENDMENT-20260918"
L10_FAMILY_AMENDMENT_NORMATIVE = {
    "amendment_id": L10_FAMILY_AMENDMENT_ID,
    "scope": "P1-only-L10-adversarial-review",
    "prior_rule": "L10 adversary family != L12 Builder family",
    "replacement_rule": {
        "family_match_permitted": True,
        "fresh_sealed_context_required": True,
        "builder_context_inheritance": False,
        "builder_write_authority": False,
        "self_certification": False,
        "exact_identity_required": True,
        "independent_provenance_required": True,
        "fallback_permitted": False,
    },
    "preserved": {
        "l14_builder_auditor_family_inequality": True,
        "court_negative_discrimination": True,
        "p1_output_contract": True,
        "sentium_frozen": True,
    },
}


def l10_amendment_definition_hash() -> str:
    import hashlib

    payload = json.dumps(
        L10_FAMILY_AMENDMENT_NORMATIVE,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


class PlannerTransportNotReady(RuntimeError):
    """The signed Luna planner qualification is absent, stale, forged, or incomplete."""


class LunaCriticBindingNotReady(PlannerTransportNotReady):
    """The qualified Luna worker does not subsume a requested critic task."""


class LunaAdversaryBindingNotReady(PlannerTransportNotReady):
    """The qualified Luna worker does not subsume the amended P1 L10 task."""


@dataclass(frozen=True, slots=True)
class PlannerTransportQualification:
    qualification_scope: str
    qualification_id: str
    supervisor_identity_sha256: str
    provider: str
    model: str
    family: str
    observed_at: int
    expires_at: int
    lifecycle: tuple[str, ...]
    canaries: tuple[str, ...]
    qualified_stages: tuple[str, ...]
    probe_bindings: dict[str, dict[str, object]]
    fallback_used: bool
    manual_chat_bridge: bool


@dataclass(frozen=True, slots=True)
class _LunaWorkerSecurityEnvelope:
    """Transport facts proven by the qualification, independent of any task role."""

    qualification_id: str
    supervisor_identity_sha256: str
    provider: str
    model: str
    family: str
    physical_critique_binding: Mapping[str, str]
    fallback_used: bool
    manual_chat_bridge: bool


@dataclass(frozen=True, slots=True, init=False)
class LunaAdversaryBinding:
    """Task-scoped GPT/Luna use for amended P1 L10 adversarial review.

    This binding does not change the global A-08 auditor rule. It reuses the supervisor-signed
    Luna transport facts only after a fresh ADVERSARIAL_REVIEW probe is present, and it binds the
    role, stage, context, write scope, and capability to one task.
    """

    _envelope: _LunaWorkerSecurityEnvelope
    capability_class: str = "TRUSTED_LUNA_READONLY_ADVERSARY"
    production_write: bool = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise LunaAdversaryBindingNotReady(
            "Luna adversary bindings may be constructed only from verified readiness"
        )

    @classmethod
    def from_readiness(cls, readiness: PlannerTransportReadiness) -> LunaAdversaryBinding:
        if not isinstance(readiness, PlannerTransportReadiness):
            raise LunaAdversaryBindingNotReady("adversary binding requires planner readiness")
        try:
            qualification = readiness.require("ADVERSARIAL_REVIEW")
        except PlannerTransportNotReady as exc:
            raise LunaAdversaryBindingNotReady(
                "Luna ADVERSARIAL_REVIEW transport qualification is not ready"
            ) from exc
        binding = qualification.probe_bindings.get("ADVERSARIAL_REVIEW")
        if not isinstance(binding, dict) or not all(field in binding for field in _HASH_FIELDS):
            raise LunaAdversaryBindingNotReady(
                "physical ADVERSARIAL_REVIEW probe binding is absent"
            )
        if (
            qualification.provider != "codex"
            or qualification.model != "gpt-5.6-luna"
            or qualification.family != "gpt"
            or qualification.fallback_used is not False
            or qualification.manual_chat_bridge is not False
        ):
            raise LunaAdversaryBindingNotReady("Luna adversary security envelope is invalid")
        physical = MappingProxyType({field: str(binding[field]) for field in sorted(_HASH_FIELDS)})
        envelope = _LunaWorkerSecurityEnvelope(
            qualification_id=qualification.qualification_id,
            supervisor_identity_sha256=qualification.supervisor_identity_sha256,
            provider=qualification.provider,
            model=qualification.model,
            family=qualification.family,
            physical_critique_binding=physical,
            fallback_used=False,
            manual_chat_bridge=False,
        )
        instance = object.__new__(cls)
        object.__setattr__(instance, "_envelope", envelope)
        object.__setattr__(instance, "capability_class", "TRUSTED_LUNA_READONLY_ADVERSARY")
        object.__setattr__(instance, "production_write", False)
        return instance

    @staticmethod
    def _scoped(values: object, *, prefix: str, description: str) -> None:
        if not isinstance(values, tuple) or len(values) != len(set(values)):
            raise LunaAdversaryBindingNotReady(f"adversary task {description} are malformed")
        if any(not isinstance(value, str) or not value.startswith(prefix) for value in values):
            raise LunaAdversaryBindingNotReady(
                f"adversary task {description} exceed the role contract"
            )

    def authorize_task(self, package: TaskPackage) -> dict[str, object]:
        if not isinstance(package, TaskPackage):
            raise LunaAdversaryBindingNotReady("adversary authorization requires a task package")
        if package.role is not Role.ADVERSARY or package.stage is not StageId.ADVERSARIAL_REVIEW:
            raise LunaAdversaryBindingNotReady("Luna adversary binding is role and stage scoped")
        if not package.context_refs or len({ref.hash for ref in package.context_refs}) != len(
            package.context_refs
        ):
            raise LunaAdversaryBindingNotReady(
                "fresh sealed adversary context is missing or duplicated"
            )
        self._scoped(package.permissions.read_scopes, prefix="", description="read scopes")
        allowed_reads = frozenset({"context/", "constitution/", "design/", "plan/", "review/"})
        if not set(package.permissions.read_scopes).issubset(allowed_reads):
            raise LunaAdversaryBindingNotReady(
                "adversary read authority exceeds the amended contract"
            )
        self._scoped(package.permissions.write_scopes, prefix="review/", description="write scopes")
        allowed_ops = frozenset(
            {
                "mcp:constitution",
                "mcp:artifacts",
                "mcp:court",
                "mcp:memory:read",
            }
        )
        operations = getattr(package.capability, "operations", None)
        if not isinstance(operations, (tuple, frozenset)) or not set(operations).issubset(
            allowed_ops
        ):
            raise LunaAdversaryBindingNotReady(
                "adversary capability operations exceed the amended contract"
            )
        bound_to = getattr(package.capability, "bound_to", None)
        if (
            getattr(bound_to, "goal_id", None) != package.goal_id
            or getattr(bound_to, "run_id", None) != package.run_id
            or getattr(bound_to, "stage", None) is not StageId.ADVERSARIAL_REVIEW
            or getattr(bound_to, "role", None) is not Role.ADVERSARY
        ):
            raise LunaAdversaryBindingNotReady("adversary capability identity is not task-bound")
        envelope = self._envelope
        return {
            "capability_class": self.capability_class,
            "role": Role.ADVERSARY.value,
            "stage": StageId.ADVERSARIAL_REVIEW.value,
            "qualification_id": envelope.qualification_id,
            "supervisor_identity_sha256": envelope.supervisor_identity_sha256,
            "provider": envelope.provider,
            "model": envelope.model,
            "family": envelope.family,
            "physical_binding": dict(envelope.physical_critique_binding),
            "fresh_context_required": True,
            "builder_context_inherited": False,
            "production_write": False,
            "fallback_used": envelope.fallback_used,
            "manual_chat_bridge": envelope.manual_chat_bridge,
        }


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
        + "\n"
    ).encode("ascii")


def canonical_planner_qualification_bytes(payload: Mapping[str, object]) -> bytes:
    if set(payload) != _PAYLOAD_FIELDS:
        raise PlannerTransportNotReady("planner qualification payload fields are not exact")
    return _canonical(dict(payload))


def _strict_json(raw: bytes) -> dict[str, object]:
    def pairs(items: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in items:
            if key in result:
                raise PlannerTransportNotReady("planner qualification has duplicate JSON fields")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlannerTransportNotReady("planner qualification is not strict UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise PlannerTransportNotReady("planner qualification root is not an object")
    return value


def _hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and value == value.casefold()
        and all(character in "0123456789abcdef" for character in value)
    )


def contract_markers_for(stage: str, transcript: str) -> dict[str, bool]:
    """Derive required stage markers from the captured response, never from caller claims."""

    normalized = "".join(
        character if character.isalnum() else " " for character in transcript.casefold()
    )
    expected = (*_COMMON_CONTRACT_MARKERS, *PLANNER_CONTRACT_MARKERS[stage])
    return {marker: marker in normalized for marker in expected}


class PlannerTransportReadiness:
    """Verify one supervisor-signed, stage-scoped physical Luna qualification."""

    def __init__(
        self,
        qualification_path: Path,
        verify_key: VerifyKey,
        *,
        clock: Callable[[], int] | None = None,
        max_age_s: int = 86_400,
    ) -> None:
        self._path = qualification_path
        self._verify_key = verify_key
        self._clock = clock or (lambda: int(time.time()))
        self._max_age_s = max_age_s

    def require(self, stage: str | None = None) -> PlannerTransportQualification:
        path = self._path
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise PlannerTransportNotReady("planner qualification file is unavailable")
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & 0o077:
                raise PlannerTransportNotReady("planner qualification permissions are too broad")
            document = _strict_json(path.read_bytes())
        except OSError as exc:
            raise PlannerTransportNotReady("planner qualification file cannot be read") from exc
        if set(document) != {"payload", "signature"} or not isinstance(
            document.get("payload"), dict
        ):
            raise PlannerTransportNotReady("planner qualification envelope is not exact")
        payload = document["payload"]
        assert isinstance(payload, dict)
        signature = document.get("signature")
        if not isinstance(signature, str) or len(signature) != 128:
            raise PlannerTransportNotReady("planner qualification signature is malformed")
        try:
            self._verify_key.verify(
                canonical_planner_qualification_bytes(payload), bytes.fromhex(signature)
            )
        except (BadSignatureError, ValueError) as exc:
            raise PlannerTransportNotReady("planner qualification signature is invalid") from exc
        qualification = self._validate_payload(payload)
        now = self._clock()
        if qualification.observed_at > now + 5:
            raise PlannerTransportNotReady("planner qualification timestamp is in the future")
        if (
            qualification.expires_at <= now
            or qualification.expires_at - qualification.observed_at > self._max_age_s
        ):
            raise PlannerTransportNotReady("planner qualification is expired or stale")
        if now - qualification.observed_at > self._max_age_s:
            raise PlannerTransportNotReady("planner qualification is stale")
        if stage is not None:
            if stage not in _PLANNER_STAGE_SET:
                raise PlannerTransportNotReady("requested stage is not a planner stage")
            if stage not in qualification.qualified_stages:
                raise PlannerTransportNotReady("requested planner stage is not qualified")
        return qualification

    @staticmethod
    def _validate_payload(payload: Mapping[str, object]) -> PlannerTransportQualification:
        if set(payload) != _PAYLOAD_FIELDS:
            raise PlannerTransportNotReady("planner qualification payload fields are not exact")
        if (
            payload.get("schema") != SCHEMA
            or payload.get("qualification_scope") != "standalone-planner-probe"
        ):
            raise PlannerTransportNotReady("planner qualification scope is invalid")
        if (
            payload.get("provider") != "codex"
            or payload.get("model") != "gpt-5.6-luna"
            or payload.get("family") != "gpt"
        ):
            raise PlannerTransportNotReady("planner qualification is not for Luna")
        if (
            payload.get("fallback_used") is not False
            or payload.get("manual_chat_bridge") is not False
        ):
            raise PlannerTransportNotReady("planner qualification used an unauthorized fallback")
        for field in ("qualification_id", "supervisor_identity_sha256"):
            if not isinstance(payload.get(field), str) or not payload[field]:
                raise PlannerTransportNotReady("planner qualification identity is malformed")
        for field in ("supervisor_identity_sha256",):
            if not _hash(payload[field]):
                raise PlannerTransportNotReady("planner qualification identity hash is invalid")
        observed_at = payload.get("observed_at")
        expires_at = payload.get("expires_at")
        if (
            isinstance(observed_at, bool)
            or isinstance(expires_at, bool)
            or not isinstance(observed_at, int)
            or not isinstance(expires_at, int)
            or expires_at <= observed_at
        ):
            raise PlannerTransportNotReady("planner qualification time bounds are invalid")
        if payload.get("lifecycle") != list(REQUIRED_LIFECYCLE):
            raise PlannerTransportNotReady("planner qualification lifecycle is incomplete")
        canaries = payload.get("canaries")
        if not isinstance(canaries, list) or sorted(canaries) != sorted(REQUIRED_CANARIES):
            raise PlannerTransportNotReady("planner qualification canaries are incomplete")
        stages = payload.get("qualified_stages")
        if (
            not isinstance(stages, list)
            or not stages
            or any(
                not isinstance(stage, str) or stage not in _PLANNER_STAGE_SET for stage in stages
            )
            or stages != sorted(set(stages))
        ):
            raise PlannerTransportNotReady("planner qualified stage set is invalid")
        bindings = payload.get("probe_bindings")
        if not isinstance(bindings, dict) or set(bindings) != set(stages):
            raise PlannerTransportNotReady("planner probe bindings are incomplete")
        normalized: dict[str, dict[str, object]] = {}
        for stage in stages:
            binding = bindings.get(stage)
            if not isinstance(binding, dict) or set(binding) != _BINDING_FIELDS:
                raise PlannerTransportNotReady("planner probe binding fields are not exact")
            if not all(_hash(binding[field]) for field in _HASH_FIELDS):
                raise PlannerTransportNotReady("planner probe binding hash is invalid")
            markers = binding.get("contract_markers")
            expected_markers = (*_COMMON_CONTRACT_MARKERS, *PLANNER_CONTRACT_MARKERS[stage])
            if (
                not isinstance(markers, dict)
                or set(markers) != set(expected_markers)
                or any(markers[marker] is not True for marker in expected_markers)
            ):
                raise PlannerTransportNotReady("planner stage contract markers are incomplete")
            normalized[stage] = {
                **{field: binding[field] for field in _HASH_FIELDS},
                "contract_markers": {marker: True for marker in expected_markers},
            }
        return PlannerTransportQualification(
            qualification_scope=str(payload["qualification_scope"]),
            qualification_id=str(payload["qualification_id"]),
            supervisor_identity_sha256=str(payload["supervisor_identity_sha256"]),
            provider=str(payload["provider"]),
            model=str(payload["model"]),
            family=str(payload["family"]),
            observed_at=observed_at,
            expires_at=expires_at,
            lifecycle=tuple(payload["lifecycle"]),
            canaries=tuple(canaries),
            qualified_stages=tuple(stages),
            probe_bindings=normalized,
            fallback_used=False,
            manual_chat_bridge=False,
        )


@dataclass(frozen=True, slots=True, init=False)
class LunaCriticBinding:
    """A task-scoped CRITIQUE use of a physically qualified Luna worker.

    This is deliberately not a routing or provider assignment.  The envelope records only
    supervisor-proven worker facts; ``authorize_task`` separately checks whether one task's
    authority is wholly contained by the read-only critic contract.
    """

    _envelope: _LunaWorkerSecurityEnvelope
    capability_class: str = "TRUSTED_LUNA_READONLY_PLANNER"
    production_write: bool = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        raise LunaCriticBindingNotReady(
            "Luna critic bindings may be constructed only from verified readiness"
        )

    @classmethod
    def from_readiness(cls, readiness: PlannerTransportReadiness) -> LunaCriticBinding:
        if not isinstance(readiness, PlannerTransportReadiness):
            raise LunaCriticBindingNotReady("critic binding requires planner transport readiness")
        try:
            qualification = readiness.require("CRITIQUE")
        except PlannerTransportNotReady as exc:
            raise LunaCriticBindingNotReady(
                "Luna CRITIQUE transport qualification is not ready"
            ) from exc

        binding = qualification.probe_bindings.get("CRITIQUE")
        if not isinstance(binding, dict) or not all(field in binding for field in _HASH_FIELDS):
            raise LunaCriticBindingNotReady("physical CRITIQUE probe binding is absent")
        if (
            qualification.provider != "codex"
            or qualification.model != "gpt-5.6-luna"
            or qualification.family != "gpt"
            or qualification.fallback_used is not False
            or qualification.manual_chat_bridge is not False
        ):
            raise LunaCriticBindingNotReady("Luna worker security envelope is invalid")

        physical = MappingProxyType({field: str(binding[field]) for field in sorted(_HASH_FIELDS)})
        envelope = _LunaWorkerSecurityEnvelope(
            qualification_id=qualification.qualification_id,
            supervisor_identity_sha256=qualification.supervisor_identity_sha256,
            provider=qualification.provider,
            model=qualification.model,
            family=qualification.family,
            physical_critique_binding=physical,
            fallback_used=False,
            manual_chat_bridge=False,
        )
        instance = object.__new__(cls)
        object.__setattr__(instance, "_envelope", envelope)
        object.__setattr__(instance, "capability_class", "TRUSTED_LUNA_READONLY_PLANNER")
        object.__setattr__(instance, "production_write", False)
        return instance

    @staticmethod
    def _bounded(values: object, allowed: frozenset[str], description: str) -> None:
        if (
            not isinstance(values, tuple)
            or any(not isinstance(value, str) for value in values)
            or len(values) != len(set(values))
            or not set(values).issubset(allowed)
        ):
            raise LunaCriticBindingNotReady(f"critic task {description} exceed the role contract")

    def authorize_task(self, package: TaskPackage) -> dict[str, object]:
        """Return signed-source transport facts iff the package is strictly subsumed."""

        if not isinstance(package, TaskPackage):
            raise LunaCriticBindingNotReady("critic authorization requires a task package")
        if package.role is not Role.CRITIC or package.stage is not StageId.CRITIQUE:
            raise LunaCriticBindingNotReady("Luna critic binding is role and stage scoped")

        self._bounded(
            package.permissions.read_scopes,
            frozenset({"constitution/", "design/", "plan/"}),
            "read scopes",
        )
        self._bounded(
            package.permissions.write_scopes,
            frozenset({"critique/"}),
            "write scopes",
        )
        self._bounded(
            package.permissions.mcp_servers,
            frozenset({"constitution", "artifacts", "memory:read"}),
            "MCP grants",
        )

        capability = package.capability
        bound_to = getattr(capability, "bound_to", None)
        if (
            getattr(bound_to, "goal_id", None) != package.goal_id
            or getattr(bound_to, "run_id", None) != package.run_id
            or getattr(bound_to, "stage", None) is not StageId.CRITIQUE
            or getattr(bound_to, "role", None) is not Role.CRITIC
        ):
            raise LunaCriticBindingNotReady("critic capability identity is not task-bound")
        operations = getattr(capability, "operations", None)
        if not isinstance(operations, (tuple, frozenset)) or not set(operations).issubset(
            {"mcp:constitution", "mcp:artifacts", "mcp:memory:read"}
        ):
            raise LunaCriticBindingNotReady("critic capability operations exceed the MCP contract")

        envelope = self._envelope
        return {
            "capability_class": self.capability_class,
            "role": Role.CRITIC.value,
            "stage": StageId.CRITIQUE.value,
            "qualification_id": envelope.qualification_id,
            "supervisor_identity_sha256": envelope.supervisor_identity_sha256,
            "provider": envelope.provider,
            "model": envelope.model,
            "family": envelope.family,
            "physical_binding": dict(envelope.physical_critique_binding),
            "production_write": False,
            "fallback_used": envelope.fallback_used,
            "manual_chat_bridge": envelope.manual_chat_bridge,
        }
