"""Parse Zeek outputs and tcpdump text logs into observation/domain statistics."""

from __future__ import annotations

import re
import socket
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


FIELD_EMPTY = "(empty)"
FIELD_UNSET = "-"


def _parse_zeek_tsv(text: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    headers: list[str] = []
    path_name: str | None = None
    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip("\n")
        if not line:
            continue
        if line.startswith("#fields\t"):
            headers = line.split("\t")[1:]
            continue
        if line.startswith("#path\t"):
            path_name = line.split("\t", 1)[1].strip()
            continue
        if line.startswith("#"):
            continue
        if not headers:
            headers = _default_headers_for_row(line, path_name=path_name)
        values = line.split("\t")
        rows.append({name: value for name, value in zip(headers, values)})
    return rows


def _default_headers_for_row(line: str, path_name: str | None = None) -> list[str]:
    column_count = len(line.split("\t"))
    if path_name == "conn":
        return [
            "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "service", "duration",
            "orig_bytes", "resp_bytes", "conn_state", "local_orig", "local_resp", "missed_bytes", "history",
            "orig_pkts", "orig_ip_bytes", "resp_pkts", "resp_ip_bytes", "tunnel_parents",
        ][:column_count]
    if path_name == "dns":
        return [
            "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "trans_id", "query",
            "qclass", "qtype", "rcode", "rcode_name", "AA", "TC", "RD", "RA", "answers", "TTLs", "rejected",
        ][:column_count]
    if path_name == "ssl":
        return [
            "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "version", "cipher", "server_name",
            "resumed", "last_alert", "next_protocol", "established",
        ][:column_count]
    if path_name == "http":
        return [
            "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "trans_depth", "method", "host", "uri",
            "referrer", "version", "user_agent", "origin", "request_body_len", "response_body_len", "status_code",
            "status_msg", "info_code", "info_msg", "tags", "username", "password",
        ][:column_count]
    if column_count == 21:
        return [
            "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "service", "duration",
            "orig_bytes", "resp_bytes", "conn_state", "local_orig", "local_resp", "missed_bytes", "history",
            "orig_pkts", "orig_ip_bytes", "resp_pkts", "resp_ip_bytes", "tunnel_parents",
        ]
    if column_count == 19:
        return [
            "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "proto", "trans_id", "query",
            "qclass", "qclass_name", "qtype", "qtype_name", "rcode", "rcode_name", "AA", "TC", "RD", "answers",
        ]
    if column_count == 13:
        return [
            "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "version", "cipher", "server_name",
            "resumed", "last_alert", "next_protocol", "established",
        ]
    if column_count == 23:
        return [
            "ts", "uid", "id.orig_h", "id.orig_p", "id.resp_h", "id.resp_p", "trans_depth", "method", "host", "uri",
            "referrer", "version", "user_agent", "origin", "request_body_len", "response_body_len", "status_code",
            "status_msg", "info_code", "info_msg", "tags", "username", "password",
        ]
    return [f"col_{index}" for index in range(column_count)]


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped in {FIELD_EMPTY, FIELD_UNSET}:
        return None
    return stripped


def _iso8601(value: Optional[str]) -> Optional[str]:
    cleaned = _clean(value)
    if cleaned is None:
        return None
    try:
        return datetime.fromtimestamp(float(cleaned), tz=timezone.utc).isoformat()
    except Exception:
        return None


def _build_observation(*, domain: Optional[str], ip: Optional[str], source_type: str, ts: Optional[str], protocol: Optional[str], transport: Optional[str]) -> Optional[dict[str, Any]]:
    domain = _clean(domain)
    ip = _clean(ip)
    if not domain and not ip:
        return None
    seen_at = _iso8601(ts)
    return {
        "domain": domain,
        "ip": ip,
        "hit_count": 1,
        "source_type": source_type,
        "protocol": _clean(protocol),
        "transport": _clean(transport),
        "first_seen_at": seen_at,
        "last_seen_at": seen_at,
    }


def _aggregate_domains(observations: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for item in observations:
        domain = item.get("domain")
        if not domain:
            continue
        current = grouped.setdefault(
            domain,
            {
                "domain": domain,
                "hit_count": 0,
                "ip_count": 0,
                "ips": set(),
                "source_types": set(),
                "first_seen_at": item.get("first_seen_at"),
                "last_seen_at": item.get("last_seen_at"),
            },
        )
        current["hit_count"] += int(item.get("hit_count") or 1)
        if item.get("ip"):
            current["ips"].add(item["ip"])
        if item.get("source_type"):
            current["source_types"].add(item["source_type"])
        if item.get("first_seen_at") and (current["first_seen_at"] is None or item["first_seen_at"] < current["first_seen_at"]):
            current["first_seen_at"] = item["first_seen_at"]
        if item.get("last_seen_at") and (current["last_seen_at"] is None or item["last_seen_at"] > current["last_seen_at"]):
            current["last_seen_at"] = item["last_seen_at"]
    rows: list[dict[str, Any]] = []
    for current in grouped.values():
        rows.append(
            {
                "domain": current["domain"],
                "hit_count": current["hit_count"],
                "ip_count": len(current["ips"]),
                "source_types": sorted(current["source_types"]),
                "first_seen_at": current["first_seen_at"],
                "last_seen_at": current["last_seen_at"],
            }
        )
    rows.sort(key=lambda item: (-item["hit_count"], item["domain"]))
    return rows


def _resolve_domain_ips(domain: str) -> list[str]:
    domain = str(domain or "").strip()
    if not domain:
        return []
    try:
        infos = socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM)
    except Exception:
        return []
    ips: list[str] = []
    for info in infos:
        ip = info[4][0]
        if ip not in ips:
            ips.append(ip)
    return ips


def _parse_tcpdump_text(text: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    line_pattern = re.compile(
        r"^(?P<ts>\d{2}:\d{2}:\d{2}\.\d+)?\s*IP\s+"
        r"(?P<src>[0-9.]+)\.(?P<src_port>\d+)\s+>\s+(?P<dst>[0-9.]+)\.(?P<dst_port>\d+)"
    )
    connect_pattern = re.compile(r"CONNECT\s+([A-Za-z0-9._-]+):(\d+)\s+HTTP/", re.IGNORECASE)
    host_pattern = re.compile(r"Host:\s*([A-Za-z0-9._-]+)(?::(\d+))?", re.IGNORECASE)
    dns_query_pattern = re.compile(r":\s+(?P<txid>\d+)\+\s+A\?\s+(?P<domain>[A-Za-z0-9._-]+)\.\s+\(")
    dns_answer_pattern = re.compile(r":\s+(?P<txid>\d+)\s+\d+/\d+/\d+\s+A\s+(?P<ips>(?:\d{1,3}(?:\.\d{1,3}){3})(?:,\s*A\s+\d{1,3}(?:\.\d{1,3}){3})*)")

    pending_ts: str | None = None
    pending_dst_ip: str | None = None
    dns_queries: dict[str, tuple[str, str | None]] = {}

    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        line_match = line_pattern.search(line)
        if line_match:
            pending_ts = line_match.group("ts")
            pending_dst_ip = line_match.group("dst")
            if line_match.group("dst_port") == "443":
                observation = _build_observation(
                    domain=None,
                    ip=pending_dst_ip,
                    source_type="tcp",
                    ts=None,
                    protocol="https",
                    transport="tcp",
                )
                if observation:
                    observations.append(observation)
            query_match = dns_query_pattern.search(line)
            if query_match:
                dns_queries[query_match.group("txid")] = (query_match.group("domain"), pending_ts)
                observation = _build_observation(
                    domain=query_match.group("domain"),
                    ip=None,
                    source_type="dns_query",
                    ts=None,
                    protocol="dns",
                    transport="udp",
                )
                if observation:
                    observations.append(observation)
                continue
            answer_match = dns_answer_pattern.search(line)
            if answer_match:
                domain, query_ts = dns_queries.get(answer_match.group("txid"), (None, pending_ts))
                ips = [ip.strip() for ip in re.sub(r"\bA\s+", "", answer_match.group("ips")).split(",") if ip.strip()]
                for ip in ips or [None]:
                    observation = _build_observation(
                        domain=domain,
                        ip=ip,
                        source_type="dns",
                        ts=None,
                        protocol="dns",
                        transport="udp",
                    )
                    if observation:
                        observations.append(observation)
                continue
            continue

        connect_match = connect_pattern.search(line)
        if connect_match:
            domain = connect_match.group(1)
            resolved_ips = _resolve_domain_ips(domain)
            if not resolved_ips and pending_dst_ip:
                resolved_ips = [pending_dst_ip]
            if not resolved_ips:
                resolved_ips = [None]
            for ip in resolved_ips:
                observation = _build_observation(
                    domain=domain,
                    ip=ip,
                    source_type="connect",
                    ts=None,
                    protocol="CONNECT",
                    transport="tcp",
                )
                if observation:
                    observations.append(observation)
            continue

        host_match = host_pattern.search(line)
        if host_match:
            domain = host_match.group(1)
            resolved_ips = _resolve_domain_ips(domain)
            if not resolved_ips and pending_dst_ip:
                resolved_ips = [pending_dst_ip]
            if not resolved_ips:
                resolved_ips = [None]
            for ip in resolved_ips:
                observation = _build_observation(
                    domain=domain,
                    ip=ip,
                    source_type="host_header",
                    ts=None,
                    protocol="HTTP",
                    transport="tcp",
                )
                if observation:
                    observations.append(observation)
    return observations


def parse_zeek_outputs(
    *,
    conn_log: str = "",
    dns_log: str = "",
    ssl_log: str = "",
    http_log: str = "",
    tcpdump_log: str = "",
) -> dict[str, list[dict[str, Any]]]:
    observations: list[dict[str, Any]] = []

    for row in _parse_zeek_tsv(conn_log):
        observation = _build_observation(
            domain=None,
            ip=row.get("id.resp_h"),
            source_type="conn",
            ts=row.get("ts"),
            protocol=row.get("service") or row.get("proto"),
            transport=row.get("proto"),
        )
        if observation:
            observations.append(observation)

    for row in _parse_zeek_tsv(dns_log):
        answers = _clean(row.get("answers"))
        observation = _build_observation(
            domain=row.get("query"),
            ip=(answers.split(",")[0] if answers else None),
            source_type="dns",
            ts=row.get("ts"),
            protocol="dns",
            transport=row.get("proto"),
        )
        if observation:
            observations.append(observation)

    for row in _parse_zeek_tsv(ssl_log):
        observation = _build_observation(
            domain=row.get("server_name"),
            ip=row.get("id.resp_h"),
            source_type="ssl",
            ts=row.get("ts"),
            protocol=row.get("version"),
            transport="tcp",
        )
        if observation:
            observations.append(observation)

    for row in _parse_zeek_tsv(http_log):
        observation = _build_observation(
            domain=row.get("host"),
            ip=row.get("id.resp_h"),
            source_type="http",
            ts=row.get("ts"),
            protocol=row.get("method"),
            transport="tcp",
        )
        if observation:
            observations.append(observation)

    observations.extend(_parse_tcpdump_text(tcpdump_log))

    return {
        "observations": observations,
        "domains": _aggregate_domains(observations),
    }
