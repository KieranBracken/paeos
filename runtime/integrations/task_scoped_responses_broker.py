"""Task-scoped loopback Responses broker for a confined Codex worker.

The worker receives only an ephemeral local bearer capability. Long-lived ChatGPT OAuth state is
read and used by this parent-owned broker, never copied into the worker filesystem or environment.
The broker exposes one fixed model and one endpoint, records hashes rather than payloads, and
becomes unreachable when the task ends.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import secrets
import socket
import ssl
import stat
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

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


@dataclass(frozen=True, slots=True)
class BrokerReply:
    status: int
    content_type: str
    body: bytes


Upstream = Callable[[bytes, str, str], BrokerReply]


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ParentOwnedResponsesBroker:
    """One-task localhost gateway whose credential-bearing side remains in the parent."""

    def __init__(
        self,
        *,
        auth_path: Path,
        model_id: str = _DEFAULT_MODEL_ID,
        upstream: Upstream | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        if model_id not in AUTHORIZED_MODEL_IDS:
            raise ValueError("parent broker model is not an authorized fixed Codex route")
        self._auth_path = Path(auth_path)
        self._model_id = model_id
        self._upstream = upstream or self._forward_to_chatgpt
        self._clock = clock or time.time
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._task_token: str | None = None
        self._access_token: str | None = None
        self._account_id: str | None = None
        self._expires_at = 0.0
        self._request_count = 0
        self._request_sha256 = ""
        self._response_sha256 = ""
        self._transport_outcome = "not_contacted"
        self._upstream_status: int | None = None
        self._upstream_error_class: str | None = None
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
        path = self._auth_path
        if not path.is_absolute() or path.is_symlink() or not path.is_file():
            raise RuntimeError("parent Codex auth state is unavailable")
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise RuntimeError("parent Codex auth state permissions are too broad")
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("parent Codex auth state is malformed") from exc
        tokens = document.get("tokens") if isinstance(document, dict) else None
        access_token = tokens.get("access_token") if isinstance(tokens, dict) else None
        account_id = tokens.get("account_id") if isinstance(tokens, dict) else None
        if (
            not isinstance(access_token, str)
            or not access_token
            or not isinstance(account_id, str)
            or not account_id
        ):
            raise RuntimeError("parent Codex auth state lacks required identity")
        return access_token, account_id

    def start(self) -> None:
        if self._server is not None or self._task_token is not None:
            raise RuntimeError("task broker is already active")
        access_token, account_id = self._load_parent_auth()
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
                with broker._lock:
                    if broker._request_count >= MAX_TASK_REQUESTS:
                        broker._local_rejection_count += 1
                        broker._local_error_class = "task_request_limit_reached"
                        broker._transport_outcome = "local_rejection"
                        self._send(429, b'{"error":{"type":"task_limit_reached"}}')
                        return
                    broker._request_count += 1
                    broker._request_sha256 = _sha256(body)
                    broker._response_sha256 = ""
                    broker._transport_outcome = "upstream_started"
                    broker._upstream_status = None
                    broker._upstream_error_class = None
                try:
                    assert broker._access_token is not None
                    assert broker._account_id is not None
                    reply = broker._upstream(body, broker._access_token, broker._account_id)
                except Exception as exc:
                    with broker._lock:
                        broker._transport_outcome = "upstream_failure"
                        broker._upstream_error_class = broker._classify_upstream_exception(exc)
                    self._send(502, b'{"error":{"type":"upstream_unavailable"}}')
                    return
                if (
                    not isinstance(reply, BrokerReply)
                    or not 100 <= reply.status <= 599
                    or not isinstance(reply.body, bytes)
                    or len(reply.body) > _MAX_RESPONSE_BYTES
                ):
                    with broker._lock:
                        broker._transport_outcome = "invalid_upstream_response"
                    self._send(502, b'{"error":{"type":"upstream_invalid"}}')
                    return
                with broker._lock:
                    broker._response_sha256 = _sha256(reply.body)
                    broker._transport_outcome = "response_received"
                    broker._upstream_status = reply.status
                self._send(reply.status, reply.body, reply.content_type)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        server.daemon_threads = True
        self._access_token = access_token
        self._account_id = account_id
        self._task_token = task_token
        self._expires_at = self._clock() + _TTL_SECONDS
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, daemon=True)
        self._thread.start()

    @staticmethod
    def _forward_to_chatgpt(body: bytes, access_token: str, account_id: str) -> BrokerReply:
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
            )
        finally:
            connection.close()

    def evidence(self) -> dict[str, object]:
        with self._lock:
            return {
                "schema": "paeos.task-scoped-responses-broker/1",
                "binding": "127.0.0.1",
                "model_id": self._model_id,
                "request_count": self._request_count,
                "request_sha256": self._request_sha256,
                "response_sha256": self._response_sha256,
                "transport_outcome": self._transport_outcome,
                "upstream_status": self._upstream_status,
                "upstream_error_class": self._upstream_error_class,
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
        self._access_token = None
        self._account_id = None
        self._expires_at = 0.0

    def __enter__(self) -> ParentOwnedResponsesBroker:
        self.start()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()
