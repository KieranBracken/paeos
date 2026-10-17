"""Consume an exact kernel-authorized successor intent, without activating it.

The caller is trusted composition: it installs a public-key verifier, an exact policy
reference and execution identity. Indexed human instructions and review bytes are
evidence references, never authenticators. This component does not issue capabilities,
apply source, validate physical preimages, qualify baselines or admit Builder work.
Those operations require separate protected integration and independent evidence.

Requires the candidate's public ``Ledger.append_once_if_new`` atomic port. There is
deliberately no fallback to check-then-append on an older ledger implementation.
"""

from __future__ import annotations

import json
import posixpath
import re
from dataclasses import asdict, dataclass

from kernel.capability import CapabilityError, CapabilityVerifier
from kernel.cas import CAS, CasError, content_hash, is_valid_hash
from kernel.ledger import Event, Ledger, LedgerError, LedgerRow
from kernel.types import CapabilityToken, DomainTag, Role, StageId

from runtime.implementation_contract import (
    ContractValidationError,
    canonical_implementation_contract_bytes,
    implementation_contract_from_canonical_json,
)

PENDING = "PENDING_REQUALIFICATION_AND_ACTIVATION"
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")


class SupersessionError(ValueError):
    """An invalid, unauthenticated, stale or already consumed intent was denied."""


@dataclass(frozen=True, slots=True)
class SupersessionRequest:
    transaction_id: str
    predecessor_contract_ref: str
    successor_contract_ref: str
    source_prestate_ref: str
    defect_evidence_ref: str
    independent_review_ref: str
    indexed_authority_record_ref: str
    policy_ref: str
    expected_head_hash: str
    goal_id: str
    run_id: str
    session: str
    domain: str
    expiry_seq: int


@dataclass(frozen=True, slots=True)
class ConsumptionReceipt:
    row: LedgerRow
    required_requalifications: tuple[str, ...]
    invalidated_evidence_refs: tuple[str, ...]
    status: str = PENDING


def _canonical(value: object) -> bytes:
    try:
        return json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("ascii")
    except (ValueError, TypeError) as exc:
        raise SupersessionError("value is not canonical JSON") from exc


def request_digest(request: SupersessionRequest) -> str:
    """Exact public signing input; hashing a request does not authorize it."""
    if type(request) is not SupersessionRequest:
        raise SupersessionError("exact SupersessionRequest required")
    return content_hash(_canonical(asdict(request)))


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise SupersessionError(f"invalid {label}")
    return value


def _identity(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(character) < 32 for character in value)
    ):
        raise SupersessionError(f"invalid {label}")
    return value


def _hash(value: object, label: str) -> str:
    if not isinstance(value, str) or not is_valid_hash(value):
        raise SupersessionError(f"invalid SHA256 reference: {label}")
    return value


def _path(value: object) -> str:
    if (
        not isinstance(value, str)
        or not value
        or value != value.strip()
        or any(ord(char) < 32 for char in value)
        or value.startswith("/")
        or "\\" in value
        or any(char in value for char in "*?[]:")
        or any(part in ("", ".", "..") for part in value.split("/"))
        or posixpath.normpath(value) != value
    ):
        raise SupersessionError("scope requires exact canonical relative file paths")
    return value


