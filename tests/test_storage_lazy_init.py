"""Tests for lazy storage client initialization."""

from unittest.mock import MagicMock, patch

from core.storage import StorageManager


def test_storage_manager_init_does_not_touch_bucket_check():
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True

    with patch("core.storage.Minio", return_value=mock_client):
        StorageManager()

    assert mock_client.bucket_exists.call_count == 0


def test_storage_manager_lazy_initializes_on_first_real_operation():
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    mock_client.put_object.return_value = None

    with patch("core.storage.Minio", return_value=mock_client):
        manager = StorageManager()
        assert mock_client.bucket_exists.call_count == 0

        ok = manager.upload_file(
            object_name="reports/task-1/report.pdf",
            data=b"hello",
            content_type="application/pdf",
        )

    assert ok is True
    assert mock_client.bucket_exists.call_count == 1
    assert mock_client.put_object.call_count == 1
