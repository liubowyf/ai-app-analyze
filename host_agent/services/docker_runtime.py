"""Docker runtime helpers for slot inspection."""

from __future__ import annotations

import json
import subprocess
from typing import Any


class DockerRuntime:
    """Minimal docker inspect wrapper for host-agent slots."""

    def inspect_container(self, container_name: str) -> dict[str, Any]:
        result = subprocess.run(
            ["docker", "inspect", container_name],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            return {
                "healthy": False,
                "container_ip": None,
                "detail": (result.stderr or result.stdout or "docker inspect failed").strip(),
            }
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError:
            return {"healthy": False, "container_ip": None, "detail": "invalid docker inspect payload"}
        if not payload:
            return {"healthy": False, "container_ip": None, "detail": "container not found"}
        item = payload[0]
        state = item.get("State") or {}
        networks = (item.get("NetworkSettings") or {}).get("Networks") or {}
        container_ip = None
        for network in networks.values():
            container_ip = network.get("IPAddress")
            if container_ip:
                break
        return {
            "healthy": bool(state.get("Running", False)),
            "container_ip": container_ip,
            "detail": None if state.get("Running", False) else "container_not_running",
        }

    def list_slots(self, slots: list[dict[str, str]]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for slot in slots:
            inspection = self.inspect_container(str(slot.get("container_name") or ""))
            items.append(
                {
                    "slot_name": str(slot.get("name") or ""),
                    "container_name": str(slot.get("container_name") or ""),
                    "adb_serial": str(slot.get("adb_serial") or ""),
                    "healthy": bool(inspection.get("healthy", False)),
                    "container_ip": inspection.get("container_ip"),
                    "detail": inspection.get("detail"),
                }
            )
        return items
