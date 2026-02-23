"""Tests for AppExplorer module."""
import pytest
import time
from unittest.mock import Mock, patch
from modules.exploration_strategy.explorer import AppExplorer, ExplorationResult
from modules.ai_driver import Operation, OperationType


def test_explorer_initialization():
    """Test AppExplorer initialization."""
    from modules.ai_driver import AIDriver
    from modules.screenshot_manager import ScreenshotManager
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


def test_phase1_clicks_consent_dialog_before_navigation():
    """Phase 1 should detect and tap consent-like dialog buttons (e.g., 同意)."""
    ai_driver = Mock()
    android_runner = Mock()
    screenshot_manager = Mock()

    android_runner.connect_remote_emulator.return_value = True
    android_runner.install_apk_remote.return_value = True
    android_runner.get_current_activity.return_value = "com.example/.MainActivity"

    ui_with_agree = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<hierarchy><node text="服务协议和隐私政策" clickable="false" bounds="[120,400][960,560]"/>'
        '<node text="同意" clickable="true" class="android.widget.Button" bounds="[420,1110][660,1180]"/>'
        "</hierarchy>"
    )
    ui_without_agree = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<hierarchy><node text="首页" clickable="false" bounds="[0,0][1080,200]"/></hierarchy>'
    )

    adb_responses = [
        "UI hierchary dumped to: /sdcard/window_dump.xml",
        ui_with_agree,
        "UI hierchary dumped to: /sdcard/window_dump.xml",
        ui_without_agree,
    ]
    android_runner.execute_adb_remote.side_effect = adb_responses
    screenshot_manager.capture.return_value = Mock()

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    with patch("modules.exploration_strategy.explorer.time.sleep", return_value=None):
        explorer.phase1_basic_setup(
            host="127.0.0.1",
            port=5555,
            apk_path="/tmp/app.apk",
            package_name="com.example",
        )

    android_runner.execute_tap.assert_any_call("127.0.0.1", 5555, 540, 1145)


def test_phase1_can_skip_upfront_permission_grant():
    """When configured, setup should avoid heavy grant_all_permissions call."""
    ai_driver = Mock()
    android_runner = Mock()
    screenshot_manager = Mock()
    android_runner.connect_remote_emulator.return_value = True
    android_runner.install_apk_remote.return_value = True
    android_runner.get_current_activity.return_value = "com.example/.MainActivity"
    android_runner.execute_adb_remote.side_effect = [
        "UI hierchary dumped to: /sdcard/window_dump.xml",
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy></hierarchy>',
    ]
    screenshot_manager.capture.return_value = Mock()

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)
    explorer.policy.skip_permission_grant = True

    with patch("modules.exploration_strategy.explorer.time.sleep", return_value=None):
        explorer.phase1_basic_setup(
            host="127.0.0.1",
            port=5555,
            apk_path="/tmp/app.apk",
            package_name="com.example",
        )

    android_runner.grant_all_permissions.assert_not_called()
    android_runner.launch_app.assert_called_once_with("127.0.0.1", 5555, "com.example")


def test_phase1_requires_target_app_foreground_after_launch():
    """Setup should fail fast when target app is not foreground after launch retries."""
    ai_driver = Mock()
    android_runner = Mock()
    screenshot_manager = Mock()
    android_runner.connect_remote_emulator.return_value = True
    android_runner.install_apk_remote.return_value = True
    android_runner.get_current_package.return_value = "com.android.launcher"
    screenshot_manager.capture.return_value = Mock()

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    with patch("modules.exploration_strategy.explorer.time.sleep", return_value=None):
        with pytest.raises(RuntimeError, match="foreground"):
            explorer.phase1_basic_setup(
                host="127.0.0.1",
                port=5555,
                apk_path="/tmp/app.apk",
                package_name="com.example",
            )


