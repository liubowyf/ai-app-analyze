"""Unit tests for APK router endpoints."""
import hashlib
import io
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from models.task import Task, TaskStatus, TaskPriority


class TestAPKUpload:
    """Test cases for APK upload endpoint."""

    def test_upload_apk_success(self, client: TestClient):
        """Test successful APK file upload."""
        # Create test APK file content
        apk_content = b"fake apk content for testing"
        apk_file = io.BytesIO(apk_content)

        # Calculate expected MD5
        expected_md5 = hashlib.md5(apk_content).hexdigest()

        with patch("api.routers.apk.SessionLocal") as mock_session_local, \
             patch("api.routers.apk.storage_client") as mock_storage, \
             patch("api.routers.apk.Task") as mock_task_class:

            # Setup mocks
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_storage.upload_file.return_value = True
            mock_storage.generate_apk_path.return_value = "apks/test-task-id/test.apk"

            # Create a mock task instance
            mock_task_instance = MagicMock()
            mock_task_instance.id = "test-task-id"
            mock_task_instance.apk_file_name = "test.apk"
            mock_task_instance.apk_file_size = len(apk_content)
            mock_task_instance.apk_md5 = expected_md5

            # Make Task class return our mock instance
            mock_task_class.return_value = mock_task_instance

            # Upload the file
            response = client.post(
                "/api/v1/apk/upload",
                files={"file": ("test.apk", apk_file, "application/vnd.android.package-archive")}
            )

        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "task_id" in data
        assert data["task_id"] == "test-task-id"
        assert data["file_name"] == "test.apk"
        assert data["file_size"] == len(apk_content)
        assert "md5" in data
        assert data["message"] == "APK file uploaded successfully"
        assert data["md5"] == expected_md5

    def test_upload_apk_invalid_extension(self, client: TestClient):
        """Test upload with non-APK file extension."""
        # Create test file with wrong extension
        file_content = b"not an apk file"
        test_file = io.BytesIO(file_content)

        # Upload the file
        response = client.post(
            "/api/v1/apk/upload",
            files={"file": ("test.txt", test_file, "text/plain")}
        )

        # Verify error response
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid file extension" in data["detail"]

    def test_upload_apk_no_extension(self, client: TestClient):
        """Test upload with file without extension."""
        # Create test file without extension
        file_content = b"file without extension"
        test_file = io.BytesIO(file_content)

        # Upload the file
        response = client.post(
            "/api/v1/apk/upload",
            files={"file": ("testfile", test_file, "application/octet-stream")}
        )

        # Verify error response
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Invalid file extension" in data["detail"]

    def test_upload_apk_storage_failure(self, client: TestClient):
        """Test upload when storage fails."""
        # Create test APK file
        apk_content = b"fake apk content"
        apk_file = io.BytesIO(apk_content)

        with patch("api.routers.apk.SessionLocal") as mock_session_local, \
             patch("api.routers.apk.storage_client") as mock_storage:

            # Setup mocks
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_storage.upload_file.return_value = False
            mock_storage.generate_apk_path.return_value = "apks/test-task-id/test.apk"

            # Upload the file
            response = client.post(
                "/api/v1/apk/upload",
                files={"file": ("test.apk", apk_file, "application/vnd.android.package-archive")}
            )

        # Verify error response
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to store file" in data["detail"]

    def test_upload_apk_md5_calculation(self, client: TestClient):
        """Test MD5 hash calculation is correct."""
        # Create test APK with known content
        apk_content = b"test content for md5 calculation"
        apk_file = io.BytesIO(apk_content)

        # Calculate expected MD5
        expected_md5 = hashlib.md5(apk_content).hexdigest()

        with patch("api.routers.apk.SessionLocal") as mock_session_local, \
             patch("api.routers.apk.storage_client") as mock_storage, \
             patch("api.routers.apk.Task") as mock_task_class:

            # Setup mocks
            mock_db = MagicMock(spec=Session)
            mock_session_local.return_value = mock_db
            mock_storage.upload_file.return_value = True
            mock_storage.generate_apk_path.return_value = "apks/test-task-id/test.apk"

            # Create a mock task instance
            mock_task_instance = MagicMock()
            mock_task_instance.id = "test-task-id"
            mock_task_instance.apk_file_name = "test.apk"
            mock_task_instance.apk_file_size = len(apk_content)
            mock_task_instance.apk_md5 = expected_md5

            # Make Task class return our mock instance
            mock_task_class.return_value = mock_task_instance

            # Upload the file
            response = client.post(
                "/api/v1/apk/upload",
                files={"file": ("test.apk", apk_file, "application/vnd.android.package-archive")}
            )

        # Verify MD5 matches
        assert response.status_code == 200
        data = response.json()
        assert data["md5"] == expected_md5
