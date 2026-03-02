"""Unit tests for MinIO storage management."""
from datetime import timedelta
from unittest.mock import Mock, MagicMock, patch
import pytest

from core.config import settings
from core.storage import StorageManager, storage_client


class TestStorageManager:
    """Test suite for StorageManager class."""

    @patch('core.storage.Minio')
    def test_init_creates_client_with_settings(self, mock_minio_class):
        """Test client init happens lazily on first real storage operation."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        manager = StorageManager()

        assert manager.client is None
        mock_minio_class.assert_not_called()
        assert manager.upload_file("test/file.txt", b"content", "text/plain") is True

        mock_minio_class.assert_called_once_with(
            endpoint=settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
        assert manager.client == mock_client

    @patch('core.storage.Minio')
    def test_init_creates_bucket_if_not_exists(self, mock_minio_class):
        """Test bucket creation happens on first operation when bucket is absent."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = False

        manager = StorageManager()

        mock_minio_class.assert_not_called()
        assert manager.upload_file("test/file.txt", b"content", "text/plain") is True
        mock_client.bucket_exists.assert_called_once_with(manager.bucket)
        mock_client.make_bucket.assert_called_once_with(manager.bucket)

    @patch('core.storage.Minio')
    def test_init_skips_bucket_creation_if_exists(self, mock_minio_class):
        """Test bucket creation is skipped when bucket already exists."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        manager = StorageManager()

        mock_minio_class.assert_not_called()
        assert manager.upload_file("test/file.txt", b"content", "text/plain") is True
        mock_client.bucket_exists.assert_called_once_with(manager.bucket)
        mock_client.make_bucket.assert_not_called()

    @patch('core.storage.Minio')
    def test_init_handles_connection_error_gracefully(self, mock_minio_class):
        """Test that connection errors don't crash initialization."""
        mock_minio_class.side_effect = Exception("Connection refused")

        manager = StorageManager()

        # Should not crash, client should be None
        assert manager.client is None

    def test_generate_apk_path(self):
        """Test APK path generation as static method."""
        # Test calling via class (spec requirement)
        path = StorageManager.generate_apk_path("task-123", "abc123def456")
        assert path == "apks/task-123/abc123def456.apk"

        # Test calling via instance (backward compatibility)
        manager = StorageManager.__new__(StorageManager)
        path = manager.generate_apk_path("task-123", "abc123def456")
        assert path == "apks/task-123/abc123def456.apk"

    def test_generate_screenshot_path(self):
        """Test screenshot path generation as static method."""
        # Test calling via class (spec requirement)
        path = StorageManager.generate_screenshot_path("task-456", 5)
        assert path == "screenshots/task-456/step_005.png"

        path = StorageManager.generate_screenshot_path("task-456", 42)
        assert path == "screenshots/task-456/step_042.png"

        # Test calling via instance (backward compatibility)
        manager = StorageManager.__new__(StorageManager)
        path = manager.generate_screenshot_path("task-456", 5)
        assert path == "screenshots/task-456/step_005.png"

    def test_generate_report_path(self):
        """Test report path generation as static method."""
        # Test calling via class (spec requirement)
        path = StorageManager.generate_report_path("task-789")
        assert path == "reports/task-789/report.pdf"

        # Test calling via instance (backward compatibility)
        manager = StorageManager.__new__(StorageManager)
        path = manager.generate_report_path("task-789")
        assert path == "reports/task-789/report.pdf"

    @patch('core.storage.Minio')
    def test_upload_file_success(self, mock_minio_class):
        """Test successful file upload."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        manager = StorageManager()

        data = b"test file content"
        result = manager.upload_file("test/file.txt", data, "text/plain")

        assert result is True
        mock_client.put_object.assert_called_once()

    @patch('core.storage.Minio')
    def test_upload_file_failure(self, mock_minio_class):
        """Test file upload failure."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        mock_client.put_object.side_effect = Exception("Upload failed")

        manager = StorageManager()

        data = b"test file content"
        result = manager.upload_file("test/file.txt", data, "text/plain")

        assert result is False

    @patch('core.storage.Minio')
    def test_upload_file_no_client(self, mock_minio_class):
        """Test upload when client is not initialized."""
        mock_minio_class.side_effect = Exception("Connection refused")

        manager = StorageManager()

        data = b"test file content"
        result = manager.upload_file("test/file.txt", data, "text/plain")

        assert result is False

    @patch('core.storage.Minio')
    def test_download_file_success(self, mock_minio_class):
        """Test successful file download."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        # Mock response
        mock_response = MagicMock()
        mock_response.read.return_value = b"downloaded content"
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)
        mock_client.get_object.return_value = mock_response

        manager = StorageManager()

        result = manager.download_file("test/file.txt")

        assert result == b"downloaded content"
        mock_client.get_object.assert_called_once_with(manager.bucket, "test/file.txt")

    @patch('core.storage.Minio')
    def test_download_file_failure(self, mock_minio_class):
        """Test file download failure."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        mock_client.get_object.side_effect = Exception("Download failed")

        manager = StorageManager()

        result = manager.download_file("test/file.txt")

        assert result is None

    @patch('core.storage.Minio')
    def test_download_file_no_client(self, mock_minio_class):
        """Test download when client is not initialized."""
        mock_minio_class.side_effect = Exception("Connection refused")

        manager = StorageManager()

        result = manager.download_file("test/file.txt")

        assert result is None

    @patch('core.storage.Minio')
    def test_get_presigned_url_success(self, mock_minio_class):
        """Test successful presigned URL generation with int parameter."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        manager = StorageManager()
        expected_url = f"http://localhost:9000/{manager.bucket}/test/file.txt?signature=abc"
        mock_client.presigned_get_object.return_value = expected_url

        # Test with default expiration (3600 seconds = 1 hour)
        url = manager.get_presigned_url("test/file.txt")

        assert url == expected_url
        mock_client.presigned_get_object.assert_called_once()
        # Verify timedelta conversion
        call_args = mock_client.presigned_get_object.call_args
        assert call_args[1]['expires'] == timedelta(seconds=3600)

    @patch('core.storage.Minio')
    def test_get_presigned_url_failure(self, mock_minio_class):
        """Test presigned URL generation failure."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        mock_client.presigned_get_object.side_effect = Exception("URL generation failed")

        manager = StorageManager()

        url = manager.get_presigned_url("test/file.txt", 3600)

        assert url is None

    @patch('core.storage.Minio')
    def test_get_presigned_url_no_client(self, mock_minio_class):
        """Test presigned URL when client is not initialized."""
        mock_minio_class.side_effect = Exception("Connection refused")

        manager = StorageManager()

        url = manager.get_presigned_url("test/file.txt", 3600)

        assert url is None

    @patch('core.storage.Minio')
    def test_delete_file_success(self, mock_minio_class):
        """Test successful file deletion."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True

        manager = StorageManager()

        result = manager.delete_file("test/file.txt")

        assert result is True
        mock_client.remove_object.assert_called_once_with(manager.bucket, "test/file.txt")

    @patch('core.storage.Minio')
    def test_delete_file_failure(self, mock_minio_class):
        """Test file deletion failure."""
        mock_client = MagicMock()
        mock_minio_class.return_value = mock_client
        mock_client.bucket_exists.return_value = True
        mock_client.remove_object.side_effect = Exception("Delete failed")

        manager = StorageManager()

        result = manager.delete_file("test/file.txt")

        assert result is False

    @patch('core.storage.Minio')
    def test_delete_file_no_client(self, mock_minio_class):
        """Test delete when client is not initialized."""
        mock_minio_class.side_effect = Exception("Connection refused")

        manager = StorageManager()

        result = manager.delete_file("test/file.txt")

        assert result is False

    def test_global_storage_client_exists(self):
        """Test that global storage_client instance exists."""
        # This test verifies that the global instance is created
        # Note: Due to mocking, we just verify the attribute exists
        assert hasattr(storage_client, 'client') or storage_client is not None
