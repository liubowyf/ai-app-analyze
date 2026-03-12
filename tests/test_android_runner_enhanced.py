"""Tests for enhanced AndroidRunner functionality."""
import pytest
from unittest.mock import Mock, patch
from modules.android_runner.runner import AndroidRunner


def test_connect_remote_emulator():
    """Test connecting to remote emulator."""
    runner = AndroidRunner()
    # This would require actual emulator connection
    # Mock for unit test
    assert runner is not None
    assert hasattr(runner, 'connect_remote_emulator')


def test_execute_adb_remote_command():
    """Test executing remote ADB command."""
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


def test_execute_adb_remote_allows_per_call_timeout_override(monkeypatch):
    """Per-call timeout should override env timeout for long-running commands."""
    runner = AndroidRunner()

    completed = Mock()
    completed.stdout = "ok"
    completed.stderr = ""
    monkeypatch.setenv("ADB_COMMAND_TIMEOUT_SECONDS", "7")

    with patch("subprocess.run", return_value=completed) as mocked_run:
        runner.execute_adb_remote(
            "10.0.0.1",
            5558,
            "install -r /tmp/a.apk",
            timeout_seconds=180,
        )

    assert mocked_run.call_args.kwargs["timeout"] == 180.0


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


def test_install_apk_remote_retries_and_uses_install_timeout(monkeypatch):
    """APK install should retry transient failures with dedicated timeout."""
    runner = AndroidRunner()
    monkeypatch.setenv("ADB_INSTALL_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("ADB_INSTALL_RETRIES", "3")

    runner.execute_adb_remote = Mock(side_effect=["Failure [TIMEOUT]", "Success"])
    runner.connect_remote_emulator = Mock(return_value=True)

    ok = runner.install_apk_remote("10.0.0.1", 5558, "/tmp/demo app.apk")

    assert ok is True
    assert runner.execute_adb_remote.call_count == 2
    first_call = runner.execute_adb_remote.call_args_list[0]
    second_call = runner.execute_adb_remote.call_args_list[1]
    assert first_call.kwargs["timeout_seconds"] == 45.0
    assert second_call.kwargs["timeout_seconds"] == 45.0
    assert "install -r -g '/tmp/demo app.apk'" in first_call.args[2]
    assert runner.connect_remote_emulator.call_count == 1


def test_install_apk_remote_fails_after_retry_limit(monkeypatch):
    """APK install should fail after exhausting configured retries."""
    runner = AndroidRunner()
    monkeypatch.setenv("ADB_INSTALL_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("ADB_INSTALL_RETRIES", "2")

    runner.execute_adb_remote = Mock(side_effect=["Failure", "Failure"])
    runner.connect_remote_emulator = Mock(return_value=True)

    ok = runner.install_apk_remote("10.0.0.1", 5558, "/tmp/demo.apk")

    assert ok is False
    assert runner.execute_adb_remote.call_count == 2
    assert runner.connect_remote_emulator.call_count == 2


def test_install_apk_remote_defaults_to_ten_minute_timeout(monkeypatch):
    """APK install should default to a 10 minute timeout for large packages."""
    runner = AndroidRunner()
    monkeypatch.delenv("ADB_INSTALL_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("ADB_INSTALL_RETRIES", "1")

    runner.execute_adb_remote = Mock(return_value="Success")
    runner.connect_remote_emulator = Mock(return_value=True)

    ok = runner.install_apk_remote("10.0.0.1", 5558, "/tmp/large.apk")

    assert ok is True
    runner.execute_adb_remote.assert_called_once()
    assert runner.execute_adb_remote.call_args.kwargs["timeout_seconds"] == 600.0


def test_launch_app_uses_configured_timeout(monkeypatch):
    """Launch command should use dedicated timeout to avoid hanging forever."""
    runner = AndroidRunner()
    monkeypatch.setenv("ADB_LAUNCH_TIMEOUT_SECONDS", "12")
    runner.execute_adb_remote = Mock(return_value="Events injected: 1")

    runner.launch_app("10.0.0.1", 5558, "com.example.demo")

    runner.execute_adb_remote.assert_called_once_with(
        "10.0.0.1",
        5558,
        "shell monkey -p com.example.demo -c android.intent.category.LAUNCHER 1",
        timeout_seconds=12.0,
    )


def test_launch_app_uses_explicit_activity_when_provided(monkeypatch):
    runner = AndroidRunner()
    monkeypatch.setenv("ADB_LAUNCH_TIMEOUT_SECONDS", "12")
    runner.execute_adb_remote = Mock(return_value="Status: ok")

    runner.launch_app("10.0.0.1", 5558, "com.example.demo", activity_name="com.example.demo.MainActivity")

    runner.execute_adb_remote.assert_called_once_with(
        "10.0.0.1",
        5558,
        "shell am start -W -n com.example.demo/com.example.demo.MainActivity",
        timeout_seconds=12.0,
    )
