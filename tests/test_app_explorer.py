"""Tests for AppExplorer module."""
import pytest
from unittest.mock import Mock, patch
from modules.exploration_strategy.explorer import AppExplorer, ExplorationResult


def test_explorer_initialization():
    """Test AppExplorer initialization."""
    from modules.ai_driver import AIDriver
    from modules.screenshot_manager import ScreenshotManager

    # Mock AndroidRunner to avoid Docker connection
    with patch('modules.android_runner.runner.docker.from_env'):
        from modules.android_runner import AndroidRunner

        ai_driver = AIDriver()
        android_runner = AndroidRunner()
        screenshot_manager = ScreenshotManager(task_id="test")

        explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)
        assert explorer is not None
        assert len(explorer.exploration_history) == 0


def test_exploration_result_dataclass():
    """Test ExplorationResult dataclass."""
    result = ExplorationResult(
        total_steps=10,
        screenshots=[],
        network_requests=[],
        activities_visited=["MainActivity"],
        success=True
    )
    assert result.total_steps == 10
    assert result.success is True
