"""HTTP client for the redroid host agent service."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


@dataclass(frozen=True)
class HostAgentError(RuntimeError):
    """Raised when the redroid host agent returns an error."""

    message: str
    code: str | None = None
    status_code: int | None = None

    def __str__(self) -> str:
        return self.message


class RedroidHostAgentClient:
    """Minimal synchronous client for host-agent control plane calls."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str | None = None,
        timeout: int = 15,
        transport: httpx.BaseTransport | None = None,
    ):
        cleaned = str(base_url or "").strip().rstrip("/")
        if not cleaned:
            raise ValueError("REDROID_HOST_AGENT_BASE_URL is required")
        self.base_url = cleaned
        self.timeout = max(1, int(timeout or 15))
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=headers,
            transport=transport,
            trust_env=False,
        )

    def _raise_for_response(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        code: str | None = None
        detail: Any = None
        try:
            payload = response.json()
        except Exception:
            payload = None
        if isinstance(payload, dict):
            code = str(payload.get("code") or "").strip() or None
            detail = payload.get("detail") or payload.get("message")
        message = str(detail or response.text or f"Host agent request failed: {response.status_code}").strip()
        raise HostAgentError(message=message, code=code, status_code=response.status_code)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise HostAgentError(message=f"Host agent unavailable: {exc}", code="agent_unreachable") from exc

        self._raise_for_response(response)
        if not response.content:
            return None
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.content

    def get_health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def list_slots(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/slots")
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            return payload["items"]
        if isinstance(payload, list):
            return payload
        raise HostAgentError(message="Invalid host agent slots payload", code="invalid_slots_payload")

    def start_capture(self, *, task_id: str, slot_name: str) -> dict[str, Any]:
        payload = {"task_id": task_id, "slot_name": slot_name}
        result = self._request("POST", "/captures", json=payload)
        if not isinstance(result, dict):
            raise HostAgentError(message="Invalid start_capture payload", code="invalid_capture_payload")
        return result

    def stop_capture(self, capture_id: str) -> dict[str, Any]:
        result = self._request("POST", f"/captures/{capture_id}/stop")
        return result if isinstance(result, dict) else {}

    def analyze_capture(self, capture_id: str) -> dict[str, Any]:
        result = self._request("POST", f"/captures/{capture_id}/analyze")
        if not isinstance(result, dict):
            raise HostAgentError(message="Invalid analyze_capture payload", code="invalid_capture_payload")
        return result

    def get_capture(self, capture_id: str) -> dict[str, Any]:
        result = self._request("GET", f"/captures/{capture_id}")
        if not isinstance(result, dict):
            raise HostAgentError(message="Invalid capture payload", code="invalid_capture_payload")
        return result

    def list_capture_files(self, capture_id: str) -> list[dict[str, Any]]:
        result = self._request("GET", f"/captures/{capture_id}/files")
        if isinstance(result, dict) and isinstance(result.get("items"), list):
            return result["items"]
        if isinstance(result, list):
            return result
        raise HostAgentError(message="Invalid capture files payload", code="invalid_capture_files_payload")

    def download_capture_file(self, capture_id: str, name: str, local_path: str) -> str:
        raw = self._request("GET", f"/captures/{capture_id}/files/{name}")
        if not isinstance(raw, (bytes, bytearray)):
            raise HostAgentError(message="Invalid capture file payload", code="invalid_capture_file_payload")
        target = Path(local_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(raw))
        return str(target)

    def delete_capture(self, capture_id: str) -> None:
        self._request("DELETE", f"/captures/{capture_id}")
