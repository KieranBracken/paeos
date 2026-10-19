"""Task-scoped loopback Responses broker for a confined Codex worker.

The worker receives only an ephemeral local bearer capability. Long-lived ChatGPT OAuth state is
read and used by this parent-owned broker, never copied into the worker filesystem or environment.
The broker exposes one fixed model and one endpoint, records hashes rather than payloads, and
becomes unreachable when the task ends. Egress is disabled until trusted disclosure authority
is integrated; a local bearer or a signed launch request is not disclosure permission.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import os
import re
import secrets
import socket
import ssl
import stat
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from runtime.integrations.disclosure_frame import FrameRejected, inspect_responses_frame

__all__ = [
    "AUTHORIZED_MODEL_IDS",
    "MAX_TASK_REQUESTS",
    "BrokerReply",
    "ParentOwnedResponsesBroker",
]

_DEFAULT_MODEL_ID = "gpt-5.6-sol"
AUTHORIZED_MODEL_IDS = frozenset({"gpt-5.6-sol", "gpt-5.6-luna"})
_ENV_KEY = "PAEOS_TASK_BROKER_TOKEN"
_MAX_REQUEST_BYTES = 2 * 1024 * 1024
_MAX_RESPONSE_BYTES = 8 * 1024 * 1024
# A Codex turn may legitimately require more than eight Responses calls (reasoning, tool/result
# exchange, and finalization). Keep the capability task-scoped and finite, but do not convert the
# old eight-call ceiling into a provider-execution failure for otherwise bounded work.
MAX_TASK_REQUESTS = 32
_TTL_SECONDS = 660.0
MODEL_IDENTITY_CONTRACT = "codex-0.147.0:be6e8eac029b183056b7e4402879f15d2c85f61b"


@dataclass(frozen=True, slots=True)
class BrokerReply:
    status: int
    content_type: str
    body: bytes
    upstream_headers: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class _RequestReceipt:
    request_id: int
    request_sha256: str
    response_sha256: str = ""
    transport_outcome: str = "upstream_started"
    upstream_status: int | None = None
    upstream_error_class: str | None = None
    observed_model_id: str | None = None
    model_identity_contract: str | None = None
    model_identity_error: str | None = None


Upstream = Callable[[bytes, str, str], BrokerReply]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ModelIdentityError(ValueError):
    """Missing or ambiguous provider-reported model; no response content exposed."""


def validate_server_model(reply: BrokerReply, expected_model: str) -> str:
    """Parse the pinned Codex HTTP/SSE ServerModel contract, never response.model.

    This is a provider assertion received through the upstream TLS boundary, not an
    attestation of backend weights. A complete successful SSE response and one exact
    model across all declarations are required. WebSocket top-level header metadata
    is deliberately unsupported on this HTTP route.
    """

    def reject():
        raise ModelIdentityError("unverified_server_model")

    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                reject()
            result[name] = value
        return result

    models: set[str] = set()

    def record(value):
        if type(value) is not str or not re.fullmatch(r"[a-z0-9][a-z0-9_.:/-]{0,255}", value):
            reject()
        models.add(value)
        if len(models) != 1:
            reject()

    try:
        if (
            not isinstance(reply, BrokerReply)
            or type(reply.status) is not int
            or not 200 <= reply.status < 300
            or type(reply.content_type) is not str
            or reply.content_type.split(";", 1)[0].strip().lower() != "text/event-stream"
            or type(reply.body) is not bytes
            or not 0 < len(reply.body) <= _MAX_RESPONSE_BYTES
            or type(reply.upstream_headers) is not tuple
            or type(expected_model) is not str
            or not re.fullmatch(r"[a-z0-9][a-z0-9_.:/-]{0,255}", expected_model)
        ):
            reject()
        for header in reply.upstream_headers:
            if (
                type(header) is not tuple
                or len(header) != 2
                or any(type(v) is not str for v in header)
            ):
                reject()
            if header[0].lower() == "openai-model":
                record(header[1])
        text = reply.body.decode("utf-8").replace("\r\n", "\n")
        if "\r" in text or not text.endswith("\n\n"):
            reject()
        completed = False
        done = False
        for frame in text.split("\n\n"):
            data = []
            event_type = None
            for line in frame.split("\n"):
                if not line or line.startswith(":"):
                    continue
                field, _, value = line.partition(":")
                value = value.removeprefix(" ")
                if field == "data":
                    data.append(value)
                elif field == "event":
                    if event_type is not None:
                        reject()
                    event_type = value
                elif field not in {"id", "retry"}:
                    reject()
            if not data:
                continue
            payload = "\n".join(data)
            if payload == "[DONE]":
                if not completed or done:
                    reject()
                done = True
                continue
            if completed or done:
                reject()
            event = json.loads(payload, object_pairs_hook=unique, parse_constant=lambda _: reject())
            if type(event) is not dict or type(event.get("type")) is not str:
                reject()
            kind = event["type"]
            if event_type is not None and event_type != kind:
                reject()
            if kind in {"error", "response.failed", "response.incomplete"}:
                reject()
            response = event.get("response")
            if response is not None and type(response) is not dict:
                reject()
            if response is not None and "headers" in response:
                headers = response["headers"]
                if type(headers) is not dict:
                    reject()
                for name, value in headers.items():
                    if name.lower() in {"openai-model", "x-openai-model"}:
                        record(value)
            if kind == "response.completed":
                if (
                    type(response) is not dict
                    or type(response.get("id")) is not str
                    or not response["id"]
                    or response.get("status") != "completed"
                ):
                    reject()
                completed = True
        if not completed or models != {expected_model}:
            reject()
        return next(iter(models))
    except (ValueError, UnicodeError, RecursionError, TypeError):
        raise ModelIdentityError("unverified_server_model") from None


class DisclosureAuthorityUnavailable(RuntimeError):
    """The broker has no trusted current disclosure authorization path."""


def _require_disclosure_authority() -> None:
    """Deny until enrollment, currentness, payload/route binding and attempts are enforced.

    The dormant policy verifier proves only a signature. No worker field, callback,
    flag or transport credential can supply the missing authority. This intentionally
    has no allow path; a future consumer requires a separately reviewed integration.
    """
    raise DisclosureAuthorityUnavailable("trusted disclosure authority is unavailable")


class ParentOwnedResponsesBroker:
    """One-task localhost gateway whose credential-bearing side remains in the parent."""

    def __init__(
        self,
        *,
        auth_path: Path,
        model_id: str = _DEFAULT_MODEL_ID,
        upstream: Upstream | None = None,
        clock: Callable[[], float] | None = None,
        max_requests: int = MAX_TASK_REQUESTS,
    ) -> None:
        if model_id not in AUTHORIZED_MODEL_IDS:
            raise ValueError("parent broker model is not an authorized fixed Codex route")
        if type(max_requests) is not int or not 1 <= max_requests <= MAX_TASK_REQUESTS:
            raise ValueError("parent broker request limit is outside the bounded range")
        self._auth_path = Path(auth_path)
        self._model_id = model_id
        self._max_requests = max_requests
        self._upstream = upstream or self._forward_to_chatgpt
        self._clock = clock or time.time
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._task_token: str | None = None
        self._expires_at = 0.0
        self._request_count = 0
        self._request_receipts: list[_RequestReceipt] = []
        self._local_rejection_count = 0
        self._local_error_class: str | None = None
        self._lock = threading.Lock()

    @staticmethod
    def _classify_upstream_exception(exc: Exception) -> str:
        if isinstance(exc, (TimeoutError, socket.timeout)):
            return "timeout"
        if isinstance(exc, ssl.SSLError):
            return "tls_failure"
        if isinstance(exc, OSError):
            return "transport_os_error"
        return "upstream_exception"

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("task broker is not active")
        host, port = self._server.server_address
        if host != "127.0.0.1" or not isinstance(port, int):
            raise RuntimeError("task broker binding is invalid")
        return f"http://127.0.0.1:{port}/v1"

    @property
    def loopback_port(self) -> int:
        if self._server is None:
            raise RuntimeError("task broker is not active")
        return int(self._server.server_address[1])

    @property
    def task_token(self) -> str:
        if self._task_token is None:
            raise RuntimeError("task broker capability is unavailable")
        return self._task_token

    @property
    def environment_key(self) -> str:
        return _ENV_KEY

    def _load_parent_auth(self) -> tuple[str, str]:
        """Read only a bounded private regular file through pinned directory descriptors."""
        path = self._auth_path
        if not path.is_absolute() or any(part in {".", ".."} for part in path.parts):
            raise RuntimeError("parent Codex auth state is unavailable")
        directory = None
        descriptor = None
        try:
            directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
            for part in path.parts[1:-1]:
                child = os.open(
                    part,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                    dir_fd=directory,
                )
                os.close(directory)
                directory = child
            descriptor = os.open(
                path.name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=directory,
            )
            metadata = os.fstat(descriptor)
            limit = 1024 * 1024
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_IMODE(metadata.st_mode) & 0o077
                or metadata.st_uid != os.geteuid()
                or not 0 < metadata.st_size <= limit
            ):
                raise RuntimeError("parent Codex auth state is not a bounded private regular file")
            blocks = []
            total = 0
            while total <= limit:
                block = os.read(descriptor, min(65536, limit + 1 - total))
                if not block:
                    break
                blocks.append(block)
                total += len(block)
            if total > limit:
                raise RuntimeError("parent Codex auth state exceeds its size bound")

            def unique(pairs):
                result = {}
                for name, value in pairs:
                    if name in result:
                        raise ValueError("duplicate auth field")
                    result[name] = value
                return result

            document = json.loads(b"".join(blocks), object_pairs_hook=unique)
        except (OSError, ValueError, UnicodeError, RecursionError):
            raise RuntimeError("parent Codex auth state is unavailable or malformed") from None
        finally:
            if descriptor is not None:
                os.close(descriptor)
            if directory is not None:
                os.close(directory)
        tokens = document.get("tokens") if type(document) is dict else None
        access_token = tokens.get("access_token") if type(tokens) is dict else None
        account_id = tokens.get("account_id") if type(tokens) is dict else None
        if any(
            type(value) is not str
            or not value
            or len(value) > 65536
            or any(ord(c) <= 32 or ord(c) >= 127 for c in value)
            for value in (access_token, account_id)
        ):
            raise RuntimeError("parent Codex auth state lacks valid header identities")
        return access_token, account_id

    def start(self) -> None:
        if self._server is not None or self._task_token is not None:
            raise RuntimeError("task broker is already active")
        task_token = secrets.token_urlsafe(32)
        broker = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, _format: str, *args: object) -> None:
                return

            def _send(
                self, status: int, body: bytes, content_type: str = "application/json"
            ) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
                self.close_connection = True

            def do_POST(self) -> None:
                if self.path != "/v1/responses":
                    self._send(404, b'{"error":{"type":"not_found"}}')
                    return
                supplied = self.headers.get("Authorization", "")
                expected = f"Bearer {broker._task_token}"
                if broker._task_token is None or not hmac.compare_digest(supplied, expected):
                    self._send(401, b'{"error":{"type":"auth_error"}}')
                    return
                if broker._clock() > broker._expires_at:
                    self._send(401, b'{"error":{"type":"expired_capability"}}')
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = 0
                if not 0 < length <= _MAX_REQUEST_BYTES:
                    self._send(413, b'{"error":{"type":"bounded_request_required"}}')
                    return
                body = self.rfile.read(length)
                try:
                    request = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._send(400, b'{"error":{"type":"invalid_request"}}')
                    return
                if not isinstance(request, dict) or request.get("model") != broker._model_id:
                    self._send(403, b'{"error":{"type":"model_not_authorized"}}')
                    return
                try:
                    _require_disclosure_authority()
                except DisclosureAuthorityUnavailable:
                    with broker._lock:
                        broker._local_rejection_count += 1
                        broker._local_error_class = "disclosure_authority_unavailable"
                    self._send(403, b'{"error":{"type":"disclosure_authority_unavailable"}}')
                    return
                try:
                    # Authorize/send the original immutable bytes, never a reconstructed
                    # subset which could omit attachments, history or tool definitions.
                    inspect_responses_frame(body, expected_model=broker._model_id)
                except FrameRejected:
                    with broker._lock:
                        broker._local_rejection_count += 1
                        broker._local_error_class = "outbound_frame_rejected"
                    self._send(403, b'{"error":{"type":"outbound_frame_rejected"}}')
                    return
                with broker._lock:
                    if broker._request_count >= broker._max_requests:
                        broker._local_rejection_count += 1
                        broker._local_error_class = "task_request_limit_reached"
                        self._send(429, b'{"error":{"type":"task_limit_reached"}}')
                        return
                    broker._request_count += 1
                    receipt = _RequestReceipt(broker._request_count, _sha256(body))
                    broker._request_receipts.append(receipt)
                try:
                    # The absent-authority path must not even inspect host credentials.
                    access_token, account_id = broker._load_parent_auth()
                    reply = broker._upstream(body, access_token, account_id)
                except Exception as exc:
                    with broker._lock:
                        broker._request_receipts[receipt.request_id - 1] = replace(
                            receipt,
                            transport_outcome="upstream_failure",
                            upstream_error_class=broker._classify_upstream_exception(exc),
                        )
                    self._send(502, b'{"error":{"type":"upstream_unavailable"}}')
                    return
                if (
                    not isinstance(reply, BrokerReply)
                    or type(reply.status) is not int
                    or not 100 <= reply.status <= 599
                    or not isinstance(reply.body, bytes)
                    or len(reply.body) > _MAX_RESPONSE_BYTES
                ):
                    with broker._lock:
                        broker._request_receipts[receipt.request_id - 1] = replace(
                            receipt, transport_outcome="invalid_upstream_response"
                        )
                    self._send(502, b'{"error":{"type":"upstream_invalid"}}')
                    return
                observed_model = None
                identity_error = None
                try:
                    observed_model = validate_server_model(reply, broker._model_id)
                except ModelIdentityError:
                    identity_error = "unverified_server_model"
                with broker._lock:
                    broker._request_receipts[receipt.request_id - 1] = replace(
                        receipt,
                        response_sha256=_sha256(reply.body),
                        transport_outcome="response_received",
                        upstream_status=reply.status,
                        observed_model_id=observed_model,
                        model_identity_contract=MODEL_IDENTITY_CONTRACT if observed_model else None,
                        model_identity_error=identity_error,
                    )
                self._send(reply.status, reply.body, reply.content_type)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        self._task_token = task_token
        self._expires_at = self._clock() + _TTL_SECONDS
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    @staticmethod
    def _forward_to_chatgpt(body: bytes, access_token: str, account_id: str) -> BrokerReply:
        # The network owner must also reject direct calls that bypass the HTTP handler.
        _require_disclosure_authority()
        # This direct entry has no parent task context, so production remains denied
        # above. Even an isolated test bypass cannot omit complete-frame inspection.
        try:
            model = json.loads(body).get("model")
        except (ValueError, TypeError, AttributeError):
            raise FrameRejected("unsupported or unbound outbound frame") from None
        inspect_responses_frame(body, expected_model=model)
        headers = {
            "Authorization": f"Bearer {access_token}",
            "ChatGPT-Account-Id": account_id,
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "OpenAI-Beta": "responses=experimental",
            "User-Agent": "paeos-trusted-codex-supervisor/1",
        }
        connection = http.client.HTTPSConnection("chatgpt.com", 443, timeout=300)
        try:
            connection.request("POST", "/backend-api/codex/responses", body=body, headers=headers)
            response = connection.getresponse()
            response_body = response.read(_MAX_RESPONSE_BYTES + 1)
            if len(response_body) > _MAX_RESPONSE_BYTES:
                raise RuntimeError("upstream response exceeds bounded size")
            return BrokerReply(
                response.status,
                response.getheader("Content-Type", "application/octet-stream"),
                response_body,
                tuple(
                    (name, value)
                    for name, value in response.getheaders()
                    if name.lower() == "openai-model"
                ),
            )
        finally:
            connection.close()

    def evidence(self) -> dict[str, object]:
        with self._lock:
            # Immutable records are replaced only for their own reserved identity. Export
            # fresh dictionaries so neither later completions nor callers mutate a snapshot.
            receipts = [asdict(receipt) for receipt in self._request_receipts]
            single = self._request_receipts[0] if len(receipts) == 1 else None
            outcome = "not_contacted"
            if receipts:
                outcome = next(
                    (
                        receipt.transport_outcome
                        for receipt in self._request_receipts
                        if receipt.transport_outcome != "response_received"
                    ),
                    "response_received",
                )
            if self._local_rejection_count:
                outcome = "local_rejection"
            return {
                "schema": "paeos.task-scoped-responses-broker/3",
                "binding": "127.0.0.1",
                "model_id": self._model_id,
                "request_count": self._request_count,
                "request_limit": self._max_requests,
                # Scalar provenance describes one call only; multiple calls have no
                # truthful single request/response pair or upstream status.
                "request_sha256": single.request_sha256 if single else "",
                "response_sha256": single.response_sha256 if single else "",
                "transport_outcome": outcome,
                "upstream_status": single.upstream_status if single else None,
                "upstream_error_class": single.upstream_error_class if single else None,
                "request_receipts": receipts,
                "local_rejection_count": self._local_rejection_count,
                "local_error_class": self._local_error_class,
                "capability_expires_at": self._expires_at,
            }

    def close(self) -> None:
        server = self._server
        thread = self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        self._task_token = None
        self._expires_at = 0.0

    def __enter__(self) -> ParentOwnedResponsesBroker:
        self.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()
