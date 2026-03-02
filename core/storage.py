"""MinIO storage management for APK Analysis Platform."""
from datetime import timedelta
from io import BytesIO
from threading import Lock
from typing import Optional

from minio import Minio
from minio.error import S3Error

from core.config import settings


class StorageManager:
    """Manages MinIO storage operations for APK analysis files."""

    def __init__(self):
        """Initialize manager state without network calls."""
        self.client: Optional[Minio] = None
        self.bucket = settings.MINIO_BUCKET
        self._client_initialized = False
        self._bucket_ensured = False
        self._client_lock = Lock()
        self._bucket_lock = Lock()

    def _get_client(self, ensure_bucket: bool = False) -> Optional[Minio]:
        """Lazily initialize MinIO client and optional bucket setup."""
        client = self._initialize_client()
        if not client:
            return None
        if ensure_bucket and not self._ensure_bucket(client):
            return None
        return client

    def _initialize_client(self) -> Optional[Minio]:
        """Initialize MinIO client once on first real storage access."""
        if self._client_initialized:
            return self.client

        with self._client_lock:
            if self._client_initialized:
                return self.client
            try:
                self.client = Minio(
                    endpoint=settings.MINIO_ENDPOINT,
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY,
                    secure=settings.MINIO_SECURE,
                )
            except Exception as e:
                print(f"Warning: Failed to initialize MinIO client: {e}")
                self.client = None
            finally:
                self._client_initialized = True

        return self.client

    def _ensure_bucket(self, client: Minio) -> bool:
        """Ensure bucket exists only once."""
        if self._bucket_ensured:
            return True

        with self._bucket_lock:
            if self._bucket_ensured:
                return True
            try:
                if not client.bucket_exists(self.bucket):
                    client.make_bucket(self.bucket)
                self._bucket_ensured = True
                return True
            except Exception as e:
                print(f"Warning: Failed to ensure bucket {self.bucket}: {e}")
                return False

    @staticmethod
    def generate_apk_path(task_id: str, md5: str) -> str:
        """
        Generate storage path for APK file.

        Args:
            task_id: Task identifier
            md5: MD5 hash of the APK file

        Returns:
            Storage path in format "apks/{task_id}/{md5}.apk"
        """
        return f"apks/{task_id}/{md5}.apk"

    @staticmethod
    def generate_screenshot_path(task_id: str, step: int) -> str:
        """
        Generate storage path for screenshot file.

        Args:
            task_id: Task identifier
            step: Step number (will be zero-padded to 3 digits)

        Returns:
            Storage path in format "screenshots/{task_id}/step_{step:03d}.png"
        """
        return f"screenshots/{task_id}/step_{step:03d}.png"

    @staticmethod
    def generate_report_path(task_id: str) -> str:
        """
        Generate storage path for analysis report.

        Args:
            task_id: Task identifier

        Returns:
            Storage path in format "reports/{task_id}/report.pdf"
        """
        return f"reports/{task_id}/report.pdf"

    def upload_file(
        self,
        object_name: str,
        data: bytes,
        content_type: str
    ) -> bool:
        """
        Upload file to MinIO storage.

        Args:
            object_name: Storage path for the file
            data: File content as bytes
            content_type: MIME type of the file

        Returns:
            True if upload successful, False otherwise
        """
        client = self._get_client(ensure_bucket=True)
        if not client:
            return False

        try:
            data_stream = BytesIO(data)
            client.put_object(
                bucket_name=self.bucket,
                object_name=object_name,
                data=data_stream,
                length=len(data),
                content_type=content_type
            )
            return True
        except Exception as e:
            print(f"Error uploading file {object_name}: {e}")
            return False

    def download_file(self, object_name: str) -> Optional[bytes]:
        """
        Download file from MinIO storage.

        Args:
            object_name: Storage path of the file

        Returns:
            File content as bytes if successful, None otherwise
        """
        client = self._get_client(ensure_bucket=True)
        if not client:
            return None

        try:
            response = client.get_object(self.bucket, object_name)
            with response:
                return response.read()
        except Exception as e:
            print(f"Error downloading file {object_name}: {e}")
            return None

    def get_presigned_url(
        self,
        object_name: str,
        expires: int = 3600
    ) -> Optional[str]:
        """
        Generate presigned URL for file access.

        Args:
            object_name: Storage path of the file
            expires: URL expiration time in seconds (default: 3600)

        Returns:
            Presigned URL if successful, None otherwise
        """
        client = self._get_client(ensure_bucket=True)
        if not client:
            return None

        try:
            url = client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=object_name,
                expires=timedelta(seconds=expires)
            )
            return url
        except Exception as e:
            print(f"Error generating presigned URL for {object_name}: {e}")
            return None

    def delete_file(self, object_name: str) -> bool:
        """
        Delete file from MinIO storage.

        Args:
            object_name: Storage path of the file

        Returns:
            True if deletion successful, False otherwise
        """
        client = self._get_client(ensure_bucket=True)
        if not client:
            return False

        try:
            client.remove_object(self.bucket, object_name)
            return True
        except Exception as e:
            print(f"Error deleting file {object_name}: {e}")
            return False


# Global storage client instance
storage_client = StorageManager()