def test_phase1_fails_when_package_cannot_be_determined():
    """Setup should abort instead of exploring desktop when package name is unknown."""
    ai_driver = Mock()
    android_runner = Mock()
    screenshot_manager = Mock()

    android_runner.connect_remote_emulator.return_value = True
    android_runner.install_apk_remote.return_value = True
    android_runner.execute_adb_remote.side_effect = [
        "package:com.android.settings\npackage:com.android.chrome\n",
        "package:com.android.settings\npackage:com.android.chrome\n",
    ]

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    with patch("modules.exploration_strategy.explorer.time.sleep", return_value=None):
        with pytest.raises(RuntimeError, match="package name"):
            explorer.phase1_basic_setup(
                host="127.0.0.1",
                port=5555,
                apk_path="/tmp/app.apk",
                package_name=None,
            )


def test_phase3_handles_priority_dialog_before_ai_operation():
    """Autonomous explore should tap dialog CTA first instead of invoking AI step."""
    ai_driver = Mock()
    ai_driver.analyze_screenshot.return_value = "no"
    ai_driver.analyze_and_decide.return_value = Mock(
        type=Mock(value="Wait"),
        params={"duration": 1},
        description="wait",
    )
    android_runner = Mock()
    screenshot_manager = Mock()

    android_runner.take_screenshot_remote.return_value = b"fake_image"

    ui_with_allow = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<hierarchy><node text="允许" clickable="true" class="android.widget.Button" bounds="[460,1080][620,1160]"/></hierarchy>'
    )
    adb_responses = [
        "UI hierchary dumped to: /sdcard/window_dump.xml",
        ui_with_allow,
    ]
    android_runner.execute_adb_remote.side_effect = adb_responses
    screenshot_manager.capture.return_value = Mock()

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    with patch("modules.exploration_strategy.explorer.time.sleep", return_value=None):
        explorer.phase3_autonomous_explore("127.0.0.1", 5555, max_steps=1)

    android_runner.execute_tap.assert_any_call("127.0.0.1", 5555, 540, 1120)
    ai_driver.analyze_and_decide.assert_not_called()


def test_phase3_relaunches_target_app_when_activity_drifted():
    """When explorer leaves target package, it should relaunch target app first."""
    ai_driver = Mock()
    ai_driver.analyze_screenshot.return_value = "no"
    ai_driver.analyze_and_decide.return_value = Mock(
        type=Mock(value="Wait"),
        params={"duration": 1},
        description="wait",
    )

    android_runner = Mock()
    screenshot_manager = Mock()

    android_runner.take_screenshot_remote.return_value = b"fake_image"
    android_runner.get_current_activity.return_value = "com.google.android.apps.nexuslauncher/.NexusLauncherActivity"
    android_runner.execute_adb_remote.side_effect = [
        "UI hierchary dumped to: /sdcard/window_dump.xml",
        '<?xml version="1.0" encoding="UTF-8"?><hierarchy></hierarchy>',
    ]
    screenshot_manager.capture.return_value = Mock()

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)
    explorer.target_package = "com.example.target"

    with patch("modules.exploration_strategy.explorer.time.sleep", return_value=None):
        explorer.phase3_autonomous_explore("127.0.0.1", 5555, max_steps=1)

    android_runner.launch_app.assert_called_once_with("127.0.0.1", 5555, "com.example.target")
    ai_driver.analyze_and_decide.assert_not_called()


def test_execute_launch_operation_reuses_target_package():
    """Launch operation should relaunch current target package, not random app names."""
    ai_driver = Mock()
    android_runner = Mock()
    screenshot_manager = Mock()
    android_runner.execute_adb_remote.return_value = "Physical size: 1080x1920"

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)
    explorer.target_package = "com.example.target"

    op = Operation(type=OperationType.LAUNCH, params={"app": "微信"}, description="launch")
    explorer._execute_operation("127.0.0.1", 5555, op)

    android_runner.launch_app.assert_called_once_with("127.0.0.1", 5555, "com.example.target")


