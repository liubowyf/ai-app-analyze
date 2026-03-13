"""Passive observation source abstractions used by the redroid tcpdump backend."""

from __future__ import annotations

import logging
import re
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Iterable, Protocol

from .observation_models import PASSIVE_CAPTURE_MODE

logger = logging.getLogger(__name__)

_CONNECT_RE = re.compile(r"\bCONNECT\s+([A-Za-z0-9._-]+)(?::(\d+))?\s+HTTP/1\.[01]\b", re.IGNORECASE)
_HOST_RE = re.compile(r"^\s*Host:\s*([A-Za-z0-9._-]+)(?::(\d+))?\s*$", re.IGNORECASE)
_DNS_QUERY_RE = re.compile(r"\b(?:A\?|AAAA\?)\s+([A-Za-z0-9._-]+)\.?$")
_DNS_ANSWER_RE = re.compile(r"\b([A-Za-z0-9._-]+)\.\s+\d+\s+IN\s+A\s+((?:\d{1,3}\.){3}\d{1,3})\b")
_TCP_ENDPOINT_RE = re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3})\.(\d+)\s*>\s*((?:\d{1,3}\.){3}\d{1,3})\.(\d+)")


class ObservationSourceAdapter(Protocol):
    def start(self, emit: Callable[[dict[str, Any]], None], **kwargs: Any) -> None:
        """Begin emitting passive observation events."""

    def stop(self) -> None:
        """Stop emitting passive observation events."""


@dataclass
class ReplayObservationSource:
    """Simple in-memory source useful for tests and smoke checks."""

    events: Iterable[dict[str, Any]] = field(default_factory=list)
    started: bool = False

    def start(self, emit: Callable[[dict[str, Any]], None], **kwargs: Any) -> None:
        del kwargs
        self.started = True
        for event in list(self.events):
            emit(event)

    def stop(self) -> None:
        self.started = False


