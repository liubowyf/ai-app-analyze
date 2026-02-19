"""MinIO storage management for APK Analysis Platform."""
from datetime import timedelta
from io import BytesIO
from typing import Optional

from minio import Minio
from minio.error import S3Error

from core.config import settings


class StorageManager:
    """Manages MinIO storage operations for APK analysis files."""

    def __init__(self):
        """Initialize MinIO client and create bucket if needed."""
        self.client: Optional[Minio] = None
        self.bucket = settings.MINIO_BUCKET

        try:
            # Initialize MinIO client
            self.client = Minio(
                endpoint=settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )

            # Create bucket if it doesn't exist
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
        except Exception as e:
            # Handle connection errors gracefully
            print(f"Warning: Failed to initialize MinIO client: {e}")
            self.client = None

    def generate_apk_path(self, task_id: str, md5: str) -> str:
        """
        Generate storage path for APK file.

        Args:
            task_id: Task identifier
            md5: MD5 hash of the APK file

        Returns:
            Storage path in format "apks/{task_id}/{md5}.apk"
        """
        return f"apks/{task_id}/{md5}.apk"

    def generate_screenshot_path(self, task_id: str, step: int) -> str:
        """
        Generate storage path for screenshot file.

        Args:
            task_id: Task identifier
            step: Step number (will be zero-padded to 3 digits)

        Returns:
            Storage path in format "screenshots/{task_id}/step_{step:03d}.png"
        """
        return f"screenshots/{task_id}/step_{step:03d}.png"

    def generate_report_path(self, task_id: str) -> str:
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
        if not self.client:
            return False

        try:
            data_stream = BytesIO(data)
            self.client.put_object(
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
        if not self.client:
            return None

        try:
            response = self.client.get_object(self.bucket, object_name)
            with response:
                return response.read()
        except Exception as e:
            print(f"Error downloading file {object_name}: {e}")
            return None

    def get_presigned_url(
        self,
        object_name: str,
        expires: timedelta
    ) -> Optional[str]:
        """
        Generate presigned URL for file access.

        Args:
            object_name: Storage path of the file
            expires: URL expiration time

        Returns:
            Presigned URL if successful, None otherwise
        """
        if not self.client:
            return None

        try:
            url = self.client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=object_name,
                expires=expires
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
        if not self.client:
            return False

        try:
            self.client.remove_object(self.bucket, object_name)
            return True
        except Exception as e:
            print(f"Error deleting file {object_name}: {e}")
            return False


# Global storage client instance
storage_client = StorageManager()
