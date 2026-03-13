from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from core.config import settings
from host_agent.app import app
from host_agent.routers import captures as captures_router
from host_agent.routers import slots as slots_router


class FakeDockerRuntime:
    def list_slots(self, slots):
        return [
            {
                "slot_name": "redroid-1",
                "container_name": "redroid-1",
                "adb_serial": "<host-agent-node>:16555",
                "healthy": True,
                "container_ip": "172.17.0.2",
                "detail": None,
            }
        ]


class FakeCaptureService:
    def __init__(self):
        self.base_dir = Path("/tmp/redroid-host-agent-tests")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def start_capture(self, *, task_id, slot_name, container_name, container_ip):
        capture_id = "cap-1"
        capture_dir = self.base_dir / capture_id
        capture_dir.mkdir(parents=True, exist_ok=True)
        zeek_dir = capture_dir / "zeek"
        zeek_dir.mkdir(parents=True, exist_ok=True)
        (zeek_dir / "conn.log").write_text("#separator \\x09\n", encoding="utf-8")
        (capture_dir / "tcpdump.log").write_text("tcpdump output\n", encoding="utf-8")
        return {
            "capture_id": capture_id,
            "task_id": task_id,
            "slot_name": slot_name,
            "container_name": container_name,
            "container_ip": container_ip,
            "pcap_path": str(capture_dir / "capture.pcap"),
            "text_path": str(capture_dir / "tcpdump.log"),
            "zeek_dir": str(capture_dir / "zeek"),
            "status": "capturing",
        }

    def stop_capture(self, capture_id):
        return {"capture_id": capture_id, "status": "stopped"}

    def analyze_capture(self, capture_id):
        return {
            "capture_id": capture_id,
            "status": "analyzed",
            "pcap_path": f"/tmp/{capture_id}/capture.pcap",
            "zeek_dir": f"/tmp/{capture_id}/zeek",
            "pcap_exists": False,
            "pcap_size": 0,
        }

    def get_capture(self, capture_id):
        return {"capture_id": capture_id, "status": "capturing"}

    def list_files(self, capture_id):
        return [{"name": "conn.log", "size": 14}]

    def read_file(self, capture_id, name):
        if name == "tcpdump.log":
            return b"tcpdump output\n"
        return b"#separator \\x09\n"

    def delete_capture(self, capture_id):
        return {"capture_id": capture_id, "status": "deleted"}


def _client():
    app.dependency_overrides[slots_router.get_docker_runtime] = lambda: FakeDockerRuntime()
    app.dependency_overrides[captures_router.get_docker_runtime] = lambda: FakeDockerRuntime()
    app.dependency_overrides[captures_router.get_capture_service] = lambda: FakeCaptureService()
    headers = {}
    token = str(settings.REDROID_HOST_AGENT_TOKEN or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return TestClient(app, headers=headers)


def test_health_returns_ok():
    client = _client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_slots_returns_runtime_slot_payload():
    client = _client()

    response = client.get("/slots")

    assert response.status_code == 200
    data = response.json()
    assert data["items"][0]["slot_name"] == "redroid-1"
    assert data["items"][0]["healthy"] is True


def test_create_stop_analyze_and_list_capture_files():
    client = _client()

    create_response = client.post("/captures", json={"task_id": "task-1", "slot_name": "redroid-1"})
    assert create_response.status_code == 200
    capture_id = create_response.json()["capture_id"]

    stop_response = client.post(f"/captures/{capture_id}/stop")
    assert stop_response.status_code == 200
    assert stop_response.json()["status"] == "stopped"

    analyze_response = client.post(f"/captures/{capture_id}/analyze")
    assert analyze_response.status_code == 200
    assert analyze_response.json()["status"] == "analyzed"

    files_response = client.get(f"/captures/{capture_id}/files")
    assert files_response.status_code == 200
    assert files_response.json()["items"][0]["name"] == "conn.log"


def test_download_capture_file_returns_binary_content():
    client = _client()

    response = client.get("/captures/cap-1/files/conn.log")

    assert response.status_code == 200
    assert response.content == b"#separator \\x09\n"


def test_download_tcpdump_file_returns_root_artifact_content():
    client = _client()

    response = client.get("/captures/cap-1/files/tcpdump.log")

    assert response.status_code == 200
    assert response.content == b"tcpdump output\n"


def test_analyze_capture_returns_500_when_zeek_analysis_fails():
    class FailingCaptureService(FakeCaptureService):
        def analyze_capture(self, capture_id):
            raise RuntimeError("zeek binary not found")

    app.dependency_overrides[slots_router.get_docker_runtime] = lambda: FakeDockerRuntime()
    app.dependency_overrides[captures_router.get_docker_runtime] = lambda: FakeDockerRuntime()
    app.dependency_overrides[captures_router.get_capture_service] = lambda: FailingCaptureService()

    headers = {}
    token = str(settings.REDROID_HOST_AGENT_TOKEN or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    client = TestClient(app, headers=headers)

    response = client.post("/captures/cap-1/analyze")

    assert response.status_code == 500
    assert response.json()["detail"] == "zeek binary not found"
