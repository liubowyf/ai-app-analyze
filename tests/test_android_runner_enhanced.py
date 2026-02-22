"""Tests for enhanced AndroidRunner functionality."""
import pytest
from unittest.mock import Mock, patch
from modules.android_runner.runner import AndroidRunner


def test_connect_remote_emulator():
    """Test connecting to remote emulator."""
    with patch('docker.from_env'):
        runner = AndroidRunner()
        # This would require actual emulator connection
        # Mock for unit test
        assert runner is not None
        assert hasattr(runner, 'connect_remote_emulator')


def test_execute_adb_remote_command():
    """Test executing remote ADB command."""
    with patch('docker.from_env'):
        runner = AndroidRunner()
        # Mock test - actual implementation requires emulator
        assert hasattr(runner, 'execute_adb_remote')
        assert hasattr(runner, 'install_apk_remote')
        assert hasattr(runner, 'take_screenshot_remote')
        assert hasattr(runner, 'grant_all_permissions')
        assert hasattr(runner, 'launch_app')
        assert hasattr(runner, 'execute_tap')
        assert hasattr(runner, 'execute_swipe')
        assert hasattr(runner, 'execute_input_text')
        assert hasattr(runner, 'get_current_activity')
        assert hasattr(runner, 'press_back')
        assert hasattr(runner, 'press_home')


def test_execute_adb_remote_shell_uses_sh_c_for_pipe_commands():
    """Shell commands should keep pipe/grep semantics via sh -c."""
    runner = AndroidRunner()

    completed = Mock()
    completed.stdout = "ok"
    completed.stderr = ""

    with patch("subprocess.run", return_value=completed) as mocked_run:
        output = runner.execute_adb_remote("10.0.0.1", 5558, "shell dumpsys activity | grep mResumedActivity")

    assert output == "ok"
    called_args = mocked_run.call_args.args[0]
    assert called_args[:4] == ["adb", "-s", "10.0.0.1:5558", "shell"]
    assert called_args[4] == "sh"
    assert called_args[5] == "-c"
    assert "grep mResumedActivity" in called_args[6]


def test_execute_adb_remote_respects_timeout_env(monkeypatch):
    """ADB command timeout should use runtime env setting."""
    runner = AndroidRunner()

    completed = Mock()
    completed.stdout = "ok"
    completed.stderr = ""
    monkeypatch.setenv("ADB_COMMAND_TIMEOUT_SECONDS", "7")

    with patch("subprocess.run", return_value=completed) as mocked_run:
        runner.execute_adb_remote("10.0.0.1", 5558, "shell getprop ro.build.version.release")

    assert mocked_run.call_args.kwargs["timeout"] == 7.0


def test_get_current_activity_parses_activity_token_from_dumpsys():
    """Foreground activity parser should extract package/activity token."""
    runner = AndroidRunner()
    runner.execute_adb_remote = Mock(return_value="mResumedActivity: ActivityRecord{123 u0 com.demo/.MainActivity t44}")

    activity = runner.get_current_activity("10.0.0.1", 5558)
    package = runner.get_current_package("10.0.0.1", 5558)

    assert activity == "com.demo/.MainActivity"
    assert package == "com.demo"


def test_extract_activity_token_prefers_resumed_activity_marker():
    """Parser should prefer mResumedActivity over earlier non-resumed ACTIVITY lines."""
    sample = """
    ACTIVITY com.google.android.apps.nexuslauncher/.NexusLauncherActivity 7160c7f pid=1013
      mResumed=false mStopped=true
    mResumedActivity: ActivityRecord{3b3684a u0 com.demo/.MainActivity t9}
    """

    activity = AndroidRunner._extract_activity_token(sample)

    assert activity == "com.demo/.MainActivity"


def test_take_screenshot_remote_prefers_exec_out(monkeypatch):
    """Screenshot capture should prefer adb exec-out to avoid pull hangs."""
    runner = AndroidRunner()

    completed = Mock()
    completed.stdout = b"\x89PNG\r\n\x1a\nDATA"
    completed.stderr = b""

    with patch("subprocess.run", return_value=completed) as mocked_run:
        data = runner.take_screenshot_remote("10.0.0.1", 5558)

    assert data.startswith(b"\x89PNG")
    cmd = mocked_run.call_args.args[0]
    assert cmd[:4] == ["adb", "-s", "10.0.0.1:5558", "exec-out"]
