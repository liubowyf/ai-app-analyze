from modules.redroid_remote.traffic_collector import RedroidTrafficCollector


class FakeHostAgentClient:
    def __init__(self):
        self.calls = []

    def list_slots(self):
        self.calls.append(("list_slots",))
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

    def start_capture(self, task_id: str, slot_name: str):
        self.calls.append(("start_capture", task_id, slot_name))
        return {
            "capture_id": "cap-123",
            "task_id": task_id,
            "slot_name": slot_name,
            "container_ip": "172.17.0.2",
            "pcap_path": "/tmp/task-123-redroid-app.pcap",
            "text_path": "/tmp/task-123-redroid-app.log",
            "status": "running",
        }

    def stop_capture(self, capture_id: str):
        self.calls.append(("stop_capture", capture_id))
        return {"capture_id": capture_id, "status": "stopped"}

    def analyze_capture(self, capture_id: str):
        self.calls.append(("analyze_capture", capture_id))
        return {
            "capture_id": capture_id,
            "status": "analyzed",
            "pcap_path": "/tmp/task-123-redroid-app.pcap",
            "zeek_dir": "/tmp/zeek-task-123",
            "pcap_exists": False,
            "pcap_size": 0,
        }


def test_resolve_container_ip_uses_slot_listing():
    client = FakeHostAgentClient()
    collector = RedroidTrafficCollector(host_agent_client=client, slot_name="redroid-1", container_name="redroid-1")

    ip = collector.resolve_container_ip()

    assert ip == "172.17.0.2"
    assert client.calls == [("list_slots",)]


def test_start_capture_delegates_to_host_agent_and_returns_metadata():
    client = FakeHostAgentClient()
    collector = RedroidTrafficCollector(host_agent_client=client, slot_name="redroid-1", container_name="redroid-1")

    capture = collector.start_capture(task_id="task-123")

    assert capture["container_ip"] == "172.17.0.2"
    assert capture["pcap_path"].endswith("task-123-redroid-app.pcap")
    assert capture["text_path"].endswith("task-123-redroid-app.log")
    assert capture["capture_id"] == "cap-123"
    assert client.calls == [
        ("list_slots",),
        ("start_capture", "task-123", "redroid-1"),
    ]


def test_run_zeek_calls_host_agent_and_returns_metadata():
    client = FakeHostAgentClient()
    collector = RedroidTrafficCollector(host_agent_client=client, slot_name="redroid-1", container_name="redroid-1")
    capture = {
        "capture_id": "cap-123",
        "pcap_path": "/tmp/task-123-redroid-app.pcap",
        "zeek_dir": "/tmp/zeek-task-123",
    }

    result = collector.run_zeek(capture)

    assert result["zeek_dir"] == "/tmp/zeek-task-123"
    assert result["pcap_exists"] is False
    assert result["pcap_size"] == 0
    assert ("analyze_capture", "cap-123") in client.calls
