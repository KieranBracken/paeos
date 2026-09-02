"""
Adversarial Unit Tests: Local Unified Gateway HTTP Server (127.0.0.1:4000)
"""
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from paeos.model_router.catalog import ModelCatalog
from paeos.model_router.credentials import CredentialStore
from paeos.model_router.router import ModelRouter
from paeos.model_router.server import run_gateway_server
from paeos.model_router.state import RouterStateDB
from tests.model_router.test_routing_policy import MockTransport


@pytest.fixture
def running_server(tmp_path: Path):
    db_file = tmp_path / "server_test_state.sqlite3"
    state_db = RouterStateDB(db_file)
    catalog = ModelCatalog()
    creds = CredentialStore(tmp_path / "mock.env")
    creds._keys = {
        "GEMINI_API_KEY": "mock-gemini-key",
        "NVIDIA_API_KEY": "mock-nvidia-key",
        "KILO_API_KEY": "mock-kilo-key",
        "OPENROUTER_API_KEY": "mock-openrouter-key",
    }
    transport = MockTransport(creds)
    router = ModelRouter(
        credentials=creds,
        catalog=catalog,
        state_db=state_db,
        transport=transport,
    )

    test_port = 4098
    server = run_gateway_server(
        host="127.0.0.1",
        port=test_port,
        router=router,
        api_key="test-secret-token",
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)

    yield f"http://127.0.0.1:{test_port}", router, transport

    server.shutdown()
    server.server_close()


def test_gateway_bearer_auth_rejection(running_server):
    """Requests without valid Bearer token return 401 Unauthorized."""
    base_url, _router, _transport = running_server

    # Request without Authorization header
    req = urllib.request.Request(f"{base_url}/v1/models")
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 401

    # Request with invalid Bearer token
    req_bad = urllib.request.Request(f"{base_url}/v1/models", headers={"Authorization": "Bearer wrong-token"})
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req_bad)
    assert exc.value.code == 401


def test_gateway_get_models_authenticated(running_server):
    """GET /v1/models with valid Bearer token returns registered models."""
    base_url, _router, _transport = running_server

    req = urllib.request.Request(
        f"{base_url}/v1/models",
        headers={"Authorization": "Bearer test-secret-token"},
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["object"] == "list"
        model_ids = [m["id"] for m in data["data"]]
        assert "paeos-auto" in model_ids
        assert "meta/llama-3.1-8b-instruct" in model_ids


def test_gateway_post_chat_completions_explicit_model(running_server):
    """POST /v1/chat/completions with explicit physical model guarantees exact dispatch."""
    base_url, _router, _transport = running_server

    payload = {
        "model": "meta/llama-3.1-8b-instruct",
        "messages": [{"role": "user", "content": "Ping"}],
        "data_class": "PUBLIC",
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test-secret-token",
        },
    )

    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res = json.loads(resp.read().decode("utf-8"))
        assert res["model"] == "meta/llama-3.1-8b-instruct"
        assert res["provider"] == "nvidia"


def test_gateway_availability_fail_closed(running_server):
    """Requesting an unavailable model returns error (fails closed)."""
    base_url, _router, _transport = running_server

    payload = {
        "model": "z-ai/glm-5.2",  # available=False
        "messages": [{"role": "user", "content": "Ping"}],
        "data_class": "PUBLIC",
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/v1/chat/completions",
        data=data_bytes,
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test-secret-token",
        },
    )

    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code in (502, 500, 404)
