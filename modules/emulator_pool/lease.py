"""Redis-backed emulator lease manager for cross-worker concurrency safety."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

import redis

from core.config import settings

logger = logging.getLogger(__name__)


def build_emulator_candidates() -> List[Dict[str, int | str]]:
    """Build emulator list in preferred order from settings."""
    preferred = [
        settings.ANDROID_EMULATOR_4,
        settings.ANDROID_EMULATOR_1,
        settings.ANDROID_EMULATOR_2,
        settings.ANDROID_EMULATOR_3,
    ]
    seen = set()
    rows: List[Dict[str, int | str]] = []
    for item in preferred:
        if not item or ":" not in item or item in seen:
            continue
        seen.add(item)
        host, port_raw = item.rsplit(":", 1)
        try:
            port = int(port_raw)
        except ValueError:
            logger.warning("Skip invalid emulator address: %s", item)
            continue
        rows.append({"host": host.strip(), "port": port})
    return rows


class EmulatorLeaseManager:
    """Manage emulator leases via Redis to support multi-process workers."""

    def __init__(
        self,
        redis_url: Optional[str] = None,
        lease_ttl_seconds: int = 3600,
        key_prefix: str = "apk:emulator:lease:",
    ):
        self.redis_url = redis_url or settings.CELERY_BROKER_URL
        self.lease_ttl_seconds = max(60, min(int(lease_ttl_seconds), 12 * 3600))
        self.key_prefix = key_prefix
        self._client: Optional[redis.Redis] = None

    @staticmethod
    def _is_redis_url(url: str) -> bool:
        return isinstance(url, str) and url.startswith("redis://")

    def _get_client(self) -> Optional[redis.Redis]:
        if self._client is not None:
            return self._client
        if not self._is_redis_url(self.redis_url):
            return None
        try:
            self._client = redis.from_url(self.redis_url, decode_responses=True)
            self._client.ping()
            return self._client
        except Exception as exc:
            logger.warning("Redis lease manager unavailable: %s", exc)
            self._client = None
            return None

    def _lease_key(self, host: str, port: int) -> str:
        return f"{self.key_prefix}{host}:{port}"

    def acquire(
        self,
        task_id: str,
        candidates: Optional[List[Dict[str, int | str]]] = None,
    ) -> Optional[Dict[str, str | int]]:
        """Acquire one emulator lease. Returns None if no slot available."""
        client = self._get_client()
        if client is None:
            return None

        pool = candidates or build_emulator_candidates()
        if not pool:
            return None

        for item in pool:
            host = str(item["host"])
            port = int(item["port"])
            key = self._lease_key(host, port)
            lease_token = uuid.uuid4().hex
            payload = {
                "task_id": task_id,
                "lease_token": lease_token,
                "leased_at": datetime.now(timezone.utc).isoformat(),
                "pid": os.getpid(),
            }
            try:
                ok = client.set(key, json.dumps(payload, ensure_ascii=False), nx=True, ex=self.lease_ttl_seconds)
            except Exception as exc:
                logger.warning("Failed to acquire emulator lease key=%s: %s", key, exc)
                continue
            if ok:
                return {
                    "host": host,
                    "port": port,
                    "lease_key": key,
                    "lease_token": lease_token,
                }
        return None

    def release(self, lease_info: Dict[str, str | int]) -> bool:
        """Release lease if token matches."""
        client = self._get_client()
        if client is None:
            return False

        key = str(lease_info.get("lease_key") or "")
        token = str(lease_info.get("lease_token") or "")
        if not key:
            host = lease_info.get("host")
            port = lease_info.get("port")
            if host is None or port is None:
                return False
            key = self._lease_key(str(host), int(port))

        try:
            raw = client.get(key)
            if not raw:
                return True
            if token:
                try:
                    parsed = json.loads(raw)
                except Exception:
                    parsed = {}
                if parsed.get("lease_token") and parsed.get("lease_token") != token:
                    return False
            client.delete(key)
            return True
        except Exception as exc:
            logger.warning("Failed to release emulator lease key=%s: %s", key, exc)
            return False