class ProxyConnectTcpdumpObservationSource:
    """Parse emulator-side tcpdump output into domain/IP observations."""

    def __init__(self, proxy_port: int = 3128):
        self.proxy_port = int(proxy_port or 3128)
        self._process: subprocess.Popen[str] | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._emit: Callable[[dict[str, Any]], None] | None = None
        self._ip_cache: dict[str, tuple[float, str | None]] = {}
        self._last_connect_domain: str | None = None
        self._last_connect_at = 0.0
        self._recent_dns_queries: dict[str, float] = {}

    def _build_command(self, emulator_host: str, emulator_port: int) -> list[str]:
        device = f"{emulator_host}:{emulator_port}"
        tcpdump_cmd = (
            f"tcpdump -i any -l -A -n -s 0 'tcp dst port {self.proxy_port} or tcp src port {self.proxy_port} or port 53'"
        )
        return ["adb", "-s", device, "shell", "sh", "-c", tcpdump_cmd]

    def _resolve_ip(self, domain: str) -> str | None:
        cached = self._ip_cache.get(domain)
        now = time.monotonic()
        if cached and (now - cached[0]) < 300:
            return cached[1]

        resolved_ip = None
        try:
            for family, _, _, _, sockaddr in socket.getaddrinfo(domain, None, type=socket.SOCK_STREAM):
                if family in (socket.AF_INET, socket.AF_INET6) and sockaddr:
                    resolved_ip = sockaddr[0]
                    break
        except Exception:
            resolved_ip = None

        self._ip_cache[domain] = (now, resolved_ip)
        return resolved_ip

    @staticmethod
    def _normalize_domain(raw: str | None) -> str | None:
        if not raw:
            return None
        value = raw.strip().strip("[]").rstrip(".").lower()
        if value in {"null", "none", "unknown"}:
            return None
        return value or None

    def _build_event(
        self,
        *,
        domain: str | None = None,
        ip: str | None = None,
        port_value: str | int | None = None,
        source_type: str,
        method: str = "UNKNOWN",
        protocol: str = "unknown",
        transport: str = "tcp",
    ) -> dict[str, Any]:
        normalized_domain = self._normalize_domain(domain)
        resolved_ip = ip or (self._resolve_ip(normalized_domain) if normalized_domain else None)
        now = datetime.utcnow()
        return {
            "domain": normalized_domain,
            "ip": resolved_ip,
            "port": int(port_value) if port_value not in (None, "") else None,
            "timestamp": now,
            "first_seen_at": now,
            "last_seen_at": now,
            "hit_count": 1,
            "source_type": source_type,
            "transport": transport,
            "protocol": protocol,
            "method": method,
            "capture_mode": PASSIVE_CAPTURE_MODE,
        }

    def _parse_tcpdump_text(self, text: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            connect_match = _CONNECT_RE.search(line)
            if connect_match:
                domain, port_value = connect_match.groups()
                event = self._build_event(
                    domain=domain,
                    port_value=port_value,
                    source_type="connect",
                    method="CONNECT",
                    protocol="https_tunnel",
                )
                events.append(event)
                self._last_connect_domain = event["domain"]
                self._last_connect_at = time.monotonic()
                continue

            host_match = _HOST_RE.search(line)
            if host_match:
                domain, port_value = host_match.groups()
                normalized = self._normalize_domain(domain)
                if (
                    normalized
                    and normalized == self._last_connect_domain
                    and (time.monotonic() - self._last_connect_at) < 1.0
                ):
                    continue
                events.append(
                    self._build_event(
                        domain=domain,
                        port_value=port_value,
                        source_type="host",
                        method="UNKNOWN",
                        protocol="http_or_proxy",
                    )
                )
                continue

            dns_query = _DNS_QUERY_RE.search(line)
            if dns_query:
                queried = self._normalize_domain(dns_query.group(1))
                if queried:
                    self._recent_dns_queries[queried] = time.monotonic()
                    events.append(
                        self._build_event(
                            domain=queried,
                            source_type="dns_query",
                            protocol="dns",
                            transport="udp",
                        )
                    )
                continue

            dns_answer = _DNS_ANSWER_RE.search(line)
            if dns_answer:
                domain, ip = dns_answer.groups()
                events.append(
                    self._build_event(
                        domain=domain,
                        ip=ip,
                        source_type="dns_answer",
                        protocol="dns",
                        transport="udp",
                    )
                )
                continue

            tcp_match = _TCP_ENDPOINT_RE.search(line)
            if tcp_match:
                src_ip, src_port, dst_ip, dst_port = tcp_match.groups()
                if int(dst_port) != self.proxy_port and int(src_port) != self.proxy_port:
                    continue
                events.append(
                    self._build_event(
                        ip=dst_ip if int(dst_port) == self.proxy_port else src_ip,
                        port_value=dst_port if int(dst_port) == self.proxy_port else src_port,
                        source_type="tcp_connect",
                        protocol="tcp",
                        transport="tcp",
                    )
                )
        return events

    def _reader_loop(self) -> None:
        if not self._process or not self._process.stdout or not self._emit:
            return
        try:
            for line in self._process.stdout:
                if self._stop_event.is_set():
                    break
                for event in self._parse_tcpdump_text(line):
                    self._emit(event)
        except Exception as exc:
            logger.warning("Passive tcpdump source reader stopped unexpectedly: %s", exc)

    def start(self, emit: Callable[[dict[str, Any]], None], **kwargs: Any) -> None:
        emulator_host = kwargs.get("emulator_host")
        emulator_port = kwargs.get("emulator_port")
        if not emulator_host or not emulator_port:
            logger.warning("Passive tcpdump source skipped: emulator target missing")
            return

        self._emit = emit
        self._stop_event.clear()
        command = self._build_command(str(emulator_host), int(emulator_port))
        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                errors="ignore",
            )
        except Exception as exc:
            logger.warning("Passive tcpdump source unavailable for %s:%s: %s", emulator_host, emulator_port, exc)
            self._process = None
            return
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=2)
        self._process = None
        self._reader_thread = None