def _strings(value: object, label: str, *, paths: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise SupersessionError(f"{label} must be a string array")
    if len(value) != len(set(value)):
        raise SupersessionError(f"{label} contains duplicates")
    for item in value:
        if paths:
            _path(item)
        elif not item:
            raise SupersessionError(f"{label} contains an empty value")
    return tuple(value)


def _object(value: object, fields: set[str], label: str) -> dict:
    if not isinstance(value, dict) or set(value) != fields:
        raise SupersessionError(f"{label} has missing or unknown fields")
    return value


def _reserved(path: str) -> bool:
    lowered = path.lower()
    return (
        lowered == "constitution"
        or lowered.startswith("constitution/")
        or lowered == "operations/engineering_lifecycle.md"
        or any(
            word in lowered for word in ("sentium", "trading", "order_execution", "live_capital")
        )
    )


class ScopeSupersessionService:
    """Runtime-owned consumer. The supplied verifier has no signing authority."""

    def __init__(
        self,
        *,
        cas: CAS,
        ledger: Ledger,
        verifier: CapabilityVerifier,
        goal_id: str,
        run_id: str,
        session: str,
        domain: DomainTag,
        policy_ref: str,
    ) -> None:
        self._cas = cas
        self._ledger = ledger
        self._verifier = verifier
        self._goal_id = _identity(goal_id, "goal")
        self._run_id = _identity(run_id, "run")
        self._session = _identity(session, "session")
        if not isinstance(domain, DomainTag):
            raise SupersessionError("explicit execution domain required")
        self._domain = domain.value
        self._policy_ref = _hash(policy_ref, "trusted policy")

    def _read(self, ref: str) -> bytes:
        _hash(ref, "CAS")
        raw = self._cas.get(ref)
        # Enforce integrity even when the caller's CAS disables verify_on_read.
        if content_hash(raw) != ref or not raw:
            raise SupersessionError("CAS content is empty or does not match its reference")
        return raw

    def _json(self, ref: str) -> dict:
        raw = self._read(ref)

        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise SupersessionError("duplicate JSON member")
                result[key] = value
            return result

        try:
            value = json.loads(raw, object_pairs_hook=pairs)
        except (ValueError, UnicodeError) as exc:
            raise SupersessionError("invalid JSON artifact") from exc
        if not isinstance(value, dict) or _canonical(value) != raw:
            raise SupersessionError("artifact must be a canonically encoded JSON object")
        return value

    def _obligations(
        self, policy: dict, scope: set[str]
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        _object(policy, {"schema", "authorized_paths", "protected_paths", "claims"}, "policy")
        if policy["schema"] != "paeos.scope-policy/1":
            raise SupersessionError("unknown policy schema")
        allowed = set(_strings(policy["authorized_paths"], "authorized paths", paths=True))
        protected = set(_strings(policy["protected_paths"], "protected paths", paths=True))
        if not scope <= allowed:
            raise SupersessionError("successor scope exceeds the installed exact policy")
        claims = policy["claims"]
        if not isinstance(claims, list):
            raise SupersessionError("claims must be an array")
        graph = {}
        for claim in claims:
            _object(claim, {"id", "source_paths", "depends_on", "evidence_refs"}, "claim")
            claim_id = _identifier(claim["id"], "claim id")
            if claim_id in graph:
                raise SupersessionError("duplicate claim id")
            sources = _strings(claim["source_paths"], "claim sources", paths=True)
            dependencies = _strings(claim["depends_on"], "claim dependencies")
            evidence = _strings(claim["evidence_refs"], "claim evidence")
            for ref in evidence:
                self._read(ref)
            graph[claim_id] = (set(sources), set(dependencies), set(evidence))
        if any(dependencies - graph.keys() for _, dependencies, _ in graph.values()):
            raise SupersessionError("dangling baseline dependency")
        # Kahn's algorithm validates the graph without recursion limits or implicit claims.
        remaining = set(graph)
        while remaining:
            ready = {name for name in remaining if not (graph[name][1] & remaining)}
            if not ready:
                raise SupersessionError("cyclic baseline dependencies")
            remaining -= ready
        impacted = {name for name, (sources, _, _) in graph.items() if sources & scope}
        while True:
            expanded = impacted | {
                name for name, (_, dependencies, _) in graph.items() if dependencies & impacted
            }
            if expanded == impacted:
                break
            impacted = expanded
        if scope & protected and "P1" not in impacted:
            raise SupersessionError("protected overlap requires mechanically impacted P1")
        stale = {ref for name in impacted for ref in graph[name][2]}
        return tuple(sorted(impacted)), tuple(sorted(stale))

    def _validate_inputs(
        self, request: SupersessionRequest
    ) -> tuple[tuple[str, ...], tuple[str, ...]]:
        for field, ref in asdict(request).items():
            if field.endswith("_ref") or field == "expected_head_hash":
                _hash(ref, field)
        _identifier(request.transaction_id, "transaction id")
        if (
            request.goal_id,
            request.run_id,
            request.session,
            request.domain,
            request.policy_ref,
        ) != (self._goal_id, self._run_id, self._session, self._domain, self._policy_ref):
            raise SupersessionError("request differs from trusted execution context or policy")
        if type(request.expiry_seq) is not int or request.expiry_seq < 1:
            raise SupersessionError("positive sequence expiry required")
        old_raw = self._read(request.predecessor_contract_ref)
        new_raw = self._read(request.successor_contract_ref)
        old = implementation_contract_from_canonical_json(old_raw)
        new = implementation_contract_from_canonical_json(new_raw)
        if (
            old.contract_id == new.contract_id
            or old.contract_hash == new.contract_hash
            or request.predecessor_contract_ref == request.successor_contract_ref
        ):
            raise SupersessionError("successor must have a new immutable contract identity")
        if canonical_implementation_contract_bytes(old) != old_raw:
            raise SupersessionError("predecessor bytes changed")
        for name in (
            "goal_id",
            "run_id",
            "ceremony_trace",
            "base_commit",
            "required_artifacts",
            "acceptance_commands",
            "rollback_argv",
            "data_class",
        ):
            if getattr(old, name) != getattr(new, name):
                raise SupersessionError(f"scope supersession cannot change {name}")
        if (new.goal_id, new.run_id) != (self._goal_id, self._run_id):
            raise SupersessionError("contract is outside trusted goal/run")
        scope = {_path(path) for path in new.allowed_paths}
        for path in old.allowed_paths:
            _path(path)
        if not set(old.allowed_paths) < scope:
            raise SupersessionError("successor scope must strictly extend predecessor scope")
        if any(_reserved(path) for path in scope):
            raise SupersessionError("constitutional or sovereign scope is outside this mechanism")
        prestate = self._json(request.source_prestate_ref)
        _object(prestate, {"schema", "files"}, "source prestate")
        if prestate["schema"] != "paeos.scope-prestate/1" or not isinstance(
            prestate["files"], list
        ):
            raise SupersessionError("unknown source prestate schema")
        observed = set()
        for entry in prestate["files"]:
            _object(entry, {"path", "sha256"}, "prestate file")
            path = _path(entry["path"])
            if path in observed:
                raise SupersessionError("duplicate prestate path")
            observed.add(path)
            if entry["sha256"] != "ABSENT":
                _hash(entry["sha256"], "preimage")
        if observed != scope:
            raise SupersessionError("prestate must cover exactly every successor path")
        for ref in (
            request.defect_evidence_ref,
            request.independent_review_ref,
            request.indexed_authority_record_ref,
        ):
            self._read(ref)
        return self._obligations(self._json(request.policy_ref), scope)

    def consume(
        self, request: SupersessionRequest, authority: CapabilityToken
    ) -> ConsumptionReceipt:
        """Consume once, retaining pending obligations. Never return execution authority.

        An unclassified exception from the atomic append may be a committed operation
        whose response was lost. It propagates unchanged; there is no retry here.
        """
        try:
            atomic_append = getattr(self._ledger, "append_once_if_new", None)
            if not callable(atomic_append):
                raise SupersessionError("atomic append_once_if_new ledger port is required")
            digest = request_digest(request)
            if type(authority) is not CapabilityToken:
                raise SupersessionError(
                    "existing kernel capability is required; evidence is not authority"
                )
            obligations, stale = self._validate_inputs(request)
            head_hash = self._ledger.verify_chain()
            head = self._ledger.head()
            if head_hash != request.expected_head_hash or (head and head.row_hash != head_hash):
                raise SupersessionError("stale ledger predecessor")
            next_seq = (head.seq if head else 0) + 1
            if next_seq > request.expiry_seq:
                raise SupersessionError("request sequence expiry exceeded")
            self._verifier.verify(
                authority,
                goal_id=self._goal_id,
                run_id=self._run_id,
                stage=StageId.PLAN,
                role=Role.RATIFIER,
                session=self._session,
                current_seq=next_seq,
                operation="scope.supersede:" + digest,
                mission_execution_digest=digest,
            )
            # Every effect follows validation/authentication; CAS writes are immutable.
            request_ref = self._cas.put(_canonical(asdict(request)))
            binding = authority.bound_to
            token_ref = self._cas.put(
                _canonical(
                    {
                        "token": authority.token,
                        "bound_to": {
                            "goal_id": binding.goal_id,
                            "run_id": binding.run_id,
                            "stage": binding.stage.value,
                            "role": binding.role.value,
                            "session": binding.session,
                            "mission_execution_digest": binding.mission_execution_digest,
                        },
                        "operations": list(authority.operations),
                        "issued_seq": authority.issued_seq,
                        "expires_seq": authority.expires_seq,
                    }
                )
            )
            row = atomic_append(
                Event(
                    1,
                    "scope_supersession_consumed",
                    {
                        "transaction_id": request.transaction_id,
                        "request_ref": request_ref,
                        "authority_token_ref": token_ref,
                        "predecessor_contract_ref": request.predecessor_contract_ref,
                        "successor_contract_ref": request.successor_contract_ref,
                        "required_requalifications": list(obligations),
                        "invalidated_evidence_refs": list(stale),
                        "status": PENDING,
                    },
                ),
                transition_id="scope-supersession:" + request.transaction_id,
                expected_head_hash=request.expected_head_hash,
                domain_tag=self._domain,
            )
            return ConsumptionReceipt(row, obligations, stale)
        except (CapabilityError, ContractValidationError, CasError, LedgerError) as exc:
            raise SupersessionError(str(exc)) from exc
