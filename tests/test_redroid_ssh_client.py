from pathlib import Path

import pytest


from modules.redroid_remote.ssh_client import RedroidSSHClient, SSHCommandResult


class FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_exec_builds_ssh_command_with_port_user_and_key(monkeypatch, tmp_path):
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("dummy")
    calls = []

    def fake_run(cmd, capture_output, text, timeout, check, env=None):
        calls.append({
            "cmd": cmd,
            "capture_output": capture_output,
            "text": text,
            "timeout": timeout,
            "check": check,
            "env": env,
        })
        return FakeCompletedProcess(stdout="ok\n")

    monkeypatch.setattr("modules.redroid_remote.ssh_client.subprocess.run", fake_run)

    client = RedroidSSHClient(host="61.152.73.88", port=22, user="dd", key_path=str(key_path))
    result = client.exec("docker ps")

    assert result == SSHCommandResult(returncode=0, stdout="ok", stderr="")
    assert calls[0]["cmd"] == [
        "ssh",
        "-p",
        "22",
        "-i",
        str(key_path),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "dd@61.152.73.88",
        "docker ps",
    ]
    assert calls[0]["capture_output"] is True
    assert calls[0]["text"] is True
    assert calls[0]["timeout"] == 30
    assert calls[0]["check"] is False


def test_exec_returns_stderr_and_nonzero_code(monkeypatch):
    monkeypatch.setattr(
        "modules.redroid_remote.ssh_client.subprocess.run",
        lambda *args, **kwargs: FakeCompletedProcess(returncode=1, stderr="boom\n"),
    )

    client = RedroidSSHClient(host="61.152.73.88", user="dd")
    result = client.exec("bad cmd", timeout=5)

    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr == "boom"


def test_docker_inspect_redroid_ip_uses_expected_template(monkeypatch):
    seen = {}

    def fake_exec(self, command, timeout=30):
        seen["command"] = command
        seen["timeout"] = timeout
        return SSHCommandResult(returncode=0, stdout="172.17.0.2", stderr="")

    monkeypatch.setattr(RedroidSSHClient, "exec", fake_exec)

    client = RedroidSSHClient(host="61.152.73.88", user="dd")
    ip = client.get_container_ip("redroid-1")

    assert ip == "172.17.0.2"
    assert seen["command"] == "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' redroid-1"
    assert seen["timeout"] == 15


def test_scp_fetch_builds_copy_command(monkeypatch, tmp_path):
    key_path = tmp_path / "id_ed25519"
    key_path.write_text("dummy")
    local_path = tmp_path / "conn.log"
    calls = []

    def fake_run(cmd, capture_output, text, timeout, check, env=None):
        calls.append(cmd)
        return FakeCompletedProcess(stdout="")

    monkeypatch.setattr("modules.redroid_remote.ssh_client.subprocess.run", fake_run)

    client = RedroidSSHClient(host="61.152.73.88", port=2222, user="dd", key_path=str(key_path))
    client.fetch_file("/tmp/conn.log", str(local_path), timeout=40)

    assert calls[0] == [
        "scp",
        "-P",
        "2222",
        "-i",
        str(key_path),
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=no",
        "dd@61.152.73.88:/tmp/conn.log",
        str(local_path),
    ]


def test_exec_supports_ssh_password_via_sshpass(monkeypatch):
    calls = []

    def fake_run(cmd, capture_output, text, timeout, check, env=None):
        calls.append({"cmd": cmd, "env": env})
        return FakeCompletedProcess(stdout="ok\n")

    monkeypatch.setattr("modules.redroid_remote.ssh_client.subprocess.run", fake_run)

    client = RedroidSSHClient(host="61.152.73.88", user="user", password="secret")
    result = client.exec("echo ok")

    assert result == SSHCommandResult(returncode=0, stdout="ok", stderr="")
    assert calls[0]["cmd"][:2] == ["sshpass", "-e"]
    assert calls[0]["cmd"][2:] == [
        "ssh",
        "-p",
        "22",
        "-o",
        "BatchMode=no",
        "-o",
        "StrictHostKeyChecking=no",
        "user@61.152.73.88",
        "echo ok",
    ]
    assert calls[0]["env"]["SSHPASS"] == "secret"
