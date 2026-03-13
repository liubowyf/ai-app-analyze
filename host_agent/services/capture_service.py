"""Capture lifecycle helpers for the redroid host agent."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

from host_agent.services.file_service import CaptureFileService


class CaptureService:
    """Manage host-side capture sessions and artifacts."""

    def __init__(self, base_dir: str | None = None):
        resolved_base_dir = (
            base_dir
            or os.getenv("HOST_AGENT_CAPTURE_DIR")
            or "/var/lib/redroid-host-agent"
        )
        self.base_dir = Path(resolved_base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.file_service = CaptureFileService()

    def _capture_dir(self, capture_id: str) -> Path:
        return self.base_dir / capture_id

    def _meta_path(self, capture_id: str) -> Path:
        return self._capture_dir(capture_id) / "meta.json"

    def _write_meta(self, capture_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        capture_dir = self._capture_dir(capture_id)
        capture_dir.mkdir(parents=True, exist_ok=True)
        self._meta_path(capture_id).write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        return payload

    def _read_meta(self, capture_id: str) -> dict[str, Any]:
        meta_path = self._meta_path(capture_id)
        if not meta_path.exists():
            raise FileNotFoundError("capture_not_found")
        return json.loads(meta_path.read_text(encoding="utf-8"))

    def _resolve_zeek_binary(self) -> str:
        candidates = [
            str(os.getenv("HOST_AGENT_ZEEK_BIN") or "").strip(),
            shutil.which("zeek") or "",
            "/usr/local/zeek/bin/zeek",
            "/opt/zeek/bin/zeek",
        ]
        for candidate in candidates:
            if candidate and Path(candidate).exists():
                return candidate
        raise RuntimeError("zeek binary not found")

    def start_capture(self, *, task_id: str, slot_name: str, container_name: str, container_ip: str | None) -> dict[str, Any]:
        capture_id = uuid.uuid4().hex
        capture_dir = self._capture_dir(capture_id)
        capture_dir.mkdir(parents=True, exist_ok=True)
        pcap_path = capture_dir / "capture.pcap"
        text_path = capture_dir / "tcpdump.log"
        zeek_dir = capture_dir / "zeek"
        zeek_dir.mkdir(parents=True, exist_ok=True)

        command = [
            "sh",
            "-lc",
            (
                "tcpdump -i any -w "
                f"{pcap_path} -l -A -n -s 0 "
                f"\"host {container_ip or '0.0.0.0'} and (tcp port 3128 or udp port 53 or tcp port 53 or udp port 443 or tcp port 443)\" "
                f"> {text_path} 2>{capture_dir / 'tcpdump.err'} & echo $!"
            ),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=10)
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "capture_start_failed").strip())
        pid = int((result.stdout or "0").strip() or "0")
        if pid <= 0:
            raise RuntimeError("capture_start_failed")

        payload = {
            "capture_id": capture_id,
            "task_id": task_id,
            "slot_name": slot_name,
            "container_name": container_name,
            "container_ip": container_ip,
            "pcap_path": str(pcap_path),
            "text_path": str(text_path),
            "zeek_dir": str(zeek_dir),
            "pid": pid,
            "status": "capturing",
        }
        return self._write_meta(capture_id, payload)

    def stop_capture(self, capture_id: str) -> dict[str, Any]:
        payload = self._read_meta(capture_id)
        pid = int(payload.get("pid") or 0)
        if pid > 0:
            subprocess.run(
                ["sh", "-lc", f"kill {pid} >/dev/null 2>&1 || true"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        payload["status"] = "stopped"
        return self._write_meta(capture_id, payload)

    def analyze_capture(self, capture_id: str) -> dict[str, Any]:
        payload = self._read_meta(capture_id)
        capture_dir = self._capture_dir(capture_id)
        zeek_dir = Path(str(payload["zeek_dir"]))
        zeek_dir.mkdir(parents=True, exist_ok=True)
        pcap_path = Path(str(payload["pcap_path"]))
        if pcap_path.exists() and pcap_path.stat().st_size > 0:
            zeek_binary = self._resolve_zeek_binary()
            result = subprocess.run(
                [zeek_binary, "-Cr", str(pcap_path)],
                cwd=zeek_dir,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )
            zeek_error_output = (result.stderr or result.stdout or "").strip()
            if zeek_error_output:
                (capture_dir / "zeek.err").write_text(zeek_error_output, encoding="utf-8")
            if result.returncode != 0:
                payload["status"] = "analyze_failed"
                self._write_meta(capture_id, payload)
                raise RuntimeError(zeek_error_output or "zeek analyze failed")
            payload["pcap_exists"] = True
            payload["pcap_size"] = pcap_path.stat().st_size
        else:
            payload["pcap_exists"] = False
            payload["pcap_size"] = 0
        payload["status"] = "analyzed"
        return self._write_meta(capture_id, payload)

    def get_capture(self, capture_id: str) -> dict[str, Any]:
        return self._read_meta(capture_id)

    def list_files(self, capture_id: str) -> list[dict[str, int | str]]:
        return self.file_service.list_allowed_files(self._capture_dir(capture_id))

    def read_file(self, capture_id: str, name: str) -> bytes:
        return self.file_service.read_allowed_file(self._capture_dir(capture_id), name)

    def delete_capture(self, capture_id: str) -> dict[str, Any]:
        capture_dir = self._capture_dir(capture_id)
        if capture_dir.exists():
            for path in sorted(capture_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            capture_dir.rmdir()
        return {"capture_id": capture_id, "status": "deleted"}
