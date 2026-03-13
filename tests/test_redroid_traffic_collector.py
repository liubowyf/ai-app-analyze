from modules.redroid_remote.traffic_collector import RedroidTrafficCollector


class FakeSSH:
    def __init__(self):
        self.exec_calls = []
        self.password = "secret"

    def exec(self, command: str, timeout: int = 30):
        self.exec_calls.append((command, timeout))
        if "docker inspect" in command:
            return "172.17.0.2\n"
        if "stat -c '%s'" in command and "task-123-redroid-app.pcap" in command:
            return "missing\n"
        if "tcpdump" in command and "echo $!" in command:
            return "4321\n"
        if "zeek" in command:
            return ""
        return ""


def test_resolve_container_ip_uses_docker_inspect():
    collector = RedroidTrafficCollector(ssh_client=FakeSSH(), container_name="redroid-1")

    ip = collector.resolve_container_ip()

    assert ip == "172.17.0.2"
    assert collector.ssh_client.exec_calls[0][0] == (
        "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' redroid-1"
    )


def test_start_capture_builds_tcpdump_command_with_dynamic_container_ip_and_returns_metadata():
    ssh = FakeSSH()
    collector = RedroidTrafficCollector(ssh_client=ssh, container_name="redroid-1")

    capture = collector.start_capture(task_id="task-123")

    assert capture["container_ip"] == "172.17.0.2"
    assert capture["pcap_path"].endswith("task-123-redroid-app.pcap")
    assert capture["text_path"].endswith("task-123-redroid-app.log")
    assert capture["pid"] == 4321
    tcpdump_call = ssh.exec_calls[1][0]
    assert "sudo -S tcpdump -i any -l -A -n -s 0" in tcpdump_call
    assert "secret" in tcpdump_call
    assert "host 172.17.0.2" in tcpdump_call
    assert "echo $!" in tcpdump_call


def test_run_zeek_skips_when_pcap_missing():
    ssh = FakeSSH()
    collector = RedroidTrafficCollector(ssh_client=ssh, container_name="redroid-1")
    capture = {
        "pcap_path": "/tmp/task-123-redroid-app.pcap",
        "zeek_dir": "/tmp/zeek-task-123",
    }

    result = collector.run_zeek(capture)

    assert result["zeek_dir"] == "/tmp/zeek-task-123"
    assert result["pcap_exists"] is False
    assert result["pcap_size"] == 0
    assert all("zeek -Cr" not in call[0] for call in ssh.exec_calls)
