"""Traffic attribution helpers for package/uid/process/source metadata."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class AttributionResult:
    """Attribution output for one request."""

    package_name: Optional[str]
    uid: Optional[int]
    process_name: Optional[str]
    source: str
    confidence: float


class AttributionEngine:
    """Best-effort attribution from Android runtime context and headers."""

    def __init__(
        self,
        emulator_host: Optional[str],
        emulator_port: Optional[int],
        android_runner: Optional[Any],
        target_package: Optional[str],
    ):
        self.emulator_host = emulator_host
        self.emulator_port = emulator_port
        self.android_runner = android_runner
        self.target_package = target_package
        self._package_uid_map: Dict[str, int] = {}
        self._process_uid_map: Dict[str, int] = {}
        self._last_refresh_at = 0.0
        self._refresh_ttl = 5.0

    def _execute(self, cmd: str) -> str:
        if not self.android_runner or not self.emulator_host or not self.emulator_port:
            return ""
        runner_exec = getattr(self.android_runner, "execute_adb_remote", None)
        if not callable(runner_exec):
            return ""
        return runner_exec(self.emulator_host, self.emulator_port, cmd) or ""

    def refresh_maps(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and (now - self._last_refresh_at) < self._refresh_ttl:
            return

        pm_output = self._execute("shell pm list packages -U")
        package_uid_map: Dict[str, int] = {}
        for line in pm_output.splitlines():
            line = line.strip()
            if not line.startswith("package:"):
                continue
            m = re.search(r"package:([^\s]+)\s+uid:(\d+)", line)
            if not m:
                continue
            package_uid_map[m.group(1)] = int(m.group(2))

        ps_output = self._execute("shell ps -A")
        process_uid_map: Dict[str, int] = {}
        for line in ps_output.splitlines():
            cols = line.split()
            if len(cols) < 2:
                continue
            process = cols[-1]
            user = cols[0]
            uid = None
            m = re.search(r"u0_a(\d+)", user)
            if m:
                uid = 10000 + int(m.group(1))
            elif user.isdigit():
                uid = int(user)
            if uid is not None:
                process_uid_map[process] = uid

        self._package_uid_map = package_uid_map
        self._process_uid_map = process_uid_map
        self._last_refresh_at = now

    @staticmethod
    def _infer_source(headers: Dict[str, str]) -> str:
        headers_l = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
        ua = headers_l.get("user-agent", "").lower()
        if "okhttp" in ua:
            return "okhttp"
        if " wv" in ua or "webview" in ua:
            return "webview"
        if "android" in ua:
            return "system"
        return "unknown"

    def _foreground_package(self) -> str:
        if not self.android_runner or not self.emulator_host or not self.emulator_port:
            return ""
        getter = getattr(self.android_runner, "get_current_package", None)
        if not callable(getter):
            return ""
        try:
            return (getter(self.emulator_host, self.emulator_port) or "").strip()
        except Exception:
            return ""

    def enrich(self, request_data: Dict[str, Any]) -> AttributionResult:
        self.refresh_maps()
        headers = request_data.get("request_headers") or {}
        source = self._infer_source(headers)

        requested_with = headers.get("X-Requested-With") or headers.get("x-requested-with")
        package_name = None
        confidence = 0.2

        if requested_with:
            package_name = str(requested_with).strip()
            confidence = 0.95
        else:
            foreground_pkg = self._foreground_package()
            if foreground_pkg:
                package_name = foreground_pkg
                confidence = 0.7
            elif self.target_package:
                package_name = self.target_package
                confidence = 0.5

        if not package_name and self.target_package:
            package_name = self.target_package
            confidence = 0.4

        uid = self._package_uid_map.get(package_name or "")
        process_name = package_name
        if package_name and process_name not in self._process_uid_map and uid is None:
            # fallback by package prefix search in process map
            for proc_name, proc_uid in self._process_uid_map.items():
                if proc_name.startswith(package_name):
                    process_name = proc_name
                    uid = proc_uid
                    break

        return AttributionResult(
            package_name=package_name,
            uid=uid,
            process_name=process_name,
            source=source,
            confidence=confidence,
        )
