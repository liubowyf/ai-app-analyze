"""File helpers for host-agent artifacts."""

from __future__ import annotations

from pathlib import Path


ALLOWED_CAPTURE_FILES = {"tcpdump.log", "conn.log", "dns.log", "ssl.log", "http.log"}
ROOT_CAPTURE_FILES = {"tcpdump.log"}
ZEEK_CAPTURE_FILES = ALLOWED_CAPTURE_FILES - ROOT_CAPTURE_FILES


class CaptureFileService:
    """Enforce fixed capture artifact file access."""

    def ensure_allowed_name(self, name: str) -> str:
        cleaned = str(name or "").strip()
        if cleaned not in ALLOWED_CAPTURE_FILES:
            raise FileNotFoundError("artifact_not_found")
        return cleaned

    def resolve_allowed_path(self, capture_dir: Path, name: str) -> Path:
        cleaned = self.ensure_allowed_name(name)
        if cleaned in ROOT_CAPTURE_FILES:
            return capture_dir / cleaned
        if cleaned in ZEEK_CAPTURE_FILES:
            return capture_dir / "zeek" / cleaned
        raise FileNotFoundError("artifact_not_found")

    def list_allowed_files(self, capture_dir: Path) -> list[dict[str, int | str]]:
        items: list[dict[str, int | str]] = []
        for name in sorted(ALLOWED_CAPTURE_FILES):
            path = self.resolve_allowed_path(capture_dir, name)
            if path.exists() and path.is_file():
                items.append({"name": name, "size": path.stat().st_size})
        return items

    def read_allowed_file(self, capture_dir: Path, name: str) -> bytes:
        path = self.resolve_allowed_path(capture_dir, name)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError("artifact_not_found")
        return path.read_bytes()
