"""ZIP extraction helpers for batch APK uploads."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
import zipfile


@dataclass(frozen=True)
class ZipExtractionLimits:
    """Safety limits for ZIP processing."""

    max_apk_size_bytes: int = 500 * 1024 * 1024
    max_total_uncompressed_bytes: int = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class ZipExtractedApk:
    """An APK entry materialized from a ZIP archive."""

    archive_name: str
    entry_name: str
    apk_file_name: str
    content: bytes
    file_size: int


@dataclass(frozen=True)
class ZipExtractionIssue:
    """A rejected ZIP entry or archive-level ZIP validation error."""

    archive_name: str
    code: str
    message: str
    archive_entry_name: str | None = None


def _normalize_entry_name(entry_name: str) -> str:
    return entry_name.replace("\\", "/")


def _is_safe_entry_name(entry_name: str) -> bool:
    normalized = _normalize_entry_name(entry_name)
    if not normalized or normalized.startswith("/"):
        return False

    path = PurePosixPath(normalized)
    if any(part in ("", "..") for part in path.parts):
        return False

    first_part = path.parts[0] if path.parts else ""
    return not first_part.endswith(":")


def extract_apks_from_zip_bytes(
    zip_filename: str,
    zip_bytes: bytes,
    *,
    limits: ZipExtractionLimits | None = None,
) -> tuple[list[ZipExtractedApk], list[ZipExtractionIssue]]:
    """Extract APK entries from a ZIP archive without writing to disk."""
    limits = limits or ZipExtractionLimits()
    extracted: list[ZipExtractedApk] = []
    issues: list[ZipExtractionIssue] = []

    try:
        archive = zipfile.ZipFile(BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return (
            [],
            [
                ZipExtractionIssue(
                    archive_name=zip_filename,
                    code="invalid_zip",
                    message="Uploaded ZIP archive is invalid.",
                )
            ],
        )

    total_uncompressed_bytes = 0

    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue

            normalized_name = _normalize_entry_name(info.filename)

            if not _is_safe_entry_name(normalized_name):
                issues.append(
                    ZipExtractionIssue(
                        archive_name=zip_filename,
                        archive_entry_name=normalized_name,
                        code="unsafe_zip_entry",
                        message="ZIP entry path is unsafe.",
                    )
                )
                continue

            lower_name = normalized_name.lower()

            if lower_name.endswith(".zip"):
                issues.append(
                    ZipExtractionIssue(
                        archive_name=zip_filename,
                        archive_entry_name=normalized_name,
                        code="nested_zip_not_supported",
                        message="Nested ZIP entries are not supported.",
                    )
                )
                continue

            if not lower_name.endswith(".apk"):
                issues.append(
                    ZipExtractionIssue(
                        archive_name=zip_filename,
                        archive_entry_name=normalized_name,
                        code="unsupported_file_type",
                        message="Only APK entries are supported in ZIP uploads.",
                    )
                )
                continue

            if info.file_size > limits.max_apk_size_bytes:
                issues.append(
                    ZipExtractionIssue(
                        archive_name=zip_filename,
                        archive_entry_name=normalized_name,
                        code="apk_file_too_large",
                        message="APK entry exceeds the configured size limit.",
                    )
                )
                continue

            total_uncompressed_bytes += info.file_size
            if total_uncompressed_bytes > limits.max_total_uncompressed_bytes:
                issues.append(
                    ZipExtractionIssue(
                        archive_name=zip_filename,
                        archive_entry_name=normalized_name,
                        code="zip_uncompressed_size_limit_exceeded",
                        message="ZIP archive exceeds the configured uncompressed size limit.",
                    )
                )
                break

            entry_bytes = archive.read(info)
            extracted.append(
                ZipExtractedApk(
                    archive_name=zip_filename,
                    entry_name=normalized_name,
                    apk_file_name=PurePosixPath(normalized_name).name,
                    content=entry_bytes,
                    file_size=len(entry_bytes),
                )
            )

    return extracted, issues
