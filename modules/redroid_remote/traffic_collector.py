"""Host-agent capture orchestration for redroid backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from modules.redroid_remote.host_agent_client import RedroidHostAgentClient


@dataclass(slots=True)
class RedroidTrafficCollector:
    """Manage pcap collection and Zeek parsing through the host agent."""

    host_agent_client: RedroidHostAgentClient | Any
    slot_name: str | None = None
    container_name: str = "redroid-1"

    def _find_slot(self) -> dict[str, Any]:
        slots = self.host_agent_client.list_slots()
        for slot in slots:
            slot_name = str(slot.get("slot_name") or "").strip()
            container_name = str(slot.get("container_name") or "").strip()
            if self.slot_name and slot_name == self.slot_name:
                return slot
            if container_name and container_name == self.container_name:
                return slot
        raise RuntimeError(f"Failed to resolve redroid slot for container {self.container_name}")

    def resolve_container_ip(self) -> str:
        slot = self._find_slot()
        ip = str(slot.get("container_ip") or "").strip()
        if not ip:
            raise RuntimeError(f"Failed to resolve container IP for {self.container_name}")
        return ip

    def start_capture(self, task_id: str) -> Dict[str, Any]:
        slot = self._find_slot()
        slot_name = str(slot.get("slot_name") or self.slot_name or "").strip()
        if not slot_name:
            raise RuntimeError(f"Failed to resolve redroid slot name for {self.container_name}")
        capture = self.host_agent_client.start_capture(task_id=task_id, slot_name=slot_name)
        capture.setdefault("container_ip", slot.get("container_ip"))
        capture.setdefault("slot_name", slot_name)
        return capture

    def stop_capture(self, capture: Dict[str, Any]) -> None:
        capture_id = str(capture.get("capture_id") or "").strip()
        if not capture_id:
            return
        self.host_agent_client.stop_capture(capture_id)

    def run_zeek(self, capture: Dict[str, Any]) -> Dict[str, Any]:
        capture_id = str(capture.get("capture_id") or "").strip()
        if not capture_id:
            raise RuntimeError("capture_id is required to analyze capture")
        result = self.host_agent_client.analyze_capture(capture_id)
        result.setdefault("pcap_path", capture.get("pcap_path"))
        result.setdefault("zeek_dir", capture.get("zeek_dir"))
        return result
