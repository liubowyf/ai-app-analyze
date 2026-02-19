"""Screenshot Manager for capturing and managing analysis screenshots."""
import io
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import subprocess
import hashlib

logger = logging.getLogger(__name__)


@dataclass
class Screenshot:
    """Screenshot data container."""
    stage: str
    description: str
    image_data: bytes
    timestamp: str
    image_hash: str
    storage_path: Optional[str] = None


class ScreenshotManager:
    """Manage screenshot capture, deduplication, and storage."""

    def __init__(self, task_id: str):
        """
        Initialize screenshot manager.

        Args:
            task_id: Task ID for organizing screenshots
        """
        self.task_id = task_id
        self.screenshots: List[Screenshot] = []
        self.last_image_hash: Optional[str] = None
        self._similarity_threshold = 10  # Image hash similarity threshold

    def _calculate_hash(self, image_data: bytes) -> str:
        """
        Calculate perceptual hash of image.

        Args:
            image_data: Image bytes

        Returns:
            Hash string
        """
        try:
            import imagehash
            from PIL import Image

            img = Image.open(io.BytesIO(image_data))
            return str(imagehash.phash(img))
        except Exception as e:
            logger.warning(f"Failed to calculate perceptual hash: {e}, using MD5")
            return hashlib.md5(image_data).hexdigest()

    def is_duplicate(self, image_data: bytes) -> bool:
        """
        Check if image is duplicate of last screenshot.

        Args:
            image_data: Image bytes to check

        Returns:
            True if duplicate
        """
        if not self.last_image_hash:
            return False

        current_hash = self._calculate_hash(image_data)

        try:
            import imagehash
            hash1 = imagehash.hex_to_hash(self.last_image_hash)
            hash2 = imagehash.hex_to_hash(current_hash)
            difference = hash1 - hash2
            return difference < self._similarity_threshold
        except Exception:
            # Fallback to exact match
            return current_hash == self.last_image_hash

    def capture(self, stage: str, description: str,
                emulator_host: str, emulator_port: int) -> Optional[Screenshot]:
        """
        Capture screenshot from remote emulator.

        Args:
            stage: Analysis stage (install, launch, explore, etc.)
            description: Screenshot description
            emulator_host: Emulator host IP
            emulator_port: Emulator ADB port

        Returns:
            Screenshot object or None if capture failed
        """
        try:
            # Use ADB to capture screenshot
            device = f"{emulator_host}:{emulator_port}"

            # Take screenshot on device
            subprocess.run(
                ["adb", "-s", device, "shell", "screencap", "-p", "/sdcard/screen.png"],
                check=True,
                capture_output=True,
                timeout=10
            )

            # Pull screenshot to local temp file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            subprocess.run(
                ["adb", "-s", device, "pull", "/sdcard/screen.png", tmp_path],
                check=True,
                capture_output=True,
                timeout=10
            )

            # Read image data
            with open(tmp_path, "rb") as f:
                image_data = f.read()

            # Clean up
            import os
            os.unlink(tmp_path)

            # Check for duplicate
            if self.is_duplicate(image_data):
                logger.info(f"Skipping duplicate screenshot: {stage}")
                return None

            # Create screenshot record
            screenshot = Screenshot(
                stage=stage,
                description=description,
                image_data=image_data,
                timestamp=datetime.now().isoformat(),
                image_hash=self._calculate_hash(image_data)
            )

            # Update last hash
            self.last_image_hash = screenshot.image_hash

            # Add to list
            self.screenshots.append(screenshot)

            logger.info(f"Captured screenshot: {stage} - {description}")
            return screenshot

        except Exception as e:
            logger.error(f"Failed to capture screenshot: {e}")
            return None

    def save_to_minio(self, screenshot: Screenshot) -> Optional[str]:
        """
        Upload screenshot to MinIO storage.

        Args:
            screenshot: Screenshot to upload

        Returns:
            Storage path or None on failure
        """
        try:
            from core.storage import storage_client

            path = f"screenshots/{self.task_id}/{screenshot.stage}_{len(self.screenshots)}.png"

            success = storage_client.upload_file(
                object_name=path,
                data=screenshot.image_data,
                content_type="image/png"
            )

            if success:
                screenshot.storage_path = path
                logger.info(f"Uploaded screenshot to MinIO: {path}")
                return path
            else:
                logger.error("Failed to upload screenshot to MinIO")
                return None

        except Exception as e:
            logger.error(f"Failed to save screenshot to MinIO: {e}")
            return None

    def get_all_for_report(self) -> List[Dict]:
        """
        Get all screenshots formatted for report.

        Returns:
            List of screenshot dictionaries
        """
        return [
            {
                "stage": s.stage,
                "description": s.description,
                "timestamp": s.timestamp,
                "storage_path": s.storage_path,
                "image_base64": self._to_base64(s.image_data) if s.image_data else None
            }
            for s in self.screenshots
        ]

    def _to_base64(self, image_data: bytes) -> str:
        """Convert image to base64 string."""
        import base64
        return base64.b64encode(image_data).decode('utf-8')

    def clear(self) -> None:
        """Clear all screenshots."""
        self.screenshots.clear()
        self.last_image_hash = None
