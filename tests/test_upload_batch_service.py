"""Tests for the batch APK upload service layer."""

from __future__ import annotations

import hashlib
import io
import itertools
import zipfile

from modules.upload_batch.service import (
    BatchUploadFile,
    BatchUploadLimits,
    BatchUploadService,
)
from modules.upload_batch.zip_extract import (
    ZipExtractionLimits,
    extract_apks_from_zip_bytes,
)


class FakeStorage:
    """Simple in-memory storage fake for upload batch tests."""

    def __init__(self, *, failing_payloads: set[bytes] | None = None):
        self.failing_payloads = failing_payloads or set()
        self.uploads: list[dict[str, object]] = []

    @staticmethod
    def generate_apk_path(task_id: str, md5: str) -> str:
        return f"apks/{task_id}/{md5}.apk"

    def upload_file(self, object_name: str, data: bytes, content_type: str) -> bool:
        self.uploads.append(
            {
                "object_name": object_name,
                "data": data,
                "content_type": content_type,
            }
        )
        return data not in self.failing_payloads


def build_zip(entries: dict[str, bytes]) -> bytes:
    """Build an in-memory zip archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def make_service(
    storage: FakeStorage | None = None,
    *,
    limits: BatchUploadLimits | None = None,
) -> tuple[BatchUploadService, FakeStorage]:
    storage = storage or FakeStorage()
    task_ids = (f"task-{index}" for index in itertools.count(1))
    service = BatchUploadService(
        storage=storage,
        task_id_factory=lambda: next(task_ids),
        limits=limits or BatchUploadLimits(),
    )
    return service, storage


def test_prepare_batch_creates_one_task_input_per_direct_apk():
    service, storage = make_service(
        limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=64, max_zip_size_bytes=256)
    )

    result = service.prepare_batch(
        [
            BatchUploadFile(filename="alpha.apk", content=b"alpha"),
            BatchUploadFile(filename="beta.apk", content=b"beta"),
        ]
    )

    assert result.status == "success"
    assert result.created_task_count == 2
    assert result.rejected_count == 0
    assert [item.task_id for item in result.task_inputs] == ["task-1", "task-2"]
    assert [item.apk_file_name for item in result.task_inputs] == ["alpha.apk", "beta.apk"]
    assert [item.source_kind for item in result.task_inputs] == ["apk", "apk"]
    assert [item.archive_entry_name for item in result.task_inputs] == [None, None]
    assert [item.apk_md5 for item in result.task_inputs] == [
        hashlib.md5(b"alpha").hexdigest(),
        hashlib.md5(b"beta").hexdigest(),
    ]
    assert len(storage.uploads) == 2


def test_prepare_batch_expands_zip_and_filters_non_apk_entries():
    service, _ = make_service(
        limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=64, max_zip_size_bytes=512)
    )
    archive_bytes = build_zip(
        {
            "apps/one.apk": b"one",
            "apps/two.apk": b"two",
            "docs/readme.txt": b"ignore me",
        }
    )

    result = service.prepare_batch([BatchUploadFile(filename="bundle.zip", content=archive_bytes)])

    assert result.status == "partial_success"
    assert result.created_task_count == 2
    assert [item.apk_file_name for item in result.task_inputs] == ["one.apk", "two.apk"]
    assert [item.archive_entry_name for item in result.task_inputs] == ["apps/one.apk", "apps/two.apk"]
    assert result.errors[0].code == "unsupported_file_type"
    assert result.errors[0].source_file_name == "bundle.zip"
    assert result.errors[0].archive_entry_name == "docs/readme.txt"


def test_prepare_batch_rejects_top_level_unsupported_files_but_keeps_valid_apks():
    service, _ = make_service(
        limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=64, max_zip_size_bytes=256)
    )

    result = service.prepare_batch(
        [
            BatchUploadFile(filename="valid.apk", content=b"apk"),
            BatchUploadFile(filename="notes.txt", content=b"text"),
        ]
    )

    assert result.status == "partial_success"
    assert result.created_task_count == 1
    assert result.task_inputs[0].apk_file_name == "valid.apk"
    assert result.errors[0].code == "unsupported_file_type"
    assert result.errors[0].source_file_name == "notes.txt"
    assert result.errors[0].archive_entry_name is None


def test_prepare_batch_rejects_nested_zip_entries_without_failing_valid_apks():
    service, _ = make_service(
        limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=64, max_zip_size_bytes=512)
    )
    nested_zip = build_zip({"inner.apk": b"inner"})
    archive_bytes = build_zip({"safe.apk": b"safe", "nested/child.zip": nested_zip})

    result = service.prepare_batch([BatchUploadFile(filename="bundle.zip", content=archive_bytes)])

    assert result.status == "partial_success"
    assert result.created_task_count == 1
    assert result.task_inputs[0].apk_file_name == "safe.apk"
    assert result.errors[0].code == "nested_zip_not_supported"
    assert result.errors[0].archive_entry_name == "nested/child.zip"


def test_prepare_batch_enforces_apk_count_limit_with_partial_success():
    service, _ = make_service(
        limits=BatchUploadLimits(max_batch_apks=1, max_apk_size_bytes=64, max_zip_size_bytes=256)
    )

    result = service.prepare_batch(
        [
            BatchUploadFile(filename="first.apk", content=b"one"),
            BatchUploadFile(filename="second.apk", content=b"two"),
        ]
    )

    assert result.status == "partial_success"
    assert result.created_task_count == 1
    assert result.task_inputs[0].apk_file_name == "first.apk"
    assert result.errors[0].code == "apk_count_limit_exceeded"
    assert result.errors[0].source_file_name == "second.apk"


def test_prepare_batch_enforces_size_limit_with_partial_success():
    service, _ = make_service(
        limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=3, max_zip_size_bytes=256)
    )

    result = service.prepare_batch(
        [
            BatchUploadFile(filename="small.apk", content=b"ok"),
            BatchUploadFile(filename="large.apk", content=b"toolarge"),
        ]
    )

    assert result.status == "partial_success"
    assert result.created_task_count == 1
    assert result.task_inputs[0].apk_file_name == "small.apk"
    assert result.errors[0].code == "apk_file_too_large"
    assert result.errors[0].source_file_name == "large.apk"


def test_extract_apks_from_zip_bytes_rejects_unsafe_paths():
    archive_bytes = build_zip(
        {
            "../escape.apk": b"escape",
            "/absolute.apk": b"absolute",
            "safe/app.apk": b"safe",
        }
    )

    extracted, errors = extract_apks_from_zip_bytes(
        "unsafe.zip",
        archive_bytes,
        limits=ZipExtractionLimits(max_apk_size_bytes=64, max_total_uncompressed_bytes=256),
    )

    assert [item.entry_name for item in extracted] == ["safe/app.apk"]
    assert [item.apk_file_name for item in extracted] == ["app.apk"]
    assert [error.code for error in errors] == ["unsafe_zip_entry", "unsafe_zip_entry"]
    assert [error.archive_entry_name for error in errors] == ["../escape.apk", "/absolute.apk"]


def test_prepare_batch_reuses_existing_storage_path_for_same_md5():
    storage = FakeStorage()
    task_ids = (f"task-{index}" for index in itertools.count(1))
    service = BatchUploadService(
        storage=storage,
        existing_apk_resolver=lambda apk_md5: "apks/existing-task/reused.apk"
        if apk_md5 == hashlib.md5(b"alpha").hexdigest()
        else None,
        task_id_factory=lambda: next(task_ids),
        limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=64, max_zip_size_bytes=256),
    )

    result = service.prepare_batch([BatchUploadFile(filename="alpha.apk", content=b"alpha")])

    assert result.status == "success"
    assert result.created_task_count == 1
    assert result.task_inputs[0].task_id == "task-1"
    assert result.task_inputs[0].apk_storage_path == "apks/existing-task/reused.apk"
    assert storage.uploads == []
