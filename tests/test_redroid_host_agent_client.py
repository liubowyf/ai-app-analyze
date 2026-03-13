from pathlib import Path

import httpx
import pytest

from modules.redroid_remote.host_agent_client import HostAgentError, RedroidHostAgentClient


def test_list_slots_sends_bearer_token_and_returns_items():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers.get("authorization")
        assert request.url.path == "/slots"
        return httpx.Response(200, json={"items": [{"slot_name": "redroid-1", "healthy": True}]})

    transport = httpx.MockTransport(handler)
    client = RedroidHostAgentClient("http://agent.local", token="demo-token", transport=transport)

    result = client.list_slots()

    assert seen["authorization"] == "Bearer demo-token"
    assert result == [{"slot_name": "redroid-1", "healthy": True}]


def test_start_capture_posts_task_id_and_slot_name():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["json"] = request.read().decode("utf-8")
        assert request.url.path == "/captures"
        return httpx.Response(
            200,
            json={"capture_id": "cap-1", "container_ip": "172.17.0.2", "status": "capturing"},
        )

    client = RedroidHostAgentClient("http://agent.local", transport=httpx.MockTransport(handler))

    result = client.start_capture(task_id="task-1", slot_name="redroid-1")

    assert '"task_id": "task-1"' in seen["json"]
    assert '"slot_name": "redroid-1"' in seen["json"]
    assert result["capture_id"] == "cap-1"


def test_download_capture_file_writes_local_path(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/captures/cap-1/files/conn.log"
        return httpx.Response(200, content=b"#separator \\x09\n")

    client = RedroidHostAgentClient("http://agent.local", transport=httpx.MockTransport(handler))
    target = tmp_path / "conn.log"

    saved_path = client.download_capture_file("cap-1", "conn.log", str(target))

    assert saved_path == str(target)
    assert target.read_bytes() == b"#separator \\x09\n"


def test_client_raises_host_agent_error_with_code():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"code": "agent_unreachable", "detail": "service unavailable"})

    client = RedroidHostAgentClient("http://agent.local", transport=httpx.MockTransport(handler))

    with pytest.raises(HostAgentError) as exc_info:
        client.get_health()

    assert exc_info.value.code == "agent_unreachable"
    assert "service unavailable" in str(exc_info.value)


def test_client_requires_base_url():
    with pytest.raises(ValueError, match="REDROID_HOST_AGENT_BASE_URL"):
        RedroidHostAgentClient("")
