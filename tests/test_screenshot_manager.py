"""Tests for ScreenshotManager module."""
import pytest
from modules.screenshot_manager.manager import ScreenshotManager, Screenshot


def test_screenshot_manager_init():
    """Test ScreenshotManager initialization."""
    manager = ScreenshotManager(task_id="test-task-123")
    assert manager.task_id == "test-task-123"
    assert len(manager.screenshots) == 0


def test_screenshot_dataclass():
    """Test Screenshot dataclass."""
    screenshot = Screenshot(
        stage="install",
        description="APK安装完成",
        image_data=b"fake_image_data",
        timestamp="2026-02-19T12:00:00",
        image_hash="abc123"
    )
    assert screenshot.stage == "install"
    assert screenshot.description == "APK安装完成"


def test_is_duplicate_detection():
    """Test duplicate screenshot detection."""
    manager = ScreenshotManager(task_id="test-task")

    # First screenshot
    image1 = b"image_data_1"
    assert not manager.is_duplicate(image1)

    # Record hash
    manager.last_image_hash = manager._calculate_hash(image1)

    # Same image
    assert manager.is_duplicate(image1)

    # Different image
    image2 = b"image_data_2_different"
    assert not manager.is_duplicate(image2)


def test_save_to_local_persists_png(tmp_path):
    manager = ScreenshotManager(task_id="task-local")
    shot = Screenshot(
        stage="launch",
        description="应用启动界面",
        image_data=b"\x89PNG\r\n\x1a\nFAKE",
        timestamp="2026-02-22T14:00:00",
        image_hash="abc",
    )

    local_path = manager.save_to_local(shot, str(tmp_path), 1)

    assert local_path is not None
    assert local_path.endswith("step_001_launch.png")
    assert (tmp_path / "step_001_launch.png").exists()
    assert shot.storage_path == local_path
