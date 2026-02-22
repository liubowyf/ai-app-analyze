"""Filter policy for network request noise reduction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence


DEFAULT_SYSTEM_DOMAIN_PATTERNS = [
    "connectivitycheck.gstatic.com",
    "play.googleapis.com",
    "www.google.com",
    "clients3.google.com",
    "mtalk.google.com",
    "android.clients.google.com",
]

DEFAULT_SYSTEM_PROCESS_PATTERNS = [
    "com.android.",
    "com.google.android.",
    "system_server",
]


@dataclass
class TrafficFilterPolicy:
    """Configurable filter policy for captured requests."""

    strict_target_package: bool = True
    include_packages: List[str] = field(default_factory=list)
    include_uids: List[int] = field(default_factory=list)
    exclude_domains: List[str] = field(default_factory=lambda: list(DEFAULT_SYSTEM_DOMAIN_PATTERNS))
    exclude_process_prefixes: List[str] = field(default_factory=lambda: list(DEFAULT_SYSTEM_PROCESS_PATTERNS))

    def should_drop(
        self,
        host: str,
        path: str,
        package_name: Optional[str],
        uid: Optional[int],
        process_name: Optional[str],
        target_package: Optional[str],
    ) -> bool:
        host_l = (host or "").lower()
        path_l = (path or "").lower()
        process_l = (process_name or "").lower()

        for blocked_host in self.exclude_domains:
            blocked_l = blocked_host.lower()
            if host_l == blocked_l or host_l.endswith(f".{blocked_l}"):
                if "generate_204" in path_l or "gen_204" in path_l or blocked_l in host_l:
                    return True

        for prefix in self.exclude_process_prefixes:
            if process_l.startswith(prefix.lower()):
                return True

        if self.include_packages and (package_name not in self.include_packages):
            return True

        if self.include_uids and (uid not in self.include_uids):
            return True

        if self.strict_target_package and target_package:
            return package_name != target_package

        return False

    @classmethod
    def merge_exclusions(cls, base: "TrafficFilterPolicy", domains: Sequence[str]) -> "TrafficFilterPolicy":
        merged = list(base.exclude_domains)
        for domain in domains:
            value = (domain or "").strip()
            if value and value not in merged:
                merged.append(value)
        base.exclude_domains = merged
        return base
