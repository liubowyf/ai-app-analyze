"""IP geolocation batching and filtering service."""

from __future__ import annotations

import ipaddress
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

from core.config import settings
from modules.ip_geo.aliyun_client import AliyunIpGeoClient

logger = logging.getLogger(__name__)


def clamp_ip_geo_concurrency(value: int) -> int:
    return max(1, min(int(value or 1), 30))


def _is_public_ip(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not any(
        (
            parsed.is_private,
            parsed.is_loopback,
            parsed.is_multicast,
            parsed.is_link_local,
            parsed.is_reserved,
            parsed.is_unspecified,
        )
    )


def _normalize_ip_inputs(ips: Iterable[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in ips:
        text = str(raw or "").strip()
        if not text or text in seen or not _is_public_ip(text):
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def resolve_ip_locations_with_client(
    ips: Iterable[str],
    *,
    client: AliyunIpGeoClient,
    max_concurrency: int,
) -> dict[str, str]:
    normalized_ips = _normalize_ip_inputs(ips)
    if not normalized_ips:
        return {}

    resolved: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=clamp_ip_geo_concurrency(max_concurrency)) as executor:
        future_map = {executor.submit(client.lookup_ip, ip): ip for ip in normalized_ips}
        for future in as_completed(future_map):
            ip = future_map[future]
            try:
                location = future.result()
            except Exception as exc:
                logger.warning("IP geolocation lookup failed ip=%s error=%s", ip, exc)
                continue
            if location:
                resolved[ip] = location
    return resolved


def resolve_ip_locations(ips: Iterable[str]) -> dict[str, str]:
    if not settings.ALIYUN_IP_GEO_ENABLED:
        return {}

    client = AliyunIpGeoClient(
        base_url=settings.ALIYUN_IP_GEO_BASE_URL,
        appcode=settings.ALIYUN_IP_GEO_APPCODE,
        appkey=settings.ALIYUN_IP_GEO_APPKEY,
        appsecret=settings.ALIYUN_IP_GEO_APPSECRET,
        timeout_seconds=settings.ALIYUN_IP_GEO_TIMEOUT_SECONDS,
    )
    return resolve_ip_locations_with_client(
        ips,
        client=client,
        max_concurrency=settings.ALIYUN_IP_GEO_MAX_CONCURRENCY,
    )
