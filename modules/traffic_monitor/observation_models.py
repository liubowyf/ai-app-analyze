"""Shared passive observation dataclasses and serialization helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional


PASSIVE_CAPTURE_MODE = "redroid_zeek"


def parse_observation_timestamp(value: Any) -> datetime:
    """Parse heterogeneous timestamp values into a datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except Exception:
            return datetime.utcnow()
    return datetime.utcnow()


@dataclass
class NetworkObservation:
    """Aggregated passive observation row for one endpoint/source tuple."""

    domain: Optional[str] = None
    ip: Optional[str] = None
    port: Optional[int] = None
    source_type: str = "unknown"
    transport: str = "unknown"
    protocol: str = "unknown"
    first_seen_at: datetime = field(default_factory=datetime.utcnow)
    last_seen_at: datetime = field(default_factory=datetime.utcnow)
    hit_count: int = 1
    uid: Optional[int] = None
    package_name: Optional[str] = None
    process_name: Optional[str] = None
    attribution_confidence: float = 0.0
    attribution_tier: str = "primary"
    capture_mode: str = PASSIVE_CAPTURE_MODE
    method: str = "UNKNOWN"
    url: Optional[str] = None
    path: Optional[str] = None
    scheme: Optional[str] = None
    response_code: Optional[int] = None
    content_type: Optional[str] = None
    request_headers: Dict[str, str] = field(default_factory=dict)
    response_headers: Dict[str, str] = field(default_factory=dict)
    request_body: Optional[str] = None
    response_body: Optional[str] = None

    @property
    def host(self) -> str:
        return self.domain or ""

    @property
    def source(self) -> str:
        return self.source_type

    @property
    def request_time(self) -> datetime:
        return self.first_seen_at

    @property
    def capture_backend(self) -> str:
        return self.capture_mode

    def to_dict(self) -> Dict[str, Any]:
        """Serialize one observation with legacy aliases preserved."""
        first_seen = self.first_seen_at.isoformat() if self.first_seen_at else None
        last_seen = self.last_seen_at.isoformat() if self.last_seen_at else None
        return {
            "url": self.url,
            "method": self.method,
            "domain": self.domain,
            "host": self.host,
            "path": self.path,
            "ip": self.ip,
            "port": self.port,
            "scheme": self.scheme,
            "request_time": first_seen,
            "first_seen_at": first_seen,
            "last_seen_at": last_seen,
            "hit_count": int(self.hit_count or 0),
            "response_code": self.response_code,
            "content_type": self.content_type,
            "request_headers": self.request_headers,
            "response_headers": self.response_headers,
            "request_body": self.request_body,
            "response_body": self.response_body,
            "uid": self.uid,
            "package_name": self.package_name,
            "process_name": self.process_name,
            "source": self.source,
            "source_type": self.source_type,
            "transport": self.transport,
            "protocol": self.protocol,
            "capture_mode": self.capture_mode,
            "capture_backend": self.capture_backend,
            "attribution_confidence": self.attribution_confidence,
            "attribution_tier": self.attribution_tier,
        }

class NetworkRequest(NetworkObservation):
    """Legacy constructor shim kept for modules that still instantiate NetworkRequest directly."""

    def __init__(self, host: Optional[str] = None, request_time: Optional[datetime] = None, **kwargs: Any):
        if "domain" not in kwargs and host is not None:
            kwargs["domain"] = host
        if "first_seen_at" not in kwargs and request_time is not None:
            kwargs["first_seen_at"] = request_time
        if "last_seen_at" not in kwargs and request_time is not None:
            kwargs["last_seen_at"] = request_time
        super().__init__(**kwargs)
