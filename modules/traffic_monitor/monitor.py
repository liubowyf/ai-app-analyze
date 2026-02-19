"""Traffic Monitor module for network traffic analysis."""
import json
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

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


class TrafficMonitor:
    """Network traffic monitor using mitmproxy."""

    def __init__(self):
        """Initialize traffic monitor."""
        self.requests: List[NetworkRequest] = []
        self.whitelist_rules: List[str] = []
        self._running = False

    def set_whitelist(self, domains: List[str]) -> None:
        """
        Set whitelist domains to filter out.

        Args:
            domains: List of domain patterns (supports wildcard *)
        """
        self.whitelist_rules = domains
        logger.info(f"Set whitelist with {len(domains)} rules")

    def is_whitelisted(self, host: str) -> bool:
        """
        Check if host is whitelisted.

        Args:
            host: Hostname to check

        Returns:
            True if whitelisted
        """
        import fnmatch
        for rule in self.whitelist_rules:
            if fnmatch.fnmatch(host, rule):
                return True
        return False

    def add_request(self, request_data: Dict[str, Any]) -> None:
        """
        Add a network request to the monitor.

        Args:
            request_data: Request data from mitmproxy
        """
        try:
            request = NetworkRequest(
                url=request_data.get("url", ""),
                method=request_data.get("method", "GET"),
                host=request_data.get("host", ""),
                path=request_data.get("path", "/"),
                ip=request_data.get("ip"),
                port=request_data.get("port", 80),
                scheme=request_data.get("scheme", "https"),
                request_time=datetime.fromisoformat(
                    request_data.get("request_time", datetime.now().isoformat())
                ),
                response_code=request_data.get("response_code"),
                content_type=request_data.get("content_type"),
                request_headers=request_data.get("request_headers", {}),
                response_headers=request_data.get("response_headers", {}),
                request_body=request_data.get("request_body"),
                response_body=request_data.get("response_body"),
            )

            # Skip whitelisted hosts
            if self.is_whitelisted(request.host):
                logger.debug(f"Skipping whitelisted: {request.host}")
                return

            self.requests.append(request)
            logger.info(f"Captured: {request.method} {request.host}{request.path}")

        except Exception as e:
            logger.error(f"Failed to add request: {e}")

    def get_requests(self, domain: Optional[str] = None) -> List[NetworkRequest]:
        """
        Get captured network requests.

        Args:
            domain: Optional domain filter

        Returns:
            List of network requests
        """
        if domain:
            return [r for r in self.requests if domain in r.host]
        return self.requests

    def get_suspicious_requests(self) -> List[NetworkRequest]:
        """
        Get suspicious network requests (not whitelisted).

        Returns:
            List of suspicious requests
        """
        return self.requests

    def clear_requests(self) -> None:
        """Clear all captured requests."""
        self.requests.clear()
        logger.info("Cleared all captured requests")

    def export_to_json(self) -> str:
        """
        Export requests to JSON.

        Returns:
            JSON string
        """
        data = []
        for req in self.requests:
            data.append({
                "url": req.url,
                "method": req.method,
                "host": req.host,
                "ip": req.ip,
                "port": req.port,
                "response_code": req.response_code,
                "request_time": req.request_time.isoformat(),
            })
        return json.dumps(data, indent=2)

    def analyze_traffic(self) -> Dict[str, Any]:
        """
        Analyze captured traffic.

        Returns:
            Analysis results
        """
        total_requests = len(self.requests)
        unique_hosts = set(r.host for r in self.requests)
        unique_ips = set(r.ip for r in self.requests if r.ip)

        # Count by response code
        response_codes = {}
        for req in self.requests:
            code = req.response_code
            if code:
                response_codes[code] = response_codes.get(code, 0) + 1

        # Count by method
        methods = {}
        for req in self.requests:
            methods[req.method] = methods.get(req.method, 0) + 1

        return {
            "total_requests": total_requests,
            "unique_hosts": len(unique_hosts),
            "unique_ips": len(unique_ips),
            "response_codes": response_codes,
            "methods": methods,
            "hosts": sorted(list(unique_hosts)),
        }

    def start(self) -> None:
        """Start the traffic monitor."""
        self._running = True
        logger.info("Traffic monitor started")

    def stop(self) -> None:
        """Stop the traffic monitor."""
        self._running = False
        logger.info("Traffic monitor stopped")

    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running
