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
