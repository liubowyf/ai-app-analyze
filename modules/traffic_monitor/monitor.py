"""Passive traffic monitor and observation aggregation helpers."""

from __future__ import annotations

import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from .attribution import AttributionEngine
from .filter_policy import TrafficFilterPolicy
from .observation_models import PASSIVE_CAPTURE_MODE, NetworkObservation, parse_observation_timestamp
from .passive_sources import ProxyConnectTcpdumpObservationSource

logger = logging.getLogger(__name__)


class TrafficMonitor:
    """Aggregate passive domain/IP observations without MITM proxying."""

    def __init__(
        self,
        proxy_port: int = 8080,
        observation_sources: Optional[Iterable[Any]] = None,
        capture_mode: str = PASSIVE_CAPTURE_MODE,
    ):
        self.proxy_port = proxy_port
        self.capture_mode = capture_mode or PASSIVE_CAPTURE_MODE
        self.whitelist_rules: List[str] = []
        self._running = False
        self._primary_observations: Dict[tuple[str, str, str, str, str], NetworkObservation] = {}
        self._candidate_observations: Dict[tuple[str, str, str, str, str], NetworkObservation] = {}
        self._observation_sources = list(observation_sources or [])
        self._emulator_host: Optional[str] = None
        self._emulator_port: Optional[int] = None
        self._android_runner = None
        self._target_package: Optional[str] = None
        self._capture_only_target_foreground = False
        self._foreground_cache_ttl = 0.8
        self._last_foreground_check_at = 0.0
        self._last_foreground_package: Optional[str] = None
        self.filter_policy = TrafficFilterPolicy()
        self._attribution_engine: Optional[AttributionEngine] = None
        self._candidate_limit = 5000
        self._proxy_session = None
        self._cert_diagnostics: Dict[str, Any] = {"verification_status": "not_applicable"}
        self._capture_diagnostics: Dict[str, Any] = {
            "capture_mode": self.capture_mode,
            "backend": "none",
            "switch_applied": False,
            "degraded_reason": None,
            "sources": [],
        }

    @staticmethod
    def _default_proxy_port() -> int:
        baseline = (
            os.getenv("ANDROID_HTTP_PROXY_BASELINE")
            or os.getenv("EMULATOR_HTTP_PROXY_BASELINE")
            or os.getenv("HTTP_PROXY")
            or os.getenv("http_proxy")
            or ""
        )
        if ":" in baseline:
            try:
                return int(str(baseline).rsplit(":", 1)[-1])
            except Exception:
                return 3128
        return 3128

    def set_target_app_context(
        self,
        target_package: Optional[str],
        emulator_host: Optional[str],
        emulator_port: Optional[int],
        android_runner: Optional[Any] = None,
    ) -> None:
        """Bind monitor to target app context for best-effort attribution and filtering."""
        self._target_package = target_package
        self._emulator_host = emulator_host
        self._emulator_port = emulator_port
        self._android_runner = android_runner
        self._capture_only_target_foreground = bool(target_package and emulator_host and emulator_port and android_runner)
        self._last_foreground_check_at = 0.0
        self._last_foreground_package = None
        self._attribution_engine = AttributionEngine(
            emulator_host=emulator_host,
            emulator_port=emulator_port,
            android_runner=android_runner,
            target_package=target_package,
        )

    def set_filter_policy(self, policy: Optional[Dict[str, Any]] = None) -> None:
        """Override default filter policy with runtime config."""
        if not policy:
            return
        if "strict_target_package" in policy:
            self.filter_policy.strict_target_package = bool(policy["strict_target_package"])
        if "include_packages" in policy and isinstance(policy["include_packages"], list):
            self.filter_policy.include_packages = [str(x) for x in policy["include_packages"]]
        if "include_uids" in policy and isinstance(policy["include_uids"], list):
            self.filter_policy.include_uids = [int(x) for x in policy["include_uids"]]
        if "exclude_domains" in policy and isinstance(policy["exclude_domains"], list):
            self.filter_policy.exclude_domains = [str(x) for x in policy["exclude_domains"]]
        if "exclude_process_prefixes" in policy and isinstance(policy["exclude_process_prefixes"], list):
            self.filter_policy.exclude_process_prefixes = [str(x) for x in policy["exclude_process_prefixes"]]
        if "candidate_limit" in policy:
            try:
                self._candidate_limit = max(100, min(int(policy["candidate_limit"]), 20000))
            except Exception:
                pass

    def _is_system_noise_request(self, host: str, path: str) -> bool:
        host_l = (host or "").lower()
        path_l = (path or "").lower()
        if host_l == "connectivitycheck.gstatic.com" and "generate_204" in path_l:
            return True
        if host_l == "play.googleapis.com" and "generate_204" in path_l:
            return True
        if host_l == "www.google.com" and "gen_204" in path_l:
            return True
        if host_l == "clients3.google.com" and "generate_204" in path_l:
            return True
        return False

    def _get_foreground_package(self) -> str:
        if not self._capture_only_target_foreground:
            return ""
        if not self._emulator_host or not self._emulator_port:
            return ""

        now = time.monotonic()
        if now - self._last_foreground_check_at < self._foreground_cache_ttl:
            return self._last_foreground_package or ""

        pkg = ""
        runner = self._android_runner
        if runner and hasattr(runner, "get_current_package"):
            try:
                value = runner.get_current_package(self._emulator_host, self._emulator_port)
                if isinstance(value, str):
                    pkg = value.strip()
            except Exception as exc:
                logger.debug("Failed to query foreground package: %s", exc)

        self._last_foreground_package = pkg
        self._last_foreground_check_at = now
        return pkg

    def set_whitelist(self, domains: List[str]) -> None:
        self.whitelist_rules = domains
        merged = list(self.filter_policy.exclude_domains)
        for domain in domains:
            if domain not in merged:
                merged.append(domain)
        self.filter_policy.exclude_domains = merged

    def is_whitelisted(self, host: str) -> bool:
        import fnmatch

        for rule in self.whitelist_rules:
            if fnmatch.fnmatch(host, rule):
                return True
        return False

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except Exception:
            return default

    @staticmethod
    def _infer_transport(request_data: Dict[str, Any], source_type: str) -> str:
        if request_data.get("transport"):
            return str(request_data["transport"])
        if source_type == "dns":
            return "udp"
        return "tcp"

    @staticmethod
    def _infer_protocol(request_data: Dict[str, Any], source_type: str) -> str:
        if request_data.get("protocol"):
            return str(request_data["protocol"])
        scheme = str(request_data.get("scheme") or "").lower()
        method = str(request_data.get("method") or "").upper()
        if source_type == "dns":
            return "dns"
        if source_type == "connect" or method == "CONNECT" or scheme == "https":
            return "https_tunnel"
        if scheme == "http":
            return "http"
        return "unknown"

    @staticmethod
    def _infer_scheme(request_data: Dict[str, Any], protocol: str) -> Optional[str]:
        if request_data.get("scheme"):
            return str(request_data["scheme"])
        if protocol in {"https_tunnel", "tls"}:
            return "https"
        if protocol == "http":
            return "http"
        return None

    def _build_observation(self, request_data: Dict[str, Any]) -> NetworkObservation:
        attrs = self._attribution_engine.enrich(request_data) if self._attribution_engine else None
        source_type = str(
            request_data.get("source_type")
            or request_data.get("source")
            or (attrs.source if attrs else "unknown")
            or "unknown"
        )
        protocol = self._infer_protocol(request_data, source_type)
        first_seen_at = parse_observation_timestamp(
            request_data.get("first_seen_at")
            or request_data.get("request_time")
            or request_data.get("timestamp")
        )
        last_seen_at = parse_observation_timestamp(
            request_data.get("last_seen_at")
            or request_data.get("request_time")
            or request_data.get("timestamp")
        )
        if last_seen_at < first_seen_at:
            last_seen_at = first_seen_at

        method = str(request_data.get("method") or ("CONNECT" if source_type == "connect" else "UNKNOWN"))
        domain = request_data.get("domain") or request_data.get("host")
        package_name = request_data.get("package_name") or (attrs.package_name if attrs else None)
        uid = request_data.get("uid")
        if uid is None and attrs:
            uid = attrs.uid
        process_name = request_data.get("process_name") or (attrs.process_name if attrs else None)
        confidence = request_data.get("attribution_confidence")
        if confidence is None and attrs:
            confidence = attrs.confidence

        return NetworkObservation(
            domain=str(domain).strip() if domain else None,
            ip=str(request_data.get("ip")).strip() if request_data.get("ip") else None,
            port=self._safe_int(request_data.get("port"), 0) or None,
            source_type=source_type,
            transport=self._infer_transport(request_data, source_type),
            protocol=protocol,
            first_seen_at=first_seen_at,
            last_seen_at=last_seen_at,
            hit_count=max(1, self._safe_int(request_data.get("hit_count"), 1)),
            uid=self._safe_int(uid, 0) or None,
            package_name=str(package_name).strip() if package_name else None,
            process_name=str(process_name).strip() if process_name else None,
            attribution_confidence=float(confidence or 0.0),
            attribution_tier=str(request_data.get("attribution_tier") or "primary"),
            capture_mode=str(request_data.get("capture_mode") or PASSIVE_CAPTURE_MODE),
            method=method,
            url=request_data.get("url"),
            path=request_data.get("path"),
            scheme=self._infer_scheme(request_data, protocol),
            response_code=request_data.get("response_code"),
            content_type=request_data.get("content_type"),
            request_headers=request_data.get("request_headers", {}) or {},
            response_headers=request_data.get("response_headers", {}) or {},
            request_body=request_data.get("request_body"),
            response_body=request_data.get("response_body"),
        )

    def _should_capture_observation(self, observation: NetworkObservation) -> bool:
        if not observation.host and not observation.ip:
            return False
        if self.is_whitelisted(observation.host):
            return False
        if self._is_system_noise_request(observation.host, observation.path or ""):
            return False

        if self._target_package and observation.package_name == self._target_package:
            return not self.filter_policy.should_drop(
                observation.host,
                observation.path or "",
                observation.package_name,
                observation.uid,
                observation.process_name,
                self._target_package,
            )

        if self._capture_only_target_foreground:
            current_pkg = self._get_foreground_package()
            if not current_pkg or current_pkg != self._target_package:
                return False

        return not self.filter_policy.should_drop(
            observation.host,
            observation.path or "",
            observation.package_name,
            observation.uid,
            observation.process_name,
            self._target_package,
        )

    def _should_keep_candidate_observation(self, observation: NetworkObservation) -> bool:
        if not observation.host and not observation.ip:
            return False
        if self.is_whitelisted(observation.host):
            return False
        if self._is_system_noise_request(observation.host, observation.path or ""):
            return False
        return True

    @staticmethod
    def _observation_key(observation: NetworkObservation) -> tuple[str, str, str, str, str]:
        return (
            observation.host or "",
            observation.ip or "",
            observation.source_type or "unknown",
            observation.transport or "unknown",
            observation.protocol or "unknown",
        )

    def _merge_observation(
        self,
        pool: Dict[tuple[str, str, str, str, str], NetworkObservation],
        observation: NetworkObservation,
    ) -> None:
        key = self._observation_key(observation)
        existing = pool.get(key)
        if existing is None:
            pool[key] = observation
            return

        existing.first_seen_at = min(existing.first_seen_at, observation.first_seen_at)
        existing.last_seen_at = max(existing.last_seen_at, observation.last_seen_at)
        existing.hit_count += max(1, observation.hit_count)
        existing.port = existing.port or observation.port
        existing.scheme = existing.scheme or observation.scheme
        existing.url = existing.url or observation.url
        existing.path = existing.path or observation.path
        if existing.method == "UNKNOWN" and observation.method:
            existing.method = observation.method
        existing.response_code = existing.response_code or observation.response_code
        existing.content_type = existing.content_type or observation.content_type
        existing.package_name = existing.package_name or observation.package_name
        existing.uid = existing.uid or observation.uid
        existing.process_name = existing.process_name or observation.process_name
        existing.attribution_confidence = max(existing.attribution_confidence, observation.attribution_confidence)
        if not existing.request_headers and observation.request_headers:
            existing.request_headers = dict(observation.request_headers)
        if not existing.response_headers and observation.response_headers:
            existing.response_headers = dict(observation.response_headers)
        existing.request_body = existing.request_body or observation.request_body
        existing.response_body = existing.response_body or observation.response_body

    def add_request(self, request_data: Dict[str, Any]) -> None:
        """Ingest one observation event (legacy name kept for compatibility)."""
        observation = self._build_observation(request_data)
        if self._should_capture_observation(observation):
            observation.attribution_tier = "primary"
            self._merge_observation(self._primary_observations, observation)
            return

        if self._should_keep_candidate_observation(observation):
            observation.attribution_tier = "candidate"
            key = self._observation_key(observation)
            if key in self._candidate_observations or len(self._candidate_observations) < self._candidate_limit:
                self._merge_observation(self._candidate_observations, observation)

    def record_observation(self, observation_data: Dict[str, Any]) -> None:
        """Explicit passive observation ingestion API."""
        self.add_request(observation_data)

    def _filter_observations(
        self,
        observations: Iterable[NetworkObservation],
        domain: Optional[str] = None,
        package_name: Optional[str] = None,
        uid: Optional[int] = None,
        process_name: Optional[str] = None,
    ) -> List[NetworkObservation]:
        items = list(observations)
        if domain:
            items = [item for item in items if domain in (item.host or "")]
        if package_name:
            items = [item for item in items if item.package_name == package_name]
        if uid is not None:
            items = [item for item in items if item.uid == uid]
        if process_name:
            items = [item for item in items if item.process_name == process_name]
        return sorted(
            items,
            key=lambda item: (item.last_seen_at, item.hit_count, item.host or "", item.ip or ""),
            reverse=True,
        )

    def get_requests(
        self,
        domain: Optional[str] = None,
        package_name: Optional[str] = None,
        uid: Optional[int] = None,
        process_name: Optional[str] = None,
    ) -> List[NetworkObservation]:
        return self._filter_observations(
            self._primary_observations.values(),
            domain=domain,
            package_name=package_name,
            uid=uid,
            process_name=process_name,
        )

    def get_observations(
        self,
        domain: Optional[str] = None,
        package_name: Optional[str] = None,
        uid: Optional[int] = None,
        process_name: Optional[str] = None,
    ) -> List[NetworkObservation]:
        return self.get_requests(domain=domain, package_name=package_name, uid=uid, process_name=process_name)

    def get_requests_as_dict(self) -> List[Dict[str, Any]]:
        return [self._observation_to_dict(req) for req in self.get_requests()]

    def get_observations_as_dict(self) -> List[Dict[str, Any]]:
        return self.get_requests_as_dict()

    def get_candidate_requests(
        self,
        domain: Optional[str] = None,
        package_name: Optional[str] = None,
        uid: Optional[int] = None,
        process_name: Optional[str] = None,
    ) -> List[NetworkObservation]:
        return self._filter_observations(
            self._candidate_observations.values(),
            domain=domain,
            package_name=package_name,
            uid=uid,
            process_name=process_name,
        )

    def get_candidate_requests_as_dict(self) -> List[Dict[str, Any]]:
        return [self._observation_to_dict(req) for req in self.get_candidate_requests()]

    def get_candidate_observations_as_dict(self) -> List[Dict[str, Any]]:
        return self.get_candidate_requests_as_dict()

    def get_aggregated_requests(self) -> List[Dict[str, Any]]:
        return [self._observation_to_aggregate_dict(req) for req in self.get_requests()]

    def get_candidate_aggregated_requests(self) -> List[Dict[str, Any]]:
        return [self._observation_to_aggregate_dict(req) for req in self.get_candidate_requests()]

    @staticmethod
    def _observation_to_dict(req: NetworkObservation) -> Dict[str, Any]:
        return req.to_dict()

    @staticmethod
    def _observation_to_aggregate_dict(req: NetworkObservation) -> Dict[str, Any]:
        return {
            "domain": req.domain,
            "host": req.host,
            "path": req.path,
            "method": req.method,
            "count": req.hit_count,
            "packages": [req.package_name] if req.package_name else [],
            "sources": [req.source_type] if req.source_type else [],
            "ips": [req.ip] if req.ip else [],
            "first_seen_at": req.first_seen_at.isoformat() if req.first_seen_at else None,
            "last_seen_at": req.last_seen_at.isoformat() if req.last_seen_at else None,
            "transport": req.transport,
            "protocol": req.protocol,
            "attribution_tier": req.attribution_tier,
        }

    def get_suspicious_requests(self) -> List[NetworkObservation]:
        return self.get_requests()

    def clear_requests(self) -> None:
        self._primary_observations.clear()
        self._candidate_observations.clear()

    def get_tls_handshake_failures(self) -> Dict[str, int]:
        return {}

    def get_capture_diagnostics(self) -> Dict[str, Any]:
        diagnostics = self._collect_source_diagnostics()
        self._capture_diagnostics = {
            "capture_mode": diagnostics.get("capture_mode", self.capture_mode),
            "backend": diagnostics.get("backend", "none"),
            "switch_applied": diagnostics.get("switch_applied", False),
            "degraded_reason": diagnostics.get("degraded_reason"),
            "sources": diagnostics.get("sources", []),
            "cert": dict(self._cert_diagnostics),
            "tls": {
                "total_failures": 0,
                "by_host": {},
            },
        }
        return dict(self._capture_diagnostics)

    def _collect_source_diagnostics(self) -> Dict[str, Any]:
        source_diagnostics: List[Dict[str, Any]] = []
        for source in self._observation_sources:
            getter = getattr(source, "get_diagnostics", None)
            if callable(getter):
                try:
                    value = getter()
                except Exception:
                    continue
                if isinstance(value, dict):
                    source_diagnostics.append(value)
        if not source_diagnostics:
            return {"sources": []}
        primary = source_diagnostics[0]
        merged = dict(primary)
        merged["sources"] = source_diagnostics
        return merged

    def export_to_json(self) -> str:
        return json.dumps(self.get_observations_as_dict(), indent=2, ensure_ascii=False)

    def get_domain_stats(self) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for observation in self.get_requests() + self.get_candidate_requests():
            if not observation.host:
                continue
            row = grouped.setdefault(
                observation.host,
                {
                    "domain": observation.host,
                    "ip": observation.ip,
                    "hit_count": 0,
                    "ips": set(),
                    "source_types": set(),
                    "transports": set(),
                    "protocols": set(),
                    "primary_hits": 0,
                    "candidate_hits": 0,
                    "first_seen_at": observation.first_seen_at,
                    "last_seen_at": observation.last_seen_at,
                },
            )
            row["hit_count"] += observation.hit_count
            if observation.ip:
                row["ips"].add(observation.ip)
                row["ip"] = row["ip"] or observation.ip
            if observation.source_type:
                row["source_types"].add(observation.source_type)
            if observation.transport:
                row["transports"].add(observation.transport)
            if observation.protocol:
                row["protocols"].add(observation.protocol)
            if observation.attribution_tier == "candidate":
                row["candidate_hits"] += observation.hit_count
            else:
                row["primary_hits"] += observation.hit_count
            row["first_seen_at"] = min(row["first_seen_at"], observation.first_seen_at)
            row["last_seen_at"] = max(row["last_seen_at"], observation.last_seen_at)

        items: List[Dict[str, Any]] = []
        for row in grouped.values():
            items.append(
                {
                    "domain": row["domain"],
                    "ip": row["ip"],
                    "hit_count": row["hit_count"],
                    "unique_ip_count": len(row["ips"]),
                    "ips": sorted(row["ips"]),
                    "source_types": sorted(row["source_types"]),
                    "transports": sorted(row["transports"]),
                    "protocols": sorted(row["protocols"]),
                    "primary_hits": row["primary_hits"],
                    "candidate_hits": row["candidate_hits"],
                    "first_seen_at": row["first_seen_at"].isoformat() if row["first_seen_at"] else None,
                    "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                }
            )
        return sorted(items, key=lambda item: (item["hit_count"], item["domain"] or ""), reverse=True)

    def get_ip_stats(self) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        for observation in self.get_requests() + self.get_candidate_requests():
            if not observation.ip:
                continue
            row = grouped.setdefault(
                observation.ip,
                {
                    "ip": observation.ip,
                    "hit_count": 0,
                    "domains": set(),
                    "source_types": set(),
                    "transports": set(),
                    "protocols": set(),
                    "first_seen_at": observation.first_seen_at,
                    "last_seen_at": observation.last_seen_at,
                },
            )
            row["hit_count"] += observation.hit_count
            if observation.host:
                row["domains"].add(observation.host)
            if observation.source_type:
                row["source_types"].add(observation.source_type)
            if observation.transport:
                row["transports"].add(observation.transport)
            if observation.protocol:
                row["protocols"].add(observation.protocol)
            row["first_seen_at"] = min(row["first_seen_at"], observation.first_seen_at)
            row["last_seen_at"] = max(row["last_seen_at"], observation.last_seen_at)

        items: List[Dict[str, Any]] = []
        for row in grouped.values():
            items.append(
                {
                    "ip": row["ip"],
                    "hit_count": row["hit_count"],
                    "domain_count": len(row["domains"]),
                    "domains": sorted(row["domains"]),
                    "source_types": sorted(row["source_types"]),
                    "transports": sorted(row["transports"]),
                    "protocols": sorted(row["protocols"]),
                    "first_seen_at": row["first_seen_at"].isoformat() if row["first_seen_at"] else None,
                    "last_seen_at": row["last_seen_at"].isoformat() if row["last_seen_at"] else None,
                }
            )
        return sorted(items, key=lambda item: (item["hit_count"], item["ip"] or ""), reverse=True)

    def analyze_traffic(self) -> Dict[str, Any]:
        primary = self.get_requests()
        candidate = self.get_candidate_requests()
        all_observations = primary + candidate

        source_counts: Dict[str, int] = defaultdict(int)
        package_counts: Dict[str, int] = defaultdict(int)
        candidate_sources: Dict[str, int] = defaultdict(int)
        candidate_packages: Dict[str, int] = defaultdict(int)

        for observation in primary:
            source_counts[observation.source_type or "unknown"] += observation.hit_count
            package_counts[observation.package_name or "unknown"] += observation.hit_count

        for observation in candidate:
            source_counts[observation.source_type or "unknown"] += observation.hit_count
            package_counts[observation.package_name or "unknown"] += observation.hit_count
            candidate_sources[observation.source_type or "unknown"] += observation.hit_count
            candidate_packages[observation.package_name or "unknown"] += observation.hit_count

        total_observations = sum(item.hit_count for item in all_observations)
        primary_observations = sum(item.hit_count for item in primary)
        candidate_observations = sum(item.hit_count for item in candidate)
        unique_domains = sorted({item.host for item in all_observations if item.host})
        unique_ips = sorted({item.ip for item in all_observations if item.ip})

        return {
            "capture_mode": self.get_capture_diagnostics().get("capture_mode", self.capture_mode),
            "total_observations": total_observations,
            "total_requests": total_observations,
            "primary_observations": primary_observations,
            "candidate_observations": candidate_observations,
            "candidate_total_requests": candidate_observations,
            "unique_domains": len(unique_domains),
            "unique_hosts": len(unique_domains),
            "unique_ips": len(unique_ips),
            "hosts": unique_domains,
            "source_breakdown": dict(source_counts),
            "sources": dict(source_counts),
            "packages": dict(package_counts),
            "aggregated": self.get_aggregated_requests()[:100],
            "candidate_unique_hosts": len({item.host for item in candidate if item.host}),
            "candidate_sources": dict(candidate_sources),
            "candidate_packages": dict(candidate_packages),
            "candidate_aggregated": self.get_candidate_aggregated_requests()[:100],
            "domain_stats": self.get_domain_stats()[:100],
            "ip_stats": self.get_ip_stats()[:100],
            "quality_gate": {
                "status": "pass" if total_observations > 0 else "degraded",
                "observed_domains": len(unique_domains),
                "observed_ips": len(unique_ips),
                "observation_hits": total_observations,
            },
            "capture_diagnostics": self.get_capture_diagnostics(),
            "cert_verification_status": "not_applicable",
            "cert_diagnostics": {"verification_status": "not_applicable"},
            "tls_handshake_failures": 0,
            "tls_handshake_failures_by_host": {},
        }

    def start(
        self,
        emulator_host: Optional[str] = None,
        emulator_port: Optional[int] = None,
        target_package: Optional[str] = None,
        android_runner: Optional[Any] = None,
        port_fallback_attempts: int = 5,
    ) -> None:
        """Start passive observation sources without touching device proxy state."""
        del port_fallback_attempts
        self.set_target_app_context(
            target_package=target_package,
            emulator_host=emulator_host,
            emulator_port=emulator_port,
            android_runner=android_runner,
        )
        if not self._observation_sources and emulator_host and emulator_port:
            self._observation_sources = [ProxyConnectTcpdumpObservationSource(self._default_proxy_port())]
        self._running = True
        for source in self._observation_sources:
            starter = getattr(source, "start", None)
            if callable(starter):
                try:
                    starter(
                        self._on_request_captured,
                        emulator_host=emulator_host,
                        emulator_port=emulator_port,
                        target_package=target_package,
                        android_runner=android_runner,
                    )
                except Exception as exc:
                    logger.warning("Passive observation source failed to start: %s", exc)
        self._capture_diagnostics = self.get_capture_diagnostics()
        logger.info("Traffic monitor started in passive mode with %s observation source(s)", len(self._observation_sources))

    def _on_request_captured(self, request_data: Dict[str, Any]) -> None:
        self.add_request(request_data)

    def stop(self) -> None:
        for source in self._observation_sources:
            stopper = getattr(source, "stop", None)
            if callable(stopper):
                try:
                    stopper()
                except Exception as exc:
                    logger.warning("Failed to stop passive observation source: %s", exc)
        self._running = False
        self._capture_diagnostics = self.get_capture_diagnostics()

    @property
    def is_running(self) -> bool:
        return self._running
