"""App exploration strategy with mixed approach."""
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from typing import List, Dict, Optional, Tuple, Any, Set
from dataclasses import dataclass, field

from modules.ai_driver import AIDriver, Operation, OperationType
from modules.android_runner import AndroidRunner
from modules.screenshot_manager import ScreenshotManager, Screenshot
from .dialog_handler import DialogHandler
from .policy import ExplorationPolicy
from .recovery_manager import RecoveryConfig, RecoveryManager
from .state_detector import StateDetector
from .ui_explorer import UIExplorer

logger = logging.getLogger(__name__)


@dataclass
class ExplorationResult:
    """Result of app exploration."""
    total_steps: int
    screenshots: List[Dict]
    network_requests: List[Dict]
    activities_visited: List[str]
    success: bool
    error_message: Optional[str] = None
    phases_completed: List[str] = field(default_factory=list)


class AppExplorer:
    """Explore Android app with mixed strategy."""
    def __init__(
        self,
        ai_driver: AIDriver,
        android_runner: AndroidRunner,
        screenshot_manager: ScreenshotManager,
        policy: Optional[ExplorationPolicy] = None,
    ):
        """
        Initialize app explorer.

        Args:
            ai_driver: AI driver for intelligent decisions
            android_runner: Android device controller
            screenshot_manager: Screenshot manager
        """
        self.ai_driver = ai_driver
        self.android_runner = android_runner
        self.screenshot_manager = screenshot_manager
        self.policy = policy or ExplorationPolicy.from_env()
        self.exploration_history: List[Dict] = []
        self.activities_visited: List[str] = []
        self.target_package: Optional[str] = None
        self.clicked_ui_signatures: Set[str] = set()
        self.screen_action_counts: Dict[str, int] = defaultdict(int)
        self._apk_path: Optional[str] = None
        self.dialog_handler = DialogHandler()
        self.ui_explorer = UIExplorer(
            blacklist=self.policy.widget_blacklist,
            whitelist=self.policy.widget_whitelist,
        )
        self.state_detector = StateDetector(
            android_runner=self.android_runner,
            stagnant_threshold=self.policy.stagnant_threshold,
        )
        self.recovery_manager = RecoveryManager(
            RecoveryConfig(
                enable_clear_data=self.policy.enable_clear_data_recovery,
                enable_reinstall=self.policy.enable_reinstall_recovery,
                max_attempts=self.policy.max_recovery_attempts,
            )
        )

    def _get_foreground_package(self, host: str, port: int) -> str:
        """Get current foreground package with graceful fallback."""
        getter = getattr(self.android_runner, "get_current_package", None)
        if callable(getter):
            try:
                pkg = getter(host, port)
                if isinstance(pkg, str) and pkg.strip():
                    return pkg.strip()
            except Exception as exc:
                logger.debug("get_current_package failed: %s", exc)

        activity = self.android_runner.get_current_activity(host, port)
        if isinstance(activity, str) and "/" in activity:
            return activity.split("/", 1)[0].strip()
        return ""

    def _is_target_app_foreground(self, host: str, port: int) -> bool:
        """Check whether target package is currently in foreground."""
        if not self.target_package:
            return True
        current_pkg = self._get_foreground_package(host, port)
        return bool(current_pkg and current_pkg == self.target_package)

    def _capture_app_screenshot(
        self,
        host: str,
        port: int,
        stage: str,
        description: str,
        require_target: bool = True,
        relaunch_on_miss: bool = True,
    ) -> Optional[Screenshot]:
        """Capture screenshot only when target app is foreground."""
        if require_target and self.target_package:
            if not self._is_target_app_foreground(host, port):
                if relaunch_on_miss:
                    self._ensure_target_app_foreground(host, port)
            if not self._is_target_app_foreground(host, port):
                logger.warning(
                    "Skip screenshot %s: target app not foreground (target=%s, current=%s)",
                    stage,
                    self.target_package,
                    self._get_foreground_package(host, port) or "unknown",
                )
                return None

        return self.screenshot_manager.capture(
            stage=stage,
            description=description,
            emulator_host=host,
            emulator_port=port,
        )

    def phase1_basic_setup(self, host: str, port: int,
                          apk_path: str, package_name: Optional[str] = None) -> List[Screenshot]:
        """
        Phase 1: Basic setup - install, grant permissions, launch.

        Args:
            host: Emulator host
            port: Emulator port
            apk_path: Path to APK file
            package_name: Package name (optional, will be detected if None)

        Returns:
            List of screenshots from this phase
        """
        logger.info(f"Phase 1: Basic setup for {package_name or 'unknown package'}")
        screenshots = []

        # Connect to emulator
        if not self.android_runner.connect_remote_emulator(host, port):
            raise RuntimeError(f"Failed to connect to emulator {host}:{port}")

        time.sleep(2)  # Wait for connection

        # Get list of packages before installation
        packages_before = set()
        if not package_name:
            try:
                output = self.android_runner.execute_adb_remote(host, port, "shell pm list packages")
                packages_before = set(line.replace("package:", "").strip() for line in output.split('\n') if "package:" in line)
                logger.info(f"Packages before install: {len(packages_before)}")
            except Exception as e:
                logger.warning(f"Failed to list packages before install: {e}")

        # Install APK
        logger.info("Installing APK...")
        if not self.android_runner.install_apk_remote(host, port, apk_path):
            raise RuntimeError("Failed to install APK")

        # Screenshot: Installation complete
        screenshot = self.screenshot_manager.capture(
            stage="install",
            description="APK安装完成",
            emulator_host=host,
            emulator_port=port
        )
        if screenshot:
            screenshots.append(screenshot)

        time.sleep(2)

        # Detect package name if not provided
        if not package_name:
            try:
                output = self.android_runner.execute_adb_remote(host, port, "shell pm list packages")
                packages_after = set(line.replace("package:", "").strip() for line in output.split('\n') if "package:" in line)
                new_packages = packages_after - packages_before
                if new_packages:
                    package_name = list(new_packages)[0]
                    logger.info(f"Detected installed package: {package_name}")
                else:
                    logger.warning("Could not detect installed package, proceeding without package name")
            except Exception as e:
                logger.warning(f"Failed to detect package name: {e}")

        # Grant all permissions (if package name available)
        if package_name:
            self.target_package = package_name
            logger.info(f"Granting permissions for {package_name}...")
            self.android_runner.grant_all_permissions(host, port, package_name)

            # Launch app
            logger.info(f"Launching app {package_name}...")
            self.android_runner.launch_app(host, port, package_name)
            time.sleep(3)  # Wait for app to start
        else:
            logger.warning("No package name available, skipping permission grant and app launch")
            logger.info("Attempting to launch the most recently installed app...")
            # Try to launch the last installed app
            try:
                self.android_runner.execute_adb_remote(host, port, "shell monkey -p com. -c android.intent.category.LAUNCHER 1")
                time.sleep(3)
            except Exception as e:
                logger.warning(f"Failed to launch app: {e}")

        # Screenshot: App launched
        screenshot = self._capture_app_screenshot(
            host=host,
            port=port,
            stage="launch",
            description="应用启动界面",
            require_target=True,
        )
        if screenshot:
            screenshots.append(screenshot)

        # Handle startup privacy/permission dialogs before deeper exploration.
        startup_screenshots = self._handle_startup_dialogs(
            host,
            port,
            max_attempts=min(10, self.policy.max_recovery_attempts + 2),
        )
        screenshots.extend(startup_screenshots)

        # Record activity
        activity = self.android_runner.get_current_activity(host, port)
        if activity and (
            not self.target_package or self.target_package in activity
        ):
            self.activities_visited.append(activity)

        self.exploration_history.append({
            "phase": "setup",
            "action": "install_and_launch",
            "success": True
        })

        return screenshots

    def phase2_navigation_explore(self, host: str, port: int) -> List[Screenshot]:
        """
        Phase 2: Explore navigation elements (tabs, menus).

        Args:
            host: Emulator host
            port: Emulator port

        Returns:
            List of screenshots
        """
        logger.info("Phase 2: Navigation exploration")
        screenshots = []

        # Take initial screenshot
        screenshot = self._capture_app_screenshot(
            host=host,
            port=port,
            stage="explore_start",
            description="开始探索首页",
            require_target=True,
        )
        if screenshot:
            screenshots.append(screenshot)

        # Common navigation positions to try (bottom nav bar typical positions)
        screen_width, screen_height = self._get_display_size(host, port)
        nav_y = int(screen_height * 0.92)
        nav_positions = [
            int(screen_width * 0.2),
            int(screen_width * 0.4),
            int(screen_width * 0.6),
            int(screen_width * 0.8),
        ]

        for i, x in enumerate(nav_positions):
            logger.info(f"Tapping navigation position {i+1}")
            if not self._ensure_target_app_foreground(host, port):
                logger.warning("Skip nav tap %s: target app not foreground", i + 1)
                continue

            # Tap
            self.android_runner.execute_tap(host, port, x, nav_y)
            time.sleep(2)  # Wait for transition

            # Screenshot
            screenshot = self._capture_app_screenshot(
                host=host,
                port=port,
                stage=f"nav_tab_{i+1}",
                description=f"点击导航栏第{i+1}个Tab",
                require_target=True,
            )
            if screenshot:
                screenshots.append(screenshot)

            # Record activity
            activity = self.android_runner.get_current_activity(host, port)
            if activity and (
                activity not in self.activities_visited
                and (not self.target_package or self.target_package in activity)
            ):
                self.activities_visited.append(activity)

            self.exploration_history.append({
                "phase": "navigation",
                "action": f"tap_nav_{i+1}",
                "position": (x, nav_y)
            })

        return screenshots

    def phase3_autonomous_explore(self, host: str, port: int,
                                  max_steps: int = 50) -> List[Screenshot]:
        """
        Phase 3: Autonomous exploration driven by AI.

        Args:
            host: Emulator host
            port: Emulator port
            max_steps: Maximum exploration steps

        Returns:
            List of screenshots
        """
        logger.info(f"Phase 3: Autonomous exploration (max {max_steps} steps)")
        screenshots = []

        consecutive_errors = 0
        max_consecutive_errors = 5
        stagnant_steps = 0
        passive_steps = 0
        recovery_count = 0

        for step in range(max_steps):
            logger.info(f"Exploration step {step + 1}/{max_steps}")

            try:
                if not self._ensure_target_app_foreground(host, port):
                    self.exploration_history.append({
                        "phase": "autonomous",
                        "step": step + 1,
                        "operation": "Recovery",
                        "description": "Relaunch target package to keep exploration focused",
                        "params": {"package": self.target_package},
                    })
                    continue

                # Collect raw artifacts for state and decision making.
                ui_xml = self._get_ui_dump_xml(host, port)
                screenshot_data = self.android_runner.take_screenshot_remote(host, port)

                if not screenshot_data:
                    logger.warning("Failed to capture screenshot")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("Too many consecutive errors, stopping")
                        break
                    continue

                state = self.state_detector.snapshot(
                    host=host,
                    port=port,
                    screenshot_data=screenshot_data,
                    ui_xml=ui_xml,
                )
                self.state_detector.record(state)
                if self.state_detector.is_stagnant(state):
                    stagnant_steps += 1
                else:
                    stagnant_steps = 0

                dialog_action = self._tap_priority_dialog_action(host, port, ui_xml=ui_xml)
                if dialog_action:
                    logger.info("Handled priority dialog action: %s", dialog_action)
                    time.sleep(1.5)
                    consecutive_errors = 0
                    screenshot = self._capture_app_screenshot(
                        host=host,
                        port=port,
                        stage=f"auto_priority_{step+1}",
                        description=f"优先处理弹窗: {dialog_action}",
                        require_target=True,
                    )
                    if screenshot:
                        screenshots.append(screenshot)
                    self.exploration_history.append({
                        "phase": "autonomous",
                        "step": step + 1,
                        "operation": "Tap",
                        "description": f"Priority dialog action: {dialog_action}",
                        "params": {},
                    })
                    continue

                # Cap taps per page-state to avoid dead loops on a single screen.
                screen_key = f"{state.activity}|{state.ui_hash}"
                if self.screen_action_counts[screen_key] >= self.policy.max_clicks_per_screen:
                    recovery_action = self.recovery_manager.next_action(
                        stagnation_count=stagnant_steps + 1,
                        error_count=consecutive_errors,
                    )
                    self._execute_recovery_action(host, port, recovery_action.kind)
                    recovery_count += 1
                    self.exploration_history.append({
                        "phase": "autonomous",
                        "step": step + 1,
                        "operation": "Recovery",
                        "description": f"Screen click budget exceeded: {recovery_action.kind}",
                        "params": {"screen": screen_key},
                    })
                    if recovery_count >= self.policy.max_recovery_attempts:
                        logger.warning("Reached max recovery attempts, stopping exploration")
                        break
                    continue

                # AI analyzes and decides next action
                operation = self.ai_driver.analyze_and_decide(
                    screenshot_data,
                    self.exploration_history,
                    goal="深度探索应用功能，触发更多网络请求"
                )

                if operation.type in (OperationType.WAIT, OperationType.LAUNCH, OperationType.HOME):
                    passive_steps += 1
                else:
                    passive_steps = 0

                ui_tap_operation = self._pick_ui_candidate_operation(
                    host,
                    port,
                    ui_xml=ui_xml,
                )
                if ui_tap_operation:
                    if passive_steps >= 1 or stagnant_steps >= 1:
                        logger.info(
                            "Switching from passive AI operation (%s) to UI-guided tap fallback",
                            operation.type.value,
                        )
                        operation = ui_tap_operation
                        passive_steps = 0
                    elif operation.type in (OperationType.WAIT, OperationType.HOME, OperationType.LAUNCH):
                        operation = ui_tap_operation

                # When screen keeps repeating, force recovery actions to break dead loops.
                if stagnant_steps >= self.policy.stagnant_threshold or (
                    operation.type == OperationType.WAIT and stagnant_steps >= 1
                ):
                    recovery_action = self.recovery_manager.next_action(
                        stagnation_count=stagnant_steps,
                        error_count=consecutive_errors,
                    )
                    logger.info(
                        "Detected stagnation (step=%s, stagnant=%s), running recovery: %s",
                        step + 1,
                        stagnant_steps,
                        recovery_action.kind,
                    )
                    self._execute_recovery_action(host, port, recovery_action.kind)
                    recovery_count += 1
                    self.exploration_history.append({
                        "phase": "autonomous",
                        "step": step + 1,
                        "operation": "Recovery",
                        "description": recovery_action.reason,
                        "params": {"kind": recovery_action.kind},
                    })
                    if recovery_count >= self.policy.max_recovery_attempts:
                        logger.warning("Reached max recovery attempts, stopping exploration")
                        break
                    continue

                # Check if should skip (login/payment/auth screens)
                if self._should_skip_screen(host, port, ui_xml=ui_xml):
                    logger.info("Skipping screen (login/payment detected)")
                    self.android_runner.press_back(host, port)
                    time.sleep(1)
                    continue

                # Execute operation
                self._execute_operation(host, port, operation)
                self.screen_action_counts[screen_key] += 1

                # Reset error counter on success
                consecutive_errors = 0

                # Wait for UI to settle
                time.sleep(2)

                # Capture result screenshot
                screenshot = self._capture_app_screenshot(
                    host=host,
                    port=port,
                    stage=f"auto_step_{step+1}",
                    description=f"{operation.type.value}: {operation.description}",
                    require_target=True,
                )
                if screenshot:
                    screenshots.append(screenshot)

                # Record in history
                self.exploration_history.append({
                    "phase": "autonomous",
                    "step": step + 1,
                    "operation": operation.type.value,
                    "description": operation.description,
                    "params": operation.params,
                    "state": {
                        "activity": state.activity,
                        "window": state.window,
                        "ui_hash": state.ui_hash,
                        "screenshot_hash": state.screenshot_hash,
                    },
                })

                # Record activity
                activity = self.android_runner.get_current_activity(host, port)
                if activity and (
                    activity not in self.activities_visited
                    and (not self.target_package or self.target_package in activity)
                ):
                    self.activities_visited.append(activity)
                    logger.info(f"Discovered new activity: {activity}")

            except Exception as e:
                logger.error(f"Error in exploration step {step + 1}: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many errors, stopping autonomous exploration")
                    break

        return screenshots

    def _ensure_target_app_foreground(self, host: str, port: int) -> bool:
        """Ensure current foreground activity belongs to target package."""
        if not self.target_package:
            return True

        current_pkg = self._get_foreground_package(host, port)
        if current_pkg == self.target_package:
            return True

        logger.info(
            "Foreground drift detected: %s (target=%s), relaunching target app",
            current_pkg or "unknown",
            self.target_package,
        )
        self.android_runner.launch_app(host, port, self.target_package)
        time.sleep(2)

        current_pkg = self._get_foreground_package(host, port)
        if current_pkg == self.target_package:
            return True

        logger.warning(
            "Failed to restore target app to foreground (target=%s, current=%s)",
            self.target_package,
            current_pkg or "unknown",
        )
        return False

    def _pick_ui_candidate_operation(
        self,
        host: str,
        port: int,
        ui_xml: Optional[str] = None,
    ) -> Optional[Operation]:
        """Pick a not-yet-clicked clickable UI element as a fallback tap operation."""
        if ui_xml is None:
            ui_xml = self._get_ui_dump_xml(host, port)
        if not ui_xml:
            return None

        best = self.ui_explorer.pick_best(ui_xml, self.clicked_ui_signatures)
        if not best:
            return None

        self.clicked_ui_signatures.add(best.signature)
        return Operation(
            type=OperationType.TAP,
            params={"x": best.x, "y": best.y},
            description=f"UI-guided tap ({best.reason})",
        )

    def _get_display_size(self, host: str, port: int) -> Tuple[int, int]:
        """Get display size from emulator; fallback to 1080x1920."""
        output = self.android_runner.execute_adb_remote(host, port, "shell wm size")
        match = re.search(r"(\d+)\s*x\s*(\d+)", output or "")
        if match:
            return int(match.group(1)), int(match.group(2))
        return 1080, 1920

    def _parse_bounds_center(self, bounds: str) -> Optional[Tuple[int, int]]:
        """Parse Android bounds string like [x1,y1][x2,y2] and return center point."""
        match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
        if not match:
            return None
        x1, y1, x2, y2 = map(int, match.groups())
        return ((x1 + x2) // 2, (y1 + y2) // 2)

    def _get_ui_dump_xml(self, host: str, port: int) -> str:
        """Dump current UI hierarchy and return XML content."""
        dumper = getattr(self.android_runner, "dump_ui_hierarchy", None)
        if callable(dumper):
            result = dumper(host, port)
            if isinstance(result, str) and "<hierarchy" in result:
                return result
        self.android_runner.execute_adb_remote(host, port, "shell uiautomator dump /sdcard/window_dump.xml")
        return self.android_runner.execute_adb_remote(host, port, "shell cat /sdcard/window_dump.xml")

    def _find_priority_dialog_action(self, ui_xml: str) -> Optional[Dict[str, Any]]:
        """Find highest-priority dialog action (agree/allow/continue) from UI XML."""
        candidate = self.dialog_handler.find_action(ui_xml)
        if not candidate:
            return None
        return {
            "x": candidate.x,
            "y": candidate.y,
            "label": candidate.label,
            "category": candidate.category,
            "score": candidate.score,
        }

    def _tap_priority_dialog_action(
        self,
        host: str,
        port: int,
        ui_xml: Optional[str] = None,
    ) -> Optional[str]:
        """Tap priority dialog action if found, and return tapped label."""
        if ui_xml is None:
            ui_xml = self._get_ui_dump_xml(host, port)
        candidate = self._find_priority_dialog_action(ui_xml)
        if not candidate:
            return None

        self.android_runner.execute_tap(host, port, candidate["x"], candidate["y"])
        return candidate["label"]

    def _handle_startup_dialogs(self, host: str, port: int, max_attempts: int = 6) -> List[Screenshot]:
        """Dismiss startup dialogs repeatedly until no priority action is found."""
        screenshots: List[Screenshot] = []
        for attempt in range(max_attempts):
            if not self._ensure_target_app_foreground(host, port):
                break
            action = self._tap_priority_dialog_action(host, port)
            if not action:
                break

            logger.info("Startup dialog handled (%s/%s): %s", attempt + 1, max_attempts, action)
            time.sleep(1.5)
            screenshot = self._capture_app_screenshot(
                host=host,
                port=port,
                stage=f"startup_dialog_{attempt+1}",
                description=f"弹窗处理: {action}",
                require_target=True,
            )
            if screenshot:
                screenshots.append(screenshot)

            self.exploration_history.append({
                "phase": "setup",
                "action": "dialog_accept",
                "description": action,
                "success": True,
            })
        return screenshots

    def _get_recovery_operation(self, step: int, stagnant_steps: int) -> Operation:
        """Generate deterministic fallback operations when AI is stuck on same screen."""
        # Cycle through swipe up -> tap center -> back to maximize navigation diversity.
        mode = (step + stagnant_steps) % 3
        if mode == 0:
            return Operation(
                type=OperationType.SWIPE,
                params={"direction": "up"},
                description="Recovery swipe up to discover scrollable content",
            )
        if mode == 1:
            return Operation(
                type=OperationType.TAP,
                params={"x": 540, "y": 960},
                description="Recovery tap center to enter candidate feature entry",
            )
        return Operation(
            type=OperationType.BACK,
            params={},
            description="Recovery back to leave blocked page",
        )

    def _execute_recovery_action(self, host: str, port: int, action_kind: str) -> None:
        """Execute recovery action selected by recovery manager."""
        if action_kind == "back":
            self.android_runner.press_back(host, port)
            return

        if action_kind == "home_relaunch":
            self.android_runner.press_home(host, port)
            if self.target_package:
                time.sleep(1)
                self.android_runner.launch_app(host, port, self.target_package)
            return

        if action_kind == "force_stop_relaunch":
            if self.target_package:
                stopper = getattr(self.android_runner, "force_stop_app", None)
                if callable(stopper):
                    stopper(host, port, self.target_package)
                else:
                    self.android_runner.execute_adb_remote(
                        host, port, f"shell am force-stop {self.target_package}"
                    )
                time.sleep(1)
                self.android_runner.launch_app(host, port, self.target_package)
            return

        if action_kind == "clear_data_relaunch":
            if self.target_package:
                clearer = getattr(self.android_runner, "clear_app_data", None)
                if callable(clearer):
                    clearer(host, port, self.target_package)
                else:
                    self.android_runner.execute_adb_remote(
                        host, port, f"shell pm clear {self.target_package}"
                    )
                time.sleep(1)
                self.android_runner.launch_app(host, port, self.target_package)
            return

        if action_kind == "reinstall_app":
            if self._apk_path:
                self.android_runner.install_apk_remote(host, port, self._apk_path)
                if self.target_package:
                    self.android_runner.grant_all_permissions(host, port, self.target_package)
                    self.android_runner.launch_app(host, port, self.target_package)
            return

    def phase4_scenario_test(self, host: str, port: int) -> List[Screenshot]:
        """
        Phase 4: Test specific scenarios (search, playback, etc.).

        Args:
            host: Emulator host
            port: Emulator port

        Returns:
            List of screenshots
        """
        logger.info("Phase 4: Scenario testing")
        screenshots = []

        # Try common scenarios
        scenarios = [
            ("search", self._test_search_scenario),
            ("scroll", self._test_scroll_scenario),
        ]

        for scenario_name, scenario_func in scenarios:
            try:
                logger.info(f"Testing scenario: {scenario_name}")
                scenario_screenshots = scenario_func(host, port)
                screenshots.extend(scenario_screenshots)
            except Exception as e:
                logger.warning(f"Scenario {scenario_name} failed: {e}")

        return screenshots

    def _execute_operation(self, host: str, port: int, operation: Operation) -> None:
        """Execute an AI operation on the device."""
        op_type = operation.type.value
        params = operation.params or {}
        screen_w, screen_h = self._get_display_size(host, port)

        if op_type == "Tap":
            x = int(params.get("x", screen_w // 2))
            y = int(params.get("y", screen_h // 2))
            x = max(0, min(x, screen_w - 1))
            y = max(0, min(y, screen_h - 1))
            self.android_runner.execute_tap(host, port, x, y)

        elif op_type == "Swipe":
            direction = params.get("direction", "up")
            # Swipe from center
            if direction == "up":
                self.android_runner.execute_swipe(host, port, 540, 1500, 540, 500)
            elif direction == "down":
                self.android_runner.execute_swipe(host, port, 540, 500, 540, 1500)
            elif direction == "left":
                self.android_runner.execute_swipe(host, port, 1000, 960, 100, 960)
            elif direction == "right":
                self.android_runner.execute_swipe(host, port, 100, 960, 1000, 960)

        elif op_type == "Type":
            text = params.get("text", "")
            self.android_runner.execute_input_text(host, port, text)

        elif op_type == "Back":
            self.android_runner.press_back(host, port)

        elif op_type == "Home":
            self.android_runner.press_home(host, port)

        elif op_type == "Wait":
            duration = params.get("duration", 2)
            try:
                duration = float(duration)
            except Exception:
                duration = 2
            duration = max(0.5, min(duration, 8))
            time.sleep(duration)

        elif op_type == "Launch":
            # Keep exploration focused on target app instead of launching unrelated apps.
            if self.target_package:
                self.android_runner.launch_app(host, port, self.target_package)
            else:
                self.android_runner.press_home(host, port)

    def _should_skip_screen(self, host: str, port: int, ui_xml: Optional[str] = None) -> bool:
        """Check if current screen is sensitive auth/payment flow that should be skipped."""
        if ui_xml is None:
            ui_xml = self._get_ui_dump_xml(host, port)
        if not isinstance(ui_xml, str) or not ui_xml or "<hierarchy" not in ui_xml:
            return False

        keywords = self.policy.skip_keywords
        try:
            root = ET.fromstring(ui_xml)
        except ET.ParseError:
            return False

        hit_count = 0
        for node in root.iter("node"):
            text = (node.attrib.get("text") or "").strip()
            content_desc = (node.attrib.get("content-desc") or "").strip()
            label = f"{text} {content_desc}".strip()
            if any(token in label for token in keywords):
                hit_count += 1
                if hit_count >= 2:
                    return True
        return False

    def _test_search_scenario(self, host: str, port: int) -> List[Screenshot]:
        """Test search functionality."""
        screenshots = []

        # Try to find and click search button (usually top right or in menu)
        # Common search icon positions
        search_positions = [
            (1000, 150),  # Top right
            (540, 150),   # Top center
        ]

        for x, y in search_positions:
            if not self._ensure_target_app_foreground(host, port):
                logger.warning("Skip search scenario step: target app not foreground")
                break
            self.android_runner.execute_tap(host, port, x, y)
            time.sleep(1)

            screenshot = self._capture_app_screenshot(
                host=host,
                port=port,
                stage="search_attempt",
                description="尝试打开搜索",
                require_target=True,
            )
            if screenshot:
                screenshots.append(screenshot)

        return screenshots

    def _test_scroll_scenario(self, host: str, port: int) -> List[Screenshot]:
        """Test scrolling."""
        screenshots = []

        # Scroll down multiple times
        for i in range(3):
            if not self._ensure_target_app_foreground(host, port):
                logger.warning("Skip scroll scenario step: target app not foreground")
                break
            self.android_runner.execute_swipe(host, port, 540, 1500, 540, 500)
            time.sleep(1)

            screenshot = self._capture_app_screenshot(
                host=host,
                port=port,
                stage=f"scroll_{i+1}",
                description=f"向下滚动第{i+1}次",
                require_target=True,
            )
            if screenshot:
                screenshots.append(screenshot)

        return screenshots

    def run_full_exploration(self, emulator_config: Dict, apk_info: Dict) -> ExplorationResult:
        """
        Run complete exploration with all phases.

        Args:
            emulator_config: {"host": "10.16.148.66", "port": 5555}
            apk_info: {"apk_path": "/path/to/file.apk", "package_name": "com.example"}

        Returns:
            ExplorationResult with all data
        """
        host = emulator_config["host"]
        port = emulator_config["port"]
        apk_path = apk_info["apk_path"]
        package_name = apk_info.get("package_name")  # 使用get方法,允许为None
        try:
            max_steps = int(os.getenv("APP_EXPLORATION_MAX_STEPS", str(self.policy.max_steps)))
        except ValueError:
            max_steps = self.policy.max_steps
        max_steps = max(5, min(max_steps, 500))
        self._apk_path = apk_path
        self.screen_action_counts.clear()
        self.clicked_ui_signatures.clear()

        all_screenshots = []
        phases_completed = []
        error_message = None

        try:
            # Phase 1: Setup
            screenshots = self.phase1_basic_setup(host, port, apk_path, package_name)
            all_screenshots.extend(screenshots)
            phases_completed.append("setup")

            # Phase 2: Navigation
            screenshots = self.phase2_navigation_explore(host, port)
            all_screenshots.extend(screenshots)
            phases_completed.append("navigation")

            # Phase 3: Autonomous
            screenshots = self.phase3_autonomous_explore(host, port, max_steps=max_steps)
            all_screenshots.extend(screenshots)
            phases_completed.append("autonomous")

            # Phase 4: Scenarios
            screenshots = self.phase4_scenario_test(host, port)
            all_screenshots.extend(screenshots)
            phases_completed.append("scenarios")

            success = True

        except Exception as e:
            logger.error(f"Exploration failed: {e}")
            success = False
            error_message = str(e)

        # Upload all screenshots to MinIO
        for screenshot in all_screenshots:
            self.screenshot_manager.save_to_minio(screenshot)

        # Cleanup: Uninstall the app after analysis
        if package_name:
            try:
                logger.info(f"Uninstalling app {package_name}...")
                output = self.android_runner.execute_adb_remote(host, port, f"uninstall {package_name}")
                if "Success" in output:
                    logger.info(f"Successfully uninstalled {package_name}")
                else:
                    logger.warning(f"Failed to uninstall {package_name}: {output}")
            except Exception as e:
                logger.warning(f"Error during app cleanup: {e}")
        else:
            logger.warning("Package name not available, skipping uninstall")

        return ExplorationResult(
            total_steps=len(self.exploration_history),
            screenshots=self.screenshot_manager.get_all_for_report(),
            network_requests=[],  # Will be filled by traffic monitor
            activities_visited=self.activities_visited,
            success=success,
            error_message=error_message,
            phases_completed=phases_completed
        )
