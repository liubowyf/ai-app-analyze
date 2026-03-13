"""ADB helpers for redroid remote device control."""
from __future__ import annotations

import subprocess
from pathlib import Path


class RedroidADBClient:
    def __init__(self, serial: str):
        self.serial = serial

    def connect(self, timeout: int = 15) -> bool:
        result = subprocess.run(
            ["adb", "connect", self.serial],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result.returncode == 0

    def _adb(self, *args: str, timeout: int = 30) -> str:
        result = subprocess.run(
            ["adb", "-s", self.serial, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (result.stdout or result.stderr or "").strip()
        if result.returncode != 0:
            raise RuntimeError(output or f"adb command failed: {' '.join(args)}")
        return output

    def install_apk(self, apk_path: str, timeout: int = 600) -> str:
        return self._adb("install", "-r", apk_path, timeout=timeout)

    def start_activity(self, package_name: str, activity_name: str, wait: bool = True) -> str:
        args = ["shell", "am", "start"]
        if wait:
            args.append("-W")
        args.extend(["-n", f"{package_name}/{activity_name}"])
        return self._adb(*args, timeout=60)

    def shell(self, command: str, timeout: int = 30) -> str:
        return self._adb("shell", command, timeout=timeout)

    def pull(self, remote_path: str, local_path: str, timeout: int = 30) -> str:
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        self._adb("pull", remote_path, local_path, timeout=timeout)
        return local_path
