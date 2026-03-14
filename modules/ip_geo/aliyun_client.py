"""Aliyun IP geolocation client."""

from __future__ import annotations

import time
import uuid
from typing import Any

import httpx


def extract_location_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract the provider payload regardless of response wrapper shape."""
    if not isinstance(payload, dict):
        return {}
    for key in ("showapi_res_body", "result", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def normalize_aliyun_ip_location(payload: dict[str, Any]) -> str | None:
    """Normalize provider fields into a compact display string."""
    payload = extract_location_payload(payload)
    if not isinstance(payload, dict):
        return None
    country = str(payload.get("country") or payload.get("nation") or "").strip()
    province = str(payload.get("province") or payload.get("region") or payload.get("prov") or "").strip()
    city = str(payload.get("city") or "").strip()
    isp = str(payload.get("operators") or payload.get("isp") or payload.get("operator") or "").strip()

    parts: list[str] = []
    for part in (country, province, city):
        if part and part not in parts:
            parts.append(part)
    if isp and isp not in parts:
        parts.append(isp)
    if not parts:
        return None
    return " ".join(parts)


class AliyunIpGeoClient:
    """Thin wrapper around the Aliyun market IP geolocation API."""

    def __init__(
        self,
        *,
        base_url: str = "https://jmipquery3.market.alicloudapi.com/ip/query-v3",
        appcode: str = "",
        appkey: str = "",
        appsecret: str = "",
        timeout_seconds: int = 8,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.appcode = appcode.strip()
        self.appkey = appkey.strip()
        self.appsecret = appsecret.strip()
        self.timeout_seconds = max(1, int(timeout_seconds))

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }
        return headers

    def lookup_ip(self, ip: str) -> str | None:
        with httpx.Client(timeout=self.timeout_seconds, trust_env=False, verify=False) as client:
            response = client.post(
                self.base_url,
                json={"ip": ip},
                headers={
                    **self._build_headers(),
                    "Content-Type": "application/json",
                    "Nonce": str(uuid.uuid4()),
                    "Timestamp": str(int(time.time() * 1000)),
                },
            )
            response.raise_for_status()
            payload = extract_location_payload(response.json())
            return normalize_aliyun_ip_location(payload)
