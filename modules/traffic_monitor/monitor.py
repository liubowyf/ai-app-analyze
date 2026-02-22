"""Traffic Monitor module for network traffic analysis."""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from .attribution import AttributionEngine
from .filter_policy import TrafficFilterPolicy

logger = logging.getLogger(__name__)


@dataclass
class NetworkRequest:
    """Network request data structure."""

    url: str
    method: str
    host: str
    path: str
    ip: Optional[str]
    port: int
    scheme: str
    request_time: datetime
    response_code: Optional[int]
    content_type: Optional[str]
    request_headers: Dict[str, str]
    response_headers: Dict[str, str]
    request_body: Optional[str]
    response_body: Optional[str]
    uid: Optional[int] = None
    package_name: Optional[str] = None
    process_name: Optional[str] = None
    source: str = "unknown"
    capture_backend: str = "mitm"
    attribution_confidence: float = 0.0


class TrafficMonitor:
    """Network traffic monitor using mitmproxy."""

    def __init__(self, proxy_port: int = 8080):
        self.requests: List[NetworkRequest] = []
        self.whitelist_rules: List[str] = []
        self._running = False
        self.proxy_port = proxy_port
        self._mitmproxy_manager = None
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

    def set_target_app_context(
        self,
        target_package: Optional[str],
        emulator_host: Optional[str],
        emulator_port: Optional[int],
        android_runner: Optional[Any] = None,
    ) -> None:
        """Bind monitor to target app context so only in-app traffic is captured."""
        self._target_package = target_package
        self._emulator_host = emulator_host
        self._emulator_port = emulator_port
        self._android_runner = android_runner
        self._capture_only_target_foreground = bool(target_package and emulator_host and emulator_port)
        self._last_foreground_check_at = 0.0
        self._last_foreground_package = None
        self._attribution_engine = AttributionEngine(
            emulator_host=emulator_host,
            emulator_port=emulator_port,
            android_runner=android_runner,
            target_package=target_package,
        )

        if self._capture_only_target_foreground:
            logger.info(
                "Traffic monitor foreground filter enabled (target=%s, emulator=%s:%s)",
                target_package,
                emulator_host,
                emulator_port,
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

    def _is_system_noise_request(self, host: str, path: str) -> bool:
        if not host:
            return False
        host_l = host.lower()
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
        logger.info("Set whitelist with %s rules", len(domains))

    def is_whitelisted(self, host: str) -> bool:
        import fnmatch

        for rule in self.whitelist_rules:
            if fnmatch.fnmatch(host, rule):
                return True
        return False

    @staticmethod
    def _parse_request_time(request_data: Dict[str, Any]) -> datetime:
        value = request_data.get("request_time", datetime.now())
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except Exception:
                return datetime.now()
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        return datetime.now()

    def _build_request(self, request_data: Dict[str, Any]) -> NetworkRequest:
        attrs = None
        if self._attribution_engine:
            attrs = self._attribution_engine.enrich(request_data)

        return NetworkRequest(
            url=request_data.get("url", ""),
            method=request_data.get("method", "GET"),
            host=request_data.get("host", ""),
            path=request_data.get("path", "/"),
            ip=request_data.get("ip"),
            port=request_data.get("port", 80),
            scheme=request_data.get("scheme", "https"),
            request_time=self._parse_request_time(request_data),
            response_code=request_data.get("response_code"),
            content_type=request_data.get("content_type"),
            request_headers=request_data.get("request_headers", {}),
            response_headers=request_data.get("response_headers", {}),
            request_body=request_data.get("request_body"),
            response_body=request_data.get("response_body"),
            uid=attrs.uid if attrs else None,
            package_name=attrs.package_name if attrs else None,
            process_name=attrs.process_name if attrs else None,
            source=attrs.source if attrs else "unknown",
            capture_backend=request_data.get("capture_backend", "mitm"),
            attribution_confidence=attrs.confidence if attrs else 0.0,
        )

    def _should_capture_request(self, request: NetworkRequest) -> bool:
        if self.is_whitelisted(request.host):
            return False

        if self._is_system_noise_request(request.host, request.path):
            return False

        # Keep highly confident target-package requests even if app is not in foreground.
        if self._target_package and request.package_name == self._target_package and request.attribution_confidence >= 0.9:
            return not self.filter_policy.should_drop(
                request.host,
                request.path,
                request.package_name,
                request.uid,
                request.process_name,
                self._target_package,
            )

        if self._capture_only_target_foreground:
            current_pkg = self._get_foreground_package()
            if not current_pkg:
                return False
            if current_pkg != self._target_package:
                return False

        if self.filter_policy.should_drop(
            request.host,
            request.path,
            request.package_name,
            request.uid,
            request.process_name,
            self._target_package,
        ):
            return False

        return True

    def add_request(self, request_data: Dict[str, Any]) -> None:
        try:
            request = self._build_request(request_data)
            if not self._should_capture_request(request):
                logger.debug("Skipping non-target/noise traffic: %s%s", request.host, request.path)
                return
            self.requests.append(request)
            logger.info("Captured: %s %s%s", request.method, request.host, request.path)
        except Exception as e:
            logger.error("Failed to add request: %s", e)

    def get_requests(
        self,
        domain: Optional[str] = None,
        package_name: Optional[str] = None,
        uid: Optional[int] = None,
        process_name: Optional[str] = None,
    ) -> List[NetworkRequest]:
        items = self.requests
        if domain:
            items = [r for r in items if domain in r.host]
        if package_name:
            items = [r for r in items if r.package_name == package_name]
        if uid is not None:
            items = [r for r in items if r.uid == uid]
        if process_name:
            items = [r for r in items if r.process_name == process_name]
        return items

    def get_requests_as_dict(self) -> List[Dict[str, Any]]:
        result = []
        for req in self.requests:
            result.append(
                {
                    "url": req.url,
                    "method": req.method,
                    "host": req.host,
                    "path": req.path,
                    "ip": req.ip,
                    "port": req.port,
                    "scheme": req.scheme,
                    "request_time": req.request_time.isoformat() if req.request_time else None,
                    "response_code": req.response_code,
                    "content_type": req.content_type,
                    "request_headers": req.request_headers,
                    "response_headers": req.response_headers,
                    "uid": req.uid,
                    "package_name": req.package_name,
                    "process_name": req.process_name,
                    "source": req.source,
                    "capture_backend": req.capture_backend,
                    "attribution_confidence": req.attribution_confidence,
                }
            )
        return result

    def get_aggregated_requests(self) -> List[Dict[str, Any]]:
        grouped: Dict[tuple, Dict[str, Any]] = {}
        for req in self.requests:
            key = (req.host, req.path, req.method)
            if key not in grouped:
                grouped[key] = {
                    "host": req.host,
                    "path": req.path,
                    "method": req.method,
                    "count": 0,
                    "packages": set(),
                    "sources": set(),
                }
            grouped[key]["count"] += 1
            if req.package_name:
                grouped[key]["packages"].add(req.package_name)
            if req.source:
                grouped[key]["sources"].add(req.source)

        rows: List[Dict[str, Any]] = []
        for item in grouped.values():
            rows.append(
                {
                    "host": item["host"],
                    "path": item["path"],
                    "method": item["method"],
                    "count": item["count"],
                    "packages": sorted(item["packages"]),
                    "sources": sorted(item["sources"]),
                }
            )
        rows.sort(key=lambda x: x["count"], reverse=True)
        return rows

    def get_suspicious_requests(self) -> List[NetworkRequest]:
        return self.requests

    def clear_requests(self) -> None:
        self.requests.clear()
        logger.info("Cleared all captured requests")

    def export_to_json(self) -> str:
        return json.dumps(self.get_requests_as_dict(), indent=2, ensure_ascii=False)

    def analyze_traffic(self) -> Dict[str, Any]:
        total_requests = len(self.requests)
        unique_hosts = set(r.host for r in self.requests)
        unique_ips = set(r.ip for r in self.requests if r.ip)

        response_codes: Dict[int, int] = {}
        methods: Dict[str, int] = {}
        source_counts: Dict[str, int] = defaultdict(int)
        package_counts: Dict[str, int] = defaultdict(int)

        for req in self.requests:
            code = req.response_code
            if code:
                response_codes[code] = response_codes.get(code, 0) + 1
            methods[req.method] = methods.get(req.method, 0) + 1
            source_counts[req.source or "unknown"] += 1
            package_counts[req.package_name or "unknown"] += 1

        return {
            "total_requests": total_requests,
            "unique_hosts": len(unique_hosts),
            "unique_ips": len(unique_ips),
            "response_codes": response_codes,
            "methods": methods,
            "hosts": sorted(list(unique_hosts)),
            "sources": dict(source_counts),
            "packages": dict(package_counts),
            "aggregated": self.get_aggregated_requests()[:100],
        }

    def start(
        self,
        emulator_host: Optional[str] = None,
        emulator_port: Optional[int] = None,
        target_package: Optional[str] = None,
        android_runner: Optional[Any] = None,
    ) -> None:
        """Start the traffic monitor."""
        try:
            self.set_target_app_context(
                target_package=target_package,
                emulator_host=emulator_host,
                emulator_port=emulator_port,
                android_runner=android_runner,
            )

            from .mitmproxy_integration import MitmProxyManager, configure_android_proxy

            self._mitmproxy_manager = MitmProxyManager()

            started = False
            last_error: Optional[Exception] = None
            base_port = self.proxy_port
            for offset in range(5):
                candidate_port = base_port + offset
                try:
                    self._mitmproxy_manager.start_proxy(
                        port=candidate_port,
                        request_callback=self._on_request_captured,
                    )
                    self.proxy_port = candidate_port
                    started = True
                    break
                except Exception as exc:
                    last_error = exc
                    message = str(exc).lower()
                    if "address already in use" in message and offset < 4:
                        logger.warning(
                            "Proxy port %s is busy, retrying with port %s",
                            candidate_port,
                            candidate_port + 1,
                        )
                        continue
                    raise

            if not started and last_error:
                raise last_error

            if emulator_host and emulator_port:
                configure_android_proxy(emulator_host, emulator_port, self.proxy_port)

            self._running = True
            logger.info("Traffic monitor started on port %s", self.proxy_port)

        except Exception as e:
            logger.error("Failed to start traffic monitor: %s", e)
            self._running = True
            logger.warning("Running in passive mode (no actual traffic capture)")

    def _on_request_captured(self, request_data: Dict[str, Any]) -> None:
        self.add_request(request_data)

    def stop(self) -> None:
        if self._mitmproxy_manager:
            try:
                self._mitmproxy_manager.stop_proxy()
            except Exception as e:
                logger.error("Error stopping mitmproxy: %s", e)

        self._running = False
        logger.info("Traffic monitor stopped. Captured %s requests", len(self.requests))

    @property
    def is_running(self) -> bool:
        return self._running
