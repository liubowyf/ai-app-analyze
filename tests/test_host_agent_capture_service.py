from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from host_agent.services.capture_service import CaptureService


def test_analyze_capture_raises_when_zeek_binary_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = CaptureService(base_dir=str(tmp_path))
    capture_id = "cap-1"
    capture_dir = tmp_path / capture_id
    capture_dir.mkdir(parents=True, exist_ok=True)
    pcap_path = capture_dir / "capture.pcap"
    pcap_path.write_bytes(b"pcap")

    service._write_meta(
        capture_id,
        {
            "capture_id": capture_id,
            "task_id": "task-1",
            "slot_name": "redroid-1",
            "container_name": "redroid-1",
            "container_ip": "172.17.0.2",
            "pcap_path": str(pcap_path),
            "text_path": str(capture_dir / "tcpdump.log"),
            "zeek_dir": str(capture_dir / "zeek"),
            "status": "stopped",
        },
    )

    monkeypatch.setattr(service, "_resolve_zeek_binary", lambda: (_ for _ in ()).throw(RuntimeError("zeek binary not found")))

    with pytest.raises(RuntimeError, match="zeek binary not found"):
        service.analyze_capture(capture_id)


def test_analyze_capture_runs_zeek_without_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = CaptureService(base_dir=str(tmp_path))
    capture_id = "cap-2"
    capture_dir = tmp_path / capture_id
    capture_dir.mkdir(parents=True, exist_ok=True)
    zeek_dir = capture_dir / "zeek"
    pcap_path = capture_dir / "capture.pcap"
    pcap_path.write_bytes(b"pcap")

    service._write_meta(
        capture_id,
        {
            "capture_id": capture_id,
            "task_id": "task-2",
            "slot_name": "redroid-2",
            "container_name": "redroid-2",
            "container_ip": "172.17.0.4",
            "pcap_path": str(pcap_path),
            "text_path": str(capture_dir / "tcpdump.log"),
            "zeek_dir": str(zeek_dir),
            "status": "stopped",
        },
    )

    seen: dict[str, object] = {}

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(service, "_resolve_zeek_binary", lambda: "/usr/local/zeek/bin/zeek")
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = service.analyze_capture(capture_id)

    assert seen["command"] == ["/usr/local/zeek/bin/zeek", "-Cr", str(pcap_path)]
    assert seen["cwd"] == zeek_dir
    assert result["status"] == "analyzed"
    assert result["pcap_exists"] is True