def test_should_skip_screen_uses_ui_keywords_not_ai_guess():
    """Login/payment pages should be detected from UI xml keywords."""
    ai_driver = Mock()
    android_runner = Mock()
    screenshot_manager = Mock()
    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    login_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<hierarchy>'
        '<node text="手机号登录" clickable="false" bounds="[10,10][100,100]"/>'
        '<node text="验证码" clickable="false" bounds="[10,120][100,180]"/>'
        "</hierarchy>"
    )
    android_runner.execute_adb_remote.side_effect = [
        "UI hierchary dumped to: /sdcard/window_dump.xml",
        login_xml,
    ]

    assert explorer._should_skip_screen("127.0.0.1", 5555) is True


def test_pick_ui_candidate_operation_prefers_positive_clickable_node():
    """UI fallback should select positive clickable nodes and ignore negative buttons."""
    ai_driver = Mock()
    android_runner = Mock()
    screenshot_manager = Mock()
    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hierarchy>"
        '<node text="取消" clickable="true" class="android.widget.Button" bounds="[50,1000][250,1080]"/>'
        '<node text="进入首页" clickable="true" class="android.widget.Button" bounds="[300,900][780,1000]"/>'
        "</hierarchy>"
    )
    android_runner.execute_adb_remote.side_effect = [
        "UI hierchary dumped to: /sdcard/window_dump.xml",
        xml,
        "Physical size: 1080x1920",
    ]

    op = explorer._pick_ui_candidate_operation("127.0.0.1", 5555)

    assert op is not None
    assert op.type == OperationType.TAP
    assert op.params["x"] == 540
    assert op.params["y"] == 950


def test_run_full_exploration_respects_env_max_steps(monkeypatch):
    """Autonomous phase should use APP_EXPLORATION_MAX_STEPS when provided."""
    ai_driver = Mock()
    android_runner = Mock()
    screenshot_manager = Mock()
    screenshot_manager.get_all_for_report.return_value = []
    screenshot_manager.save_to_minio.return_value = None

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)
    explorer.phase1_basic_setup = Mock(return_value=[])
    explorer.phase2_navigation_explore = Mock(return_value=[])
    explorer.phase3_autonomous_explore = Mock(return_value=[])
    explorer.phase4_scenario_test = Mock(return_value=[])

    monkeypatch.setenv("APP_EXPLORATION_MAX_STEPS", "20")
    result = explorer.run_full_exploration(
        emulator_config={"host": "127.0.0.1", "port": 5555},
        apk_info={"apk_path": "/tmp/app.apk"},
    )

    assert result.success is True
    explorer.phase3_autonomous_explore.assert_called_once()
    _, kwargs = explorer.phase3_autonomous_explore.call_args
    assert kwargs["max_steps"] == 20
    assert "deadline_ts" in kwargs


def test_run_full_exploration_uninstall_uses_detected_target_package():
    """Cleanup should uninstall detected target package even when apk_info package is missing."""
    ai_driver = Mock()
    android_runner = Mock()
    android_runner.execute_adb_remote.return_value = "Success"
    screenshot_manager = Mock()
    screenshot_manager.get_all_for_report.return_value = []
    screenshot_manager.save_to_minio.return_value = None

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    def _phase1(*args, **kwargs):
        explorer.target_package = "com.example.detected"
        return []

    explorer.phase1_basic_setup = Mock(side_effect=_phase1)
    explorer.phase2_navigation_explore = Mock(return_value=[])
    explorer.phase3_autonomous_explore = Mock(return_value=[])
    explorer.phase4_scenario_test = Mock(return_value=[])

    result = explorer.run_full_exploration(
        emulator_config={"host": "127.0.0.1", "port": 5555},
        apk_info={"apk_path": "/tmp/app.apk", "package_name": None},
    )

    assert result.success is True
    android_runner.execute_adb_remote.assert_called_with(
        "127.0.0.1",
        5555,
        "uninstall com.example.detected",
    )


