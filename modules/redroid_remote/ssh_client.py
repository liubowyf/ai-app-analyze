"""SSH helpers for redroid remote host operations."""
from __future__ import annotations

from dataclasses import dataclass
import os
import subprocess
from pathlib import Path


@dataclass(frozen=True)
class SSHCommandResult:
    returncode: int
    stdout: str
    stderr: str


class RedroidSSHClient:
    def __init__(
        self,
        host: str,
        user: str,
        port: int = 22,
        key_path: str | None = None,
        password: str | None = None,
    ):
        self.host = host
        self.user = user
        self.port = int(port)
        self.key_path = key_path
        self.password = password

    def _ssh_prefix(self) -> list[str]:
        cmd: list[str] = []
        if self.password:
            cmd.extend(["sshpass", "-e"])
        cmd.extend(["ssh", "-p", str(self.port)])
        if self.key_path:
            cmd.extend(["-i", self.key_path])
        cmd.extend(["-o", f"BatchMode={'no' if self.password else 'yes'}", "-o", "StrictHostKeyChecking=no"])
        cmd.append(f"{self.user}@{self.host}")
        return cmd

    def _scp_prefix(self) -> list[str]:
        cmd: list[str] = []
        if self.password:
            cmd.extend(["sshpass", "-e"])
        cmd.extend(["scp", "-P", str(self.port)])
        if self.key_path:
            cmd.extend(["-i", self.key_path])
        cmd.extend(["-o", f"BatchMode={'no' if self.password else 'yes'}", "-o", "StrictHostKeyChecking=no"])
        return cmd

    def exec(self, command: str, timeout: int = 30) -> SSHCommandResult:
        env = os.environ.copy()
        if self.password:
            env["SSHPASS"] = self.password
        result = subprocess.run(
            [*self._ssh_prefix(), command],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        return SSHCommandResult(
            returncode=int(result.returncode),
            stdout=(result.stdout or "").strip(),
            stderr=(result.stderr or "").strip(),
        )

    def get_container_ip(self, container_name: str) -> str:
        template = "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"
        result = self.exec(f"docker inspect -f '{template}' {container_name}", timeout=15)
        if result.returncode != 0 or not result.stdout:
            raise RuntimeError(f"Failed to resolve container IP for {container_name}: {result.stderr or result.stdout}")
        return result.stdout

    def fetch_file(self, remote_path: str, local_path: str, timeout: int = 30) -> str:
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        if self.password:
            env["SSHPASS"] = self.password
        result = subprocess.run(
            [*self._scp_prefix(), f"{self.user}@{self.host}:{remote_path}", local_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "scp failed").strip())
        return local_path
