"""Reusable service layer for batch APK and ZIP uploads."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Callable, Protocol, Sequence
import uuid

from modules.upload_batch.zip_extract import (
    ZipExtractionIssue,
    ZipExtractionLimits,
    extract_apks_from_zip_bytes,
)


APK_CONTENT_TYPE = "application/vnd.android.package-archive"


class UploadStorage(Protocol):
    """Storage surface required by the batch upload service."""

    def generate_apk_path(self, task_id: str, md5: str) -> str:
        """Return the object storage path for an APK."""

    def upload_file(self, object_name: str, data: bytes, content_type: str) -> bool:
        """Upload bytes to object storage."""


class ExistingApkResolver(Protocol):
    """Resolve an existing stored APK object by content hash."""

    def __call__(self, apk_md5: str) -> str | None:
        """Return an existing object storage path if available."""


@dataclass(frozen=True)
class BatchUploadFile:
    """A top-level uploaded file passed into the service."""

    filename: str
    content: bytes
    content_type: str | None = None


@dataclass(frozen=True)
class BatchUploadLimits:
    """Limits enforced by the batch upload service."""

    max_batch_apks: int = 50
    max_apk_size_bytes: int = 500 * 1024 * 1024
    max_zip_size_bytes: int = 500 * 1024 * 1024
    max_total_uncompressed_zip_bytes: int = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class BatchTaskInput:
    """Prepared task input for one accepted APK."""

    task_id: str
    apk_file_name: str
    apk_file_size: int
    apk_md5: str
    apk_storage_path: str
    source_file_name: str
    source_kind: str
    archive_entry_name: str | None = None


@dataclass(frozen=True)
class BatchUploadError:
    """Structured rejection item for one top-level file or ZIP entry."""

    source_file_name: str
    code: str
    message: str
    archive_entry_name: str | None = None


@dataclass(frozen=True)
class BatchUploadResult:
    """Aggregate outcome for a batch upload request."""

    status: str
    submitted_file_count: int
    created_task_count: int
    rejected_count: int
    task_inputs: list[BatchTaskInput]
    errors: list[BatchUploadError]


class BatchUploadService:
    """Prepare batch-uploaded APKs for downstream task creation."""

    def __init__(
        self,
        *,
        storage: UploadStorage,
        existing_apk_resolver: ExistingApkResolver | None = None,
        task_id_factory: Callable[[], str] | None = None,
        limits: BatchUploadLimits | None = None,
    ):
        self.storage = storage
        self.existing_apk_resolver = existing_apk_resolver
        self.task_id_factory = task_id_factory or (lambda: str(uuid.uuid4()))
        self.limits = limits or BatchUploadLimits()

    def prepare_batch(self, files: Sequence[BatchUploadFile]) -> BatchUploadResult:
        """Validate, expand, upload, and summarize a batch upload payload."""
        task_inputs: list[BatchTaskInput] = []
        errors: list[BatchUploadError] = []

        for upload in files:
            filename = upload.filename or ""
            lower_name = filename.lower()

            if lower_name.endswith(".apk"):
                self._collect_direct_apk(upload, task_inputs, errors)
                continue

            if lower_name.endswith(".zip"):
                self._collect_zip(upload, task_inputs, errors)
                continue

            errors.append(
                BatchUploadError(
                    source_file_name=filename,
                    code="unsupported_file_type",
                    message="Only APK and ZIP uploads are supported.",
                )
            )

        return BatchUploadResult(
            status=self._resolve_status(task_inputs, errors),
            submitted_file_count=len(files),
            created_task_count=len(task_inputs),
            rejected_count=len(errors),
            task_inputs=task_inputs,
            errors=errors,
        )

    def _collect_direct_apk(
        self,
        upload: BatchUploadFile,
        task_inputs: list[BatchTaskInput],
        errors: list[BatchUploadError],
    ) -> None:
        prepared = self._prepare_apk(
            apk_file_name=upload.filename,
            apk_bytes=upload.content,
            source_file_name=upload.filename,
            source_kind="apk",
            archive_entry_name=None,
            current_task_count=len(task_inputs),
        )
        if isinstance(prepared, BatchUploadError):
            errors.append(prepared)
            return
        task_inputs.append(prepared)

    def _collect_zip(
        self,
        upload: BatchUploadFile,
        task_inputs: list[BatchTaskInput],
        errors: list[BatchUploadError],
    ) -> None:
        if len(upload.content) > self.limits.max_zip_size_bytes:
            errors.append(
                BatchUploadError(
                    source_file_name=upload.filename,
                    code="zip_file_too_large",
                    message="ZIP upload exceeds the configured size limit.",
                )
            )
            return

        extracted_apks, zip_issues = extract_apks_from_zip_bytes(
            upload.filename,
            upload.content,
            limits=ZipExtractionLimits(
                max_apk_size_bytes=self.limits.max_apk_size_bytes,
                max_total_uncompressed_bytes=self.limits.max_total_uncompressed_zip_bytes,
            ),
        )
        errors.extend(self._map_zip_issues(zip_issues))

        for extracted in extracted_apks:
            prepared = self._prepare_apk(
                apk_file_name=extracted.apk_file_name,
                apk_bytes=extracted.content,
                source_file_name=upload.filename,
                source_kind="zip_apk",
                archive_entry_name=extracted.entry_name,
                current_task_count=len(task_inputs),
            )
            if isinstance(prepared, BatchUploadError):
                errors.append(prepared)
                continue
            task_inputs.append(prepared)

    def _prepare_apk(
        self,
        *,
        apk_file_name: str,
        apk_bytes: bytes,
        source_file_name: str,
        source_kind: str,
        archive_entry_name: str | None,
        current_task_count: int,
    ) -> BatchTaskInput | BatchUploadError:
        if current_task_count >= self.limits.max_batch_apks:
            return BatchUploadError(
                source_file_name=source_file_name,
                archive_entry_name=archive_entry_name,
                code="apk_count_limit_exceeded",
                message="Batch APK count exceeds the configured limit.",
            )

        if len(apk_bytes) > self.limits.max_apk_size_bytes:
            return BatchUploadError(
                source_file_name=source_file_name,
                archive_entry_name=archive_entry_name,
                code="apk_file_too_large",
                message="APK exceeds the configured size limit.",
            )

        apk_md5 = hashlib.md5(apk_bytes).hexdigest()
        task_id = self.task_id_factory()
        storage_path = None
        if self.existing_apk_resolver is not None:
            storage_path = self.existing_apk_resolver(apk_md5)

        if not storage_path:
            storage_path = self.storage.generate_apk_path(task_id, apk_md5)
            uploaded = self.storage.upload_file(
                object_name=storage_path,
                data=apk_bytes,
                content_type=APK_CONTENT_TYPE,
            )
            if not uploaded:
                return BatchUploadError(
                    source_file_name=source_file_name,
                    archive_entry_name=archive_entry_name,
                    code="storage_upload_failed",
                    message="Failed to upload APK to object storage.",
                )

        return BatchTaskInput(
            task_id=task_id,
            apk_file_name=apk_file_name,
            apk_file_size=len(apk_bytes),
            apk_md5=apk_md5,
            apk_storage_path=storage_path,
            source_file_name=source_file_name,
            source_kind=source_kind,
            archive_entry_name=archive_entry_name,
        )

    @staticmethod
    def _map_zip_issues(issues: list[ZipExtractionIssue]) -> list[BatchUploadError]:
        return [
            BatchUploadError(
                source_file_name=issue.archive_name,
                archive_entry_name=issue.archive_entry_name,
                code=issue.code,
                message=issue.message,
            )
            for issue in issues
        ]

    @staticmethod
    def _resolve_status(
        task_inputs: list[BatchTaskInput],
        errors: list[BatchUploadError],
    ) -> str:
        if task_inputs and errors:
            return "partial_success"
        if task_inputs:
            return "success"
        return "failed"