def test_phase3_performs_form_input_and_submit_before_ai_wait():
    """When input fields are detected, explorer should fill and submit before passive AI actions."""
    ai_driver = Mock()
    ai_driver.analyze_and_decide.return_value = Operation(
        type=OperationType.WAIT,
        params={"duration": 1},
        description="wait",
    )
    android_runner = Mock()
    screenshot_manager = Mock()

    android_runner.take_screenshot_remote.return_value = b"fake_image"
    android_runner.get_current_activity.return_value = "com.example/.LoginActivity"
    android_runner.execute_adb_remote.side_effect = [
        "UI hierchary dumped to: /sdcard/window_dump.xml",
        (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<hierarchy>'
            '<node text="手机号" class="android.widget.EditText" clickable="true" focusable="true" '
            'bounds="[100,260][980,380]"/>'
            '<node text="登录" class="android.widget.Button" clickable="true" '
            'bounds="[260,900][820,1020]"/>'
            "</hierarchy>"
        ),
    ]
    screenshot_manager.capture.return_value = Mock()

    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)
    explorer.target_package = "com.example"

    with patch("modules.exploration_strategy.explorer.time.sleep", return_value=None):
        explorer.phase3_autonomous_explore("127.0.0.1", 5555, max_steps=1)

    android_runner.execute_input_text.assert_called_once_with("127.0.0.1", 5555, "13800138000")
    android_runner.execute_tap.assert_any_call("127.0.0.1", 5555, 540, 320)
    android_runner.execute_tap.assert_any_call("127.0.0.1", 5555, 540, 960)
    ai_driver.analyze_and_decide.assert_not_called()


def test_should_skip_screen_allows_login_page_with_input_candidates():
    """Login-like screens should not be skipped when form interaction is enabled."""
    ai_driver = Mock()
    android_runner = Mock()
    screenshot_manager = Mock()
    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    login_form_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<hierarchy>"
        '<node text="登录" clickable="false" bounds="[10,10][100,100]"/>'
        '<node text="手机号" class="android.widget.EditText" clickable="true" focusable="true" '
        'bounds="[100,260][980,380]"/>'
        '<node text="验证码" class="android.widget.EditText" clickable="true" focusable="true" '
        'bounds="[100,420][980,540]"/>'
        "</hierarchy>"
    )

    assert explorer._should_skip_screen("127.0.0.1", 5555, ui_xml=login_form_xml) is False


def test_execute_swipe_operation_uses_explicit_coordinates():
    """Swipe operation should use explicit start/end coordinates when provided."""
    ai_driver = Mock()
    android_runner = Mock()
    android_runner.execute_adb_remote.return_value = "Physical size: 1080x1920"
    screenshot_manager = Mock()
    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)

    op = Operation(
        type=OperationType.SWIPE,
        params={"start_x": 100, "start_y": 900, "end_x": 100, "end_y": 200},
        description="swipe up",
    )
    explorer._execute_operation("127.0.0.1", 5555, op)

    android_runner.execute_swipe.assert_called_once_with("127.0.0.1", 5555, 100, 900, 100, 200)


def test_decide_operation_with_timeout_returns_wait_fallback():
    """Slow AI decision should fallback to wait when timeout is exceeded."""
    ai_driver = Mock()

    def slow_decide(*args, **kwargs):
        time.sleep(3)
        return Operation(type=OperationType.TAP, params={"x": 1, "y": 1}, description="slow")

    ai_driver.analyze_and_decide.side_effect = slow_decide
    android_runner = Mock()
    screenshot_manager = Mock()
    explorer = AppExplorer(ai_driver, android_runner, screenshot_manager)
    explorer.policy.ai_step_timeout_seconds = 1

    begin = time.time()
    op = explorer._decide_operation_with_timeout(b"img", goal="explore")
    elapsed = time.time() - begin

    assert op.type == OperationType.WAIT
    assert "timeout" in op.description.lower()
    assert elapsed < 1.8
