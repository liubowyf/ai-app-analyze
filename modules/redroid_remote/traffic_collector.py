"""Remote host tcpdump orchestration for redroid backend."""

from __future__ import annotations

from dataclasses import dataclass
import shlex
from typing import Any, Dict


def _stdout_or_raise(result: Any, *, command: str) -> str:
    """Normalize ssh client exec output across fake/test and real clients."""
    if isinstance(result, str):
        return result.strip()
    returncode = getattr(result, "returncode", 0)
    stdout = str(getattr(result, "stdout", "") or "").strip()
    stderr = str(getattr(result, "stderr", "") or "").strip()
    if int(returncode or 0) != 0:
        raise RuntimeError(stderr or stdout or f"SSH command failed: {command}")
    return stdout


@dataclass(slots=True)
class RedroidTrafficCollector:
    """Manage pcap collection and Zeek parsing on the redroid host."""

    ssh_client: Any
    container_name: str = "redroid-1"
    tcpdump_interface: str = "any"
    zeek_binary: str = "/opt/zeek/bin/zeek"

    def _sudo_prefix(self) -> str:
        password = getattr(self.ssh_client, "password", None)
        if password:
            quoted_password = shlex.quote(password)
            return f"printf '%s\\n' {quoted_password} | sudo -S"
        return "sudo -n"

    def _remote_file_info(self, path: str) -> dict[str, Any]:
        command = (
            "sh -lc "
            + shlex.quote(
                f"if [ -f {shlex.quote(path)} ]; then stat -c '%s' {shlex.quote(path)}; else echo missing; fi"
            )
        )
        output = _stdout_or_raise(self.ssh_client.exec(command), command=command)
        cleaned = (output or "").strip()
        if cleaned == "missing":
            return {"exists": False, "size": 0}
        try:
            return {"exists": True, "size": int(cleaned or "0")}
        except ValueError:
            return {"exists": True, "size": 0}

    def resolve_container_ip(self) -> str:
        command = (
            f"docker inspect -f '{{{{range .NetworkSettings.Networks}}}}{{{{.IPAddress}}}}{{{{end}}}}' "
            f"{self.container_name}"
        )
        output = _stdout_or_raise(self.ssh_client.exec(command), command=command)
        ip = (output or "").strip()
        if not ip:
            raise RuntimeError(f"Failed to resolve container IP for {self.container_name}")
        return ip

    def start_capture(self, task_id: str) -> Dict[str, Any]:
        container_ip = self.resolve_container_ip()
        pcap_path = f"/tmp/{task_id}-redroid-app.pcap"
        text_path = f"/tmp/{task_id}-redroid-app.log"
        zeek_dir = f"/tmp/zeek-{task_id}"
        tcpdump_expr = (
            f"host {container_ip} and (tcp port 3128 or udp port 53 or tcp port 53 or udp port 443 or tcp port 443)"
        )
        tcpdump_cmd = (
            f"{self._sudo_prefix()} tcpdump "
            f"-i {self.tcpdump_interface} -l -A -n -s 0 {shlex.quote(tcpdump_expr)} "
            f"> {shlex.quote(text_path)} 2>/tmp/{task_id}-tcpdump.err & echo $!"
        )
        command = f"sh -lc {shlex.quote(tcpdump_cmd)}"
        pid_output = _stdout_or_raise(self.ssh_client.exec(command), command=command)
        pid = int((pid_output or "0").strip() or "0")
        capture = {
            "task_id": task_id,
            "container_ip": container_ip,
            "pcap_path": pcap_path,
            "text_path": text_path,
            "zeek_dir": zeek_dir,
            "pid": pid,
        }
        if pid <= 0:
            raise RuntimeError("Failed to start remote tcpdump capture")
        return capture

    def stop_capture(self, capture: Dict[str, Any]) -> None:
        pid = int(capture.get("pid") or 0)
        if pid <= 0:
            return
        self.ssh_client.exec(f"sh -lc 'kill {pid} >/dev/null 2>&1 || true'")

    def run_zeek(self, capture: Dict[str, Any]) -> Dict[str, Any]:
        pcap_path = str(capture["pcap_path"])
        zeek_dir = str(capture["zeek_dir"])
        file_info = self._remote_file_info(pcap_path)
        if not file_info["exists"] or int(file_info["size"] or 0) <= 0:
            return {
                "pcap_path": pcap_path,
                "zeek_dir": zeek_dir,
                "pcap_exists": False,
                "pcap_size": 0,
            }
        command = (
            f"sh -lc 'mkdir -p {zeek_dir} && cd {zeek_dir} && {self.zeek_binary} -Cr {pcap_path}'"
        )
        _stdout_or_raise(self.ssh_client.exec(command), command=command)
        return {
            "pcap_path": pcap_path,
            "zeek_dir": zeek_dir,
            "pcap_exists": True,
            "pcap_size": int(file_info["size"] or 0),
        }
