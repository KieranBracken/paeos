"""
PAEOS Model Router — Local Unified OpenAI-Compatible HTTP Gateway Server
Listens on 127.0.0.1:4000 (Loopback Only).
Enforces local bearer token authentication, tool calling, SSE streaming, and hardened loopback CORS.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import time
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import Any

from paeos.model_router.observability import ObservabilityDiagnostics
from paeos.model_router.router import ModelRouter
from paeos.model_router.types import (
    DataClass,
    LogicalModel,
    ModelFamily,
    NormalizedError,
    TaskClass,
    TaskRequest,
)


class GatewayHandler(BaseHTTPRequestHandler):
    router: ModelRouter
    diagnostics: ObservabilityDiagnostics
    api_key: str | None = None

    def _check_auth(self) -> bool:
        """Validates incoming Authorization: Bearer <token> if api_key is configured."""
        if not self.api_key:
            return True
        auth_header = self.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._send_json(401, {"error": {"message": "Missing or malformed Authorization header. Expected 'Bearer <key>'.", "type": "auth_error"}})
            return False
        token = auth_header[7:].strip()
        if token != self.api_key:
            self._send_json(401, {"error": {"message": "Invalid Bearer token provided.", "type": "auth_error"}})
            return False
        return True

    def _send_json(self, status: int, data: dict[str, Any]) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        origin = self.headers.get("Origin", "")
        if "127.0.0.1" in origin or "localhost" in origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:
        self.send_response(200)
        origin = self.headers.get("Origin", "")
        if "127.0.0.1" in origin or "localhost" in origin:
            self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, X-PAEOS-Data-Class, X-PAEOS-Task-Class")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._check_auth():
            return

        if self.path in ("/v1/models", "/models"):
            models_data = []
            for m in self.router.catalog.list_models():
                models_data.append({
                    "id": m.model_id,
                    "object": "model",
                    "created": int(m.verified_at),
                    "owned_by": m.provider_id.value,
                    "permission": [],
                    "root": m.model_id,
                    "parent": None,
                    "cost_tier": m.cost_tier.value,
                    "pricing_verified_free": m.pricing_verified_free,
                    "live_verified": m.live_verified,
                    "available": m.available,
                })
            for lm in LogicalModel:
                models_data.append({
                    "id": lm.value,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "paeos-router",
                    "permission": [],
                    "root": lm.value,
                    "parent": None,
                    "cost_tier": "LOGICAL",
                })
            self._send_json(200, {"object": "list", "data": models_data})

        elif self.path in ("/v1/quota", "/quota", "/v1/usage", "/usage"):
            status = self.diagnostics.get_mesh_status()
            self._send_json(200, {
                "object": "quota_status",
                "quota_reset_countdown": status["quota_reset_countdown"],
                "quota_reset_in_seconds": status["quota_reset_in_seconds"],
                "providers": status["providers"],
            })

        elif self.path in ("/health", "/v1/health"):
            status = self.diagnostics.get_mesh_status()
            self._send_json(200, {"status": "ok", "mesh": status})

        elif self.path in ("/metrics", "/v1/metrics"):
            status = self.diagnostics.get_mesh_status()
            self._send_json(200, status)

        else:
            self._send_json(404, {"error": {"message": f"Endpoint not found: {self.path}", "type": "not_found"}})

    def do_POST(self) -> None:
        if not self._check_auth():
            return

        if self.path not in ("/v1/chat/completions", "/chat/completions"):
            self._send_json(404, {"error": {"message": f"Endpoint not found: {self.path}", "type": "not_found"}})
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(length)
            body = json.loads(body_raw.decode("utf-8"))
        except Exception as e:
            self._send_json(400, {"error": {"message": f"Malformed JSON request: {e}", "type": "invalid_request_error"}})
            return

        messages = body.get("messages", [])
        if not messages:
            self._send_json(400, {"error": {"message": "Field 'messages' is required.", "type": "invalid_request_error"}})
            return

        requested_model = body.get("model", LogicalModel.PAEOS_AUTO.value)
        logical_model: LogicalModel | None = None
        for lm in LogicalModel:
            if lm.value == requested_model:
                logical_model = lm
                break

        data_class_str = body.get("data_class", self.headers.get("X-PAEOS-Data-Class", DataClass.INTERNAL.value))
        try:
            data_class = DataClass(data_class_str.upper())
        except ValueError:
            data_class = DataClass.INTERNAL

        task_class_str = body.get("task_class", self.headers.get("X-PAEOS-Task-Class", TaskClass.ROUTINE.value))
        try:
            task_class = TaskClass(task_class_str.upper())
        except ValueError:
            task_class = TaskClass.ROUTINE

        builder_family_str = body.get("builder_family", self.headers.get("X-PAEOS-Builder-Family"))
        builder_family: ModelFamily | None = None
        if builder_family_str:
            with contextlib.suppress(ValueError):
                builder_family = ModelFamily(builder_family_str.lower())

        stream = bool(body.get("stream", False))
        tools = body.get("tools")
        tool_choice = body.get("tool_choice")

        req = TaskRequest(
            messages=messages,
            task_class=task_class,
            data_class=data_class,
            logical_model=logical_model or LogicalModel.PAEOS_AUTO,
            explicit_model=requested_model if not logical_model else None,
            builder_family=builder_family,
            tools=tools,
            tool_choice=tool_choice,
            stream=stream,
            max_tokens=body.get("max_tokens"),
            temperature=body.get("temperature", 0.7),
        )

        try:
            resp = self.router.route(req)
            chat_id = f"chatcmpl-{int(time.time() * 1000)}"

            if stream:
                # SSE Streaming output for Cline agent compatibility
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                origin = self.headers.get("Origin", "")
                if "127.0.0.1" in origin or "localhost" in origin:
                    self.send_header("Access-Control-Allow-Origin", origin)
                self.end_headers()
                self.close_connection = True

                # Chunk 1: Role & Content / Tool Calls
                delta_payload: dict[str, Any] = {"role": "assistant"}
                if resp.content:
                    delta_payload["content"] = resp.content
                if resp.tool_calls:
                    delta_payload["tool_calls"] = resp.tool_calls

                chunk_1 = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": resp.model_id,
                    "provider": resp.provider_id.value,
                    "choices": [
                        {
                            "index": 0,
                            "delta": delta_payload,
                            "finish_reason": None,
                        }
                    ],
                }
                self.wfile.write(f"data: {json.dumps(chunk_1)}\n\n".encode())
                self.wfile.flush()

                # Chunk 2: Finish Reason
                chunk_2 = {
                    "id": chat_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": resp.model_id,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": resp.finish_reason or "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": resp.prompt_tokens,
                        "completion_tokens": resp.completion_tokens,
                        "total_tokens": resp.total_tokens,
                    },
                }
                self.wfile.write(f"data: {json.dumps(chunk_2)}\n\n".encode())
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()

            else:
                # Non-streaming standard JSON response
                msg_payload: dict[str, Any] = {
                    "role": "assistant",
                    "content": resp.content,
                }
                if resp.tool_calls:
                    msg_payload["tool_calls"] = resp.tool_calls

                openai_resp = {
                    "id": chat_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": resp.model_id,
                    "provider": resp.provider_id.value,
                    "system_fingerprint": f"paeos-router-{resp.family.value}",
                    "choices": [
                        {
                            "index": 0,
                            "message": msg_payload,
                            "finish_reason": resp.finish_reason or ("tool_calls" if resp.tool_calls else "stop"),
                        }
                    ],
                    "usage": {
                        "prompt_tokens": resp.prompt_tokens,
                        "completion_tokens": resp.completion_tokens,
                        "total_tokens": resp.total_tokens,
                    },
                    "fallback_chain": resp.fallback_chain,
                    "latency_ms": round(resp.latency_ms, 1),
                }
                self._send_json(200, openai_resp)

        except NormalizedError as ne:
            status_code = ne.http_status or 502
            self._send_json(status_code, {
                "error": {
                    "message": ne.message,
                    "type": ne.error_type.value,
                    "provider": ne.provider_id.value if ne.provider_id else None,
                    "retry_after": ne.retry_after,
                }
            })
        except Exception as e:
            self._send_json(500, {"error": {"message": f"Router internal error: {e}", "type": "internal_error"}})

    def log_message(self, format: str, *args: Any) -> None:
        pass


def run_gateway_server(
    host: str = "127.0.0.1",
    port: int = 4000,
    router: ModelRouter | None = None,
    api_key: str | None = None,
) -> HTTPServer:
    """Instantiates and starts the local loopback gateway server."""
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError(f"SECURITY VIOLATION: Gateway server must strictly bind to loopback (127.0.0.1), got '{host}'.")

    r = router or ModelRouter()
    configured_key = api_key or os.environ.get("PAEOS_GATEWAY_KEY")
    if not configured_key and r.credentials.env_file.exists():
        for line in r.credentials.env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("PAEOS_GATEWAY_KEY="):
                configured_key = line.split("=", 1)[1].strip().strip('"\'')

    diagnostics = ObservabilityDiagnostics(r.state_db, r.catalog, r.credentials)

    class CustomHandler(GatewayHandler):

        pass

    CustomHandler.router = r
    CustomHandler.diagnostics = diagnostics
    CustomHandler.api_key = configured_key

    server = ThreadingHTTPServer((host, port), CustomHandler)
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PAEOS Local Model Router OpenAI-Compatible Gateway")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface (strictly 127.0.0.1)")
    parser.add_argument("--port", type=int, default=4000, help="Port (default: 4000)")
    parser.add_argument("--api-key", default=None, help="Optional Bearer token for local authentication")
    args = parser.parse_args()

    print(f"Starting PAEOS Gateway on http://{args.host}:{args.port}/v1 ...")
    server = run_gateway_server(host=args.host, port=args.port, api_key=args.api_key)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PAEOS Gateway.")
        server.server_close()
