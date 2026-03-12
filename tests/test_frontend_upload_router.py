"""Tests for the frontend batch upload router."""

from __future__ import annotations

import importlib
import io
import itertools
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.database import Base
from models.task import Task, TaskPriority, TaskStatus
from modules.upload_batch.service import BatchUploadLimits, BatchUploadService as RealBatchUploadService


class FakeStorage:
    """In-memory storage fake used by the upload router tests."""

    def __init__(self):
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
        return True


def build_zip(entries: dict[str, bytes]) -> bytes:
    """Create an in-memory ZIP archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.fixture
def frontend_upload_client() -> tuple[TestClient, sessionmaker]:
    """Create a frontend test client backed by in-memory SQLite."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with patch("api.main.Base") as mock_base, patch("api.main.engine") as mock_engine:
        mock_base.metadata = MagicMock()
        api_main = importlib.import_module("api.main")

    from api.routers.frontend import get_db

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    api_main.app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(api_main.app) as client:
            yield client, testing_session_local
    finally:
        api_main.app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def service_factory(storage: FakeStorage, *, limits: BatchUploadLimits):
    """Build a deterministic batch service factory for route tests."""
    task_ids = (f"task-upload-{index}" for index in itertools.count(1))

    def _factory(*args, **kwargs):
        return RealBatchUploadService(
            storage=storage,
            existing_apk_resolver=kwargs.get("existing_apk_resolver"),
            task_id_factory=lambda: next(task_ids),
            limits=limits,
        )

    return _factory


