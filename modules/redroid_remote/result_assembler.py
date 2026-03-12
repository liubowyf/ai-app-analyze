"""Assemble redroid outputs into the current dynamic-analysis result shape."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REDROID_CAPTURE_MODE = "redroid_zeek"


def _normalize_observation(item: dict[str, Any]) -> dict[str, Any]:
    domain = item.get("domain")
    ip = item.get("ip")
    source_type = item.get("source_type") or "unknown"
    hit_count = max(1, int(item.get("hit_count") or 1))
    first_seen_at = item.get("first_seen_at")
    last_seen_at = item.get("last_seen_at") or first_seen_at
    protocol = item.get("protocol")
    transport = item.get("transport")

    scheme = None
    method = "UNKNOWN"
    if source_type == "http":
        scheme = "http"
        method = str(protocol or "GET").upper()
    elif source_type == "ssl":
        scheme = "https"
    elif source_type == "dns":
        scheme = "dns"
    elif source_type == "conn":
        scheme = "tcp"

    url = f"{scheme}://{domain}" if scheme in {"http", "https"} and domain else None
    return {
        "domain": domain,
        "host": domain,
        "ip": ip,
        "hit_count": hit_count,
        "source_type": source_type,
        "transport": transport or "unknown",
        "protocol": protocol or "unknown",
        "first_seen_at": first_seen_at,
        "last_seen_at": last_seen_at,
        "request_time": first_seen_at,
        "capture_mode": REDROID_CAPTURE_MODE,
        "method": method,
        "scheme": scheme,
        "url": url,
        "path": None,
        "port": 443 if scheme == "https" else 80 if scheme == "http" else 0,
        "package_name": None,
        "uid": None,
        "process_name": None,
        "attribution_tier": "primary",
        "attribution_confidence": 1.0,
    }


def _build_domain_stats(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in observations:
        domain = item.get("domain")
        if not domain:
            continue
        row = grouped.setdefault(
            domain,
            {
                "domain": domain,
                "ip": item.get("ip"),
                "hit_count": 0,
                "request_count": 0,
                "post_count": 0,
                "unique_ip_count": 0,
                "source_types": set(),
                "ips": set(),
                "first_seen_at": item.get("first_seen_at"),
                "last_seen_at": item.get("last_seen_at"),
                "capture_mode": REDROID_CAPTURE_MODE,
            },
        )
        row["hit_count"] += int(item.get("hit_count") or 1)
        row["request_count"] = row["hit_count"]
        if item.get("ip"):
            row["ips"].add(item["ip"])
            if row.get("ip") is None:
                row["ip"] = item["ip"]
        if item.get("source_type"):
            row["source_types"].add(str(item["source_type"]))
        if item.get("first_seen_at") and (
            row["first_seen_at"] is None or item["first_seen_at"] < row["first_seen_at"]
        ):
            row["first_seen_at"] = item["first_seen_at"]
        if item.get("last_seen_at") and (
            row["last_seen_at"] is None or item["last_seen_at"] > row["last_seen_at"]
        ):
            row["last_seen_at"] = item["last_seen_at"]
    rows: list[dict[str, Any]] = []
    for row in grouped.values():
        row["unique_ip_count"] = len(row.pop("ips"))
        row["source_types"] = sorted(row["source_types"])
        rows.append(row)
    rows.sort(key=lambda item: (-item["hit_count"], item["domain"]))
    return rows


@dataclass(slots=True)
class RedroidObservationAdapter:
    """Adapter that mimics the current TrafficMonitor read API."""

    observations: list[dict[str, Any]]

    def get_requests_as_dict(self) -> list[dict[str, Any]]:
        return list(self.observations)

    def get_candidate_requests_as_dict(self) -> list[dict[str, Any]]:
        return []

    def get_requests(self) -> list[dict[str, Any]]:
        return list(self.observations)

    def get_candidate_requests(self) -> list[dict[str, Any]]:
        return []

    def get_aggregated_requests(self) -> list[dict[str, Any]]:
        return self.get_requests_as_dict()

    def get_candidate_aggregated_requests(self) -> list[dict[str, Any]]:
        return []

    def get_domain_stats(self) -> list[dict[str, Any]]:
        return _build_domain_stats(self.observations)

    def analyze_traffic(self) -> dict[str, Any]:
        source_breakdown: dict[str, int] = {}
        unique_hosts = set()
        unique_ips = set()
        total_hits = 0
        for item in self.observations:
            source = str(item.get("source_type") or "unknown")
            source_breakdown[source] = source_breakdown.get(source, 0) + int(item.get("hit_count") or 1)
            if item.get("domain"):
                unique_hosts.add(item["domain"])
            if item.get("ip"):
                unique_ips.add(item["ip"])
            total_hits += int(item.get("hit_count") or 1)
        return {
            "capture_mode": REDROID_CAPTURE_MODE,
            "source_breakdown": source_breakdown,
            "sources": source_breakdown,
            "candidate_sources": {},
            "unique_hosts": len(unique_hosts),
            "candidate_unique_hosts": 0,
            "unique_ips": len(unique_ips),
            "total_observations": total_hits,
            "primary_observations": total_hits,
            "candidate_observations": 0,
            "tls_handshake_failures_by_host": {},
        }


def assemble_redroid_observation_adapter(parsed: dict[str, list[dict[str, Any]]]) -> tuple[RedroidObservationAdapter, dict[str, Any]]:
    """Normalize parsed Zeek outputs for the current persistence and report chain."""
    observations = [_normalize_observation(item) for item in parsed.get("observations", [])]
    adapter = RedroidObservationAdapter(observations=observations)
    domain_report = {
        "capture_mode": REDROID_CAPTURE_MODE,
        "master_domains": [
            {
                "domain": row.get("domain"),
                "ip": row.get("ip"),
                "score": row.get("hit_count", 0),
                "confidence": "observed",
                "hit_count": row.get("hit_count", 0),
                "request_count": row.get("request_count", 0),
                "post_count": row.get("post_count", 0),
                "unique_ip_count": row.get("unique_ip_count", 0),
                "source_types": row.get("source_types", []),
                "first_seen_at": row.get("first_seen_at"),
                "last_seen_at": row.get("last_seen_at"),
                "capture_mode": REDROID_CAPTURE_MODE,
                "evidence": {"source_types": row.get("source_types", [])},
            }
            for row in _build_domain_stats(observations)
        ],
    }
    return adapter, domain_report