class TestFrontendUploadRouter:
    """Behavioral tests for POST /api/v1/frontend/tasks/upload."""

    def test_upload_route_creates_multiple_tasks_for_multiple_apks(
        self,
        frontend_upload_client: tuple[TestClient, sessionmaker],
    ):
        """Multiple direct APK uploads should create multiple queued tasks."""
        client, session_local = frontend_upload_client
        fake_storage = FakeStorage()

        with patch("api.routers.frontend.BatchUploadService", side_effect=service_factory(
            fake_storage,
            limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=64, max_zip_size_bytes=512),
        )), patch("api.routers.frontend.enqueue_task", return_value=True) as mock_enqueue:
            response = client.post(
                "/api/v1/frontend/tasks/upload",
                files=[
                    ("files", ("alpha.apk", b"alpha", "application/vnd.android.package-archive")),
                    ("files", ("beta.apk", b"beta", "application/vnd.android.package-archive")),
                ],
            )

        assert response.status_code == 200
        data = response.json()
        assert data["accepted_files"] == ["alpha.apk", "beta.apk"]
        assert data["rejected_files"] == []
        assert data["extracted_apk_count"] == 0
        assert data["message"] == "成功创建 2 个任务。"
        assert [item["id"] for item in data["created_tasks"]] == [
            "task-upload-1",
            "task-upload-2",
        ]
        assert all(item["status"] == "pending" for item in data["created_tasks"])
        assert all(item["risk_level"] == "unknown" for item in data["created_tasks"])
        assert all(item["report_ready"] is False for item in data["created_tasks"])

        db = session_local()
        try:
            tasks = db.query(Task).order_by(Task.id.asc()).all()
            assert [task.id for task in tasks] == ["task-upload-1", "task-upload-2"]
            assert all(task.priority == TaskPriority.BATCH for task in tasks)
            assert all(task.status == TaskStatus.PENDING for task in tasks)
        finally:
            db.close()

        assert len(fake_storage.uploads) == 2
        assert mock_enqueue.call_count == 2

    def test_upload_route_expands_zip_and_returns_created_tasks(
        self,
        frontend_upload_client: tuple[TestClient, sessionmaker],
    ):
        """ZIP uploads should expand APKs and expose them as created tasks."""
        client, session_local = frontend_upload_client
        fake_storage = FakeStorage()
        archive_bytes = build_zip(
            {
                "apps/one.apk": b"one",
                "apps/two.apk": b"two",
            }
        )

        with patch("api.routers.frontend.BatchUploadService", side_effect=service_factory(
            fake_storage,
            limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=64, max_zip_size_bytes=512),
        )), patch("api.routers.frontend.enqueue_task", return_value=True):
            response = client.post(
                "/api/v1/frontend/tasks/upload",
                files=[
                    ("files", ("bundle.zip", archive_bytes, "application/zip")),
                ],
            )

        assert response.status_code == 200
        data = response.json()
        assert data["accepted_files"] == ["one.apk", "two.apk"]
        assert data["rejected_files"] == []
        assert data["extracted_apk_count"] == 2
        assert data["message"] == "成功创建 2 个任务。"
        assert [item["apk_file_name"] for item in data["created_tasks"]] == [
            "one.apk",
            "two.apk",
        ]

        db = session_local()
        try:
            assert db.query(Task).count() == 2
        finally:
            db.close()

    def test_upload_route_reports_rejected_files_for_invalid_and_oversized_inputs(
        self,
        frontend_upload_client: tuple[TestClient, sessionmaker],
    ):
        """Invalid top-level files and oversized APKs should be surfaced as rejected files."""
        client, session_local = frontend_upload_client
        fake_storage = FakeStorage()

        with patch("api.routers.frontend.BatchUploadService", side_effect=service_factory(
            fake_storage,
            limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=4, max_zip_size_bytes=512),
        )), patch("api.routers.frontend.enqueue_task", return_value=True):
            response = client.post(
                "/api/v1/frontend/tasks/upload",
                files=[
                    ("files", ("valid.apk", b"ok", "application/vnd.android.package-archive")),
                    ("files", ("notes.txt", b"text", "text/plain")),
                    ("files", ("too-large.apk", b"oversized", "application/vnd.android.package-archive")),
                ],
            )

        assert response.status_code == 200
        data = response.json()
        assert data["accepted_files"] == ["valid.apk"]
        assert data["extracted_apk_count"] == 0
        assert data["message"] == "成功创建 1 个任务，2 个文件被拒绝。"
        assert data["created_tasks"][0]["apk_file_name"] == "valid.apk"
        assert data["created_tasks"][0]["id"] == "task-upload-1"
        assert data["rejected_files"] == [
            {
                "file_name": "notes.txt",
                "reason": "Only APK and ZIP uploads are supported.",
            },
            {
                "file_name": "too-large.apk",
                "reason": "APK exceeds the configured size limit.",
            },
        ]

        db = session_local()
        try:
            tasks = db.query(Task).all()
            assert len(tasks) == 1
            assert tasks[0].apk_file_name == "valid.apk"
        finally:
            db.close()

    def test_upload_route_reuses_existing_storage_path_for_duplicate_apk(
        self,
        frontend_upload_client: tuple[TestClient, sessionmaker],
    ):
        """Duplicate APK uploads should reuse existing object storage instead of re-uploading."""
        client, session_local = frontend_upload_client
        fake_storage = FakeStorage()

        db = session_local()
        try:
            existing_task = Task(
                id="existing-task",
                apk_file_name="alpha.apk",
                apk_file_size=5,
                apk_md5="2c1743a391305fbf367df8e4f069f9f9",
                apk_storage_path="apks/existing-task/reused.apk",
                status=TaskStatus.COMPLETED,
                priority=TaskPriority.NORMAL,
            )
            db.add(existing_task)
            db.commit()
        finally:
            db.close()

        with patch("api.routers.frontend.BatchUploadService", side_effect=service_factory(
            fake_storage,
            limits=BatchUploadLimits(max_batch_apks=10, max_apk_size_bytes=64, max_zip_size_bytes=512),
        )), patch("api.routers.frontend.enqueue_task", return_value=True):
            response = client.post(
                "/api/v1/frontend/tasks/upload",
                files=[
                    ("files", ("alpha.apk", b"alpha", "application/vnd.android.package-archive")),
                ],
            )

        assert response.status_code == 200
        data = response.json()
        assert data["created_tasks"][0]["apk_file_name"] == "alpha.apk"

        db = session_local()
        try:
            created = db.query(Task).filter(Task.id == "task-upload-1").one()
            assert created.apk_storage_path == "apks/existing-task/reused.apk"
        finally:
            db.close()

        assert fake_storage.uploads == []
