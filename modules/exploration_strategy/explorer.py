"""App exploration strategy with mixed approach."""
import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
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

SPECIAL_PERMISSION_PACKAGES = {
    "com.android.settings",
    "com.android.permissioncontroller",
    "com.google.android.permissioncontroller",
}


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
    history: List[Dict[str, Any]] = field(default_factory=list)
    permission_summary: Dict[str, Any] = field(default_factory=dict)


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
        self.filled_input_signatures: Set[str] = set()
        self.screen_action_counts: Dict[str, int] = defaultdict(int)
        self.screen_form_action_counts: Dict[str, int] = defaultdict(int)
        self._apk_path: Optional[str] = None
        self._captured_screenshot_count: int = 0
        self._permission_summary: Dict[str, Any] = {
            "requested_permissions": [],
            "granted_permissions": [],
            "failed_permissions": [],
        }
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

    def _list_third_party_packages(self, host: str, port: int) -> Set[str]:
        """List third-party packages to help detect newly installed target app."""
        output = self.android_runner.execute_adb_remote(host, port, "shell pm list packages -3")
        return {
            line.replace("package:", "").strip()
            for line in (output or "").split("\n")
            if "package:" in line
        }

    def _launch_target_with_verification(
        self,
        host: str,
        port: int,
        package_name: str,
        activity_name: Optional[str] = None,
        retries: int = 3,
    ) -> None:
        """Launch target app and require it to become foreground."""
        attempts = max(1, retries)
        last_foreground = ""
        for attempt in range(1, attempts + 1):
            retry_activity = activity_name if attempt == 1 else None
            self.android_runner.launch_app(host, port, package_name, activity_name=retry_activity)
            time.sleep(2)
            current_pkg = self._get_foreground_package(host, port)
            if current_pkg == package_name:
                return
            last_foreground = current_pkg or ""
            logger.warning(
                "Launch verification failed (%s/%s): target=%s current=%s",
                attempt,
                attempts,
                package_name,
                current_pkg or "unknown",
            )
            if attempt < attempts:
                self.android_runner.press_home(host, port)
                time.sleep(1)

        raise RuntimeError(
            f"Target app launch failed: {package_name} not foreground "
            f"(current={last_foreground or 'unknown'})"
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

        if self._captured_screenshot_count >= self.policy.total_screenshot_budget:
            logger.info(
                "Skip screenshot %s: total screenshot budget reached (%s)",
                stage,
                self.policy.total_screenshot_budget,
            )
            return None

        screenshot = self.screenshot_manager.capture(
            stage=stage,
            description=description,
            emulator_host=host,
            emulator_port=port,
        )
        if screenshot:
            self._captured_screenshot_count += 1
        return screenshot

    def _record_action(self, entry: Dict[str, Any]) -> bool:
        """Append action history only when global action budget allows it."""
        if len(self.exploration_history) >= self.policy.total_action_budget:
            logger.info(
                "Skip action record: total action budget reached (%s)",
                self.policy.total_action_budget,
            )
            return False
        self.exploration_history.append(entry)
        return True

    def _action_budget_remaining(self) -> bool:
        """Check whether total action budget still allows more actions."""
        return len(self.exploration_history) < self.policy.total_action_budget

    def phase1_basic_setup(
        self,
        host: str,
        port: int,
        apk_path: str,
        package_name: Optional[str] = None,
        activity_name: Optional[str] = None,
    ) -> List[Screenshot]:
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
                packages_before = self._list_third_party_packages(host, port)
                logger.info(f"Packages before install: {len(packages_before)}")
            except Exception as e:
                logger.warning(f"Failed to list packages before install: {e}")

        # Install APK
        logger.info("Installing APK...")
        if not self.android_runner.install_apk_remote(host, port, apk_path):
            raise RuntimeError("Failed to install APK")

        # Screenshot: Installation complete
        screenshot = self._capture_app_screenshot(
            stage="install",
            description="APK安装完成",
            host=host,
            port=port,
            require_target=False,
        )
        if screenshot:
            screenshots.append(screenshot)

        time.sleep(2)

        # Detect package name if not provided
        if not package_name:
            try:
                packages_after = self._list_third_party_packages(host, port)
                new_packages = packages_after - packages_before
                if new_packages:
                    package_name = sorted(new_packages)[0]
                    logger.info(f"Detected installed package: {package_name}")
                else:
                    logger.error("Could not detect installed package after APK install")
            except Exception as e:
                logger.warning(f"Failed to detect package name: {e}")

        if not package_name:
            raise RuntimeError(
                "Unable to determine target package name after installation; "
                "abort exploration to avoid operating on launcher/home screen"
            )

        # Grant all permissions and launch target app with foreground verification.
        self.target_package = package_name
        if self.policy.skip_permission_grant:
            logger.info(
                "Skip upfront permission grant for %s (APP_EXPLORATION_SKIP_PERMISSION_GRANT=true)",
                package_name,
            )
        else:
            logger.info(f"Granting permissions for {package_name}...")
            grant_summary = self.android_runner.grant_all_permissions(host, port, package_name)
            self._merge_permission_summary(grant_summary)

        logger.info(f"Launching app {package_name}...")
        self._launch_target_with_verification(host, port, package_name, activity_name=activity_name)

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

        self._record_action({
            "phase": "setup",
            "action": "install_and_launch",
            "success": True
        })

        return screenshots

    def phase2_navigation_explore(
        self,
        host: str,
        port: int,
        deadline_ts: Optional[float] = None,
    ) -> List[Screenshot]:
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
            if not self._within_deadline(deadline_ts):
                logger.info("Phase 2 stopped due to time budget")
                break
            if not self._action_budget_remaining():
                logger.info("Phase 2 stopped due to total action budget")
                break
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

            self._record_action({
                "phase": "navigation",
                "action": f"tap_nav_{i+1}",
                "position": (x, nav_y)
            })

            # Each navigation tab does one additional interaction to increase coverage.
            if not self._within_deadline(deadline_ts):
                continue
            self.android_runner.execute_swipe(
                host,
                port,
                int(screen_width * 0.5),
                int(screen_height * 0.82),
                int(screen_width * 0.5),
                int(screen_height * 0.35),
            )
            time.sleep(1)

            screenshot = self._capture_app_screenshot(
                host=host,
                port=port,
                stage=f"nav_tab_{i+1}_scroll",
                description=f"Tab{i+1} 内部滚动触发内容加载",
                require_target=True,
            )
            if screenshot:
                screenshots.append(screenshot)

            # Try one clickable entry point from current tab, then backtrack.
            ui_xml = self._get_ui_dump_xml(host, port)
            op = self._pick_ui_candidate_operation(host, port, ui_xml=ui_xml)
            if op:
                self._execute_operation(host, port, op)
                time.sleep(1.5)
                screenshot = self._capture_app_screenshot(
                    host=host,
                    port=port,
                    stage=f"nav_tab_{i+1}_entry",
                    description=f"Tab{i+1} 入口探索: {op.description}",
                    require_target=True,
                )
                if screenshot:
                    screenshots.append(screenshot)
                self.android_runner.press_back(host, port)
                time.sleep(0.8)
            self._record_current_activity(host, port)

        return screenshots

    @staticmethod
    def _within_deadline(deadline_ts: Optional[float]) -> bool:
        """Check whether the runtime budget still allows more actions."""
        if deadline_ts is None:
            return True
        return time.time() < deadline_ts

    def _record_current_activity(self, host: str, port: int) -> None:
        """Record current activity into visited set when it belongs to target app."""
        activity = self.android_runner.get_current_activity(host, port)
        if activity and (
            activity not in self.activities_visited
            and (not self.target_package or self.target_package in activity)
        ):
            self.activities_visited.append(activity)

    def phase3_autonomous_explore(
        self,
        host: str,
        port: int,
        max_steps: int = 50,
        deadline_ts: Optional[float] = None,
    ) -> List[Screenshot]:
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
        dialog_action_counts: Dict[str, int] = defaultdict(int)

        for step in range(max_steps):
            if not self._within_deadline(deadline_ts):
                logger.info("Phase 3 stopped due to time budget")
                break
            if not self._action_budget_remaining():
                logger.info("Phase 3 stopped due to total action budget")
                break
            logger.info(f"Exploration step {step + 1}/{max_steps}")

            try:
                if not self._ensure_target_app_foreground(host, port):
                    self._record_action({
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

                screen_key = f"{state.activity}|{state.ui_hash}"
                input_candidates = (
                    self._find_input_candidates(ui_xml)
                    if self.policy.enable_form_interaction
                    else []
                )
                has_form_candidates = bool(input_candidates)

                dialog_candidate = self._find_priority_dialog_action(ui_xml)
                if dialog_candidate:
                    dialog_key = f"{screen_key}|{dialog_candidate['label']}"
                    repeat_limit = (
                        self.policy.dialog_repeat_limit_with_form
                        if has_form_candidates
                        else self.policy.dialog_repeat_limit
                    )
                    repeat_count = dialog_action_counts[dialog_key]
                    if repeat_count >= repeat_limit:
                        logger.info(
                            "Skip repeated priority dialog action: %s (count=%s, limit=%s)",
                            dialog_candidate["label"],
                            repeat_count,
                            repeat_limit,
                        )
                    else:
                        self.android_runner.execute_tap(
                            host,
                            port,
                            dialog_candidate["x"],
                            dialog_candidate["y"],
                        )
                        dialog_action_counts[dialog_key] = repeat_count + 1
                        dialog_action = dialog_candidate["label"]
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
                        self._record_action({
                            "phase": "autonomous",
                            "step": step + 1,
                            "operation": "Tap",
                            "description": f"Priority dialog action: {dialog_action}",
                            "params": {},
                        })
                        continue

                # Prefer form interactions before generic tapping to unlock deeper flows.
                if (
                    self.policy.enable_form_interaction
                    and has_form_candidates
                    and self.screen_form_action_counts[screen_key] < self.policy.max_form_interactions_per_screen
                ):
                    form_action = self._perform_form_interaction(
                        host=host,
                        port=port,
                        ui_xml=ui_xml,
                        candidates=input_candidates,
                    )
                    if form_action:
                        self.screen_form_action_counts[screen_key] += 1
                        consecutive_errors = 0
                        passive_steps = 0
                        stagnant_steps = 0
                        time.sleep(1.2)
                        screenshot = self._capture_app_screenshot(
                            host=host,
                            port=port,
                            stage=f"auto_form_{step+1}",
                            description=form_action,
                            require_target=True,
                        )
                        if screenshot:
                            screenshots.append(screenshot)
                        self._record_action({
                            "phase": "autonomous",
                            "step": step + 1,
                            "operation": "FormInteraction",
                            "description": form_action,
                            "params": {},
                        })
                        continue

                # Cap taps per page-state to avoid dead loops on a single screen.
                if self.screen_action_counts[screen_key] >= self.policy.max_clicks_per_screen:
                    recovery_action = self.recovery_manager.next_action(
                        stagnation_count=stagnant_steps + 1,
                        error_count=consecutive_errors,
                    )
                    self._execute_recovery_action(host, port, recovery_action.kind)
                    recovery_count += 1
                    self._record_action({
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
                operation = self._decide_operation_with_timeout(
                    screenshot_data=screenshot_data,
                    goal="深度探索应用功能，触发更多网络请求",
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
                    self._record_action({
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
                self._record_action({
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
                before_count = len(self.activities_visited)
                self._record_current_activity(host, port)
                if len(self.activities_visited) > before_count:
                    logger.info("Discovered new activity: %s", self.activities_visited[-1])

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

        if self._is_special_permission_package(current_pkg):
            logger.info(
                "Foreground drift entered special-permission page: %s (target=%s)",
                current_pkg,
                self.target_package,
            )
            if self._recover_from_special_permission_page(host, port, current_pkg):
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

    def _is_special_permission_package(self, package_name: str) -> bool:
        """Return whether current foreground belongs to system settings/permission UI."""
        normalized = (package_name or "").strip()
        if not normalized:
            return False
        return normalized in SPECIAL_PERMISSION_PACKAGES or "permissioncontroller" in normalized

    def _recover_from_special_permission_page(self, host: str, port: int, package_name: str) -> bool:
        """Best-effort recovery from system settings/special permission screens."""
        action = self._tap_priority_dialog_action(host, port)
        if action:
            logger.info(
                "Tapped action on special-permission page package=%s action=%s",
                package_name,
                action,
            )
            time.sleep(1.5)
            if self._is_target_app_foreground(host, port):
                return True

        self.android_runner.press_back(host, port)
        time.sleep(1)
        current_pkg = self._get_foreground_package(host, port)
        if current_pkg == self.target_package:
            logger.info(
                "Recovered target app from special-permission page via back package=%s target=%s",
                package_name,
                self.target_package,
            )
            return True

        logger.info(
            "Special-permission page back recovery incomplete package=%s current=%s target=%s",
            package_name,
            current_pkg or "unknown",
            self.target_package,
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

    def _decide_operation_with_timeout(
        self,
        screenshot_data: bytes,
        goal: str,
    ) -> Operation:
        """Run AI decision with a hard timeout to avoid per-step hangs."""
        timeout_seconds = max(1, int(self.policy.ai_step_timeout_seconds))
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            self.ai_driver.analyze_and_decide,
            screenshot_data,
            self.exploration_history,
            goal,
        )
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            logger.warning("AI decision timeout after %ss, fallback to Wait", timeout_seconds)
            return Operation(
                type=OperationType.WAIT,
                params={"duration": 1},
                description=f"AI timeout({timeout_seconds}s), fallback wait",
            )
        except Exception as exc:
            logger.warning("AI decision error: %s", exc)
            return Operation(
                type=OperationType.WAIT,
                params={"duration": 1},
                description="AI error fallback wait",
            )
        finally:
            if not future.done():
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)

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

            self._record_action({
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
                    grant_summary = self.android_runner.grant_all_permissions(host, port, self.target_package)
                    self._merge_permission_summary(grant_summary)
                    self.android_runner.launch_app(host, port, self.target_package)
            return

    def _merge_permission_summary(self, summary: Optional[Dict[str, Any]]) -> None:
        if not isinstance(summary, dict):
            return
        for key in ("requested_permissions", "granted_permissions", "failed_permissions"):
            bucket = self._permission_summary.setdefault(key, [])
            for item in summary.get(key, []) or []:
                if item not in bucket:
                    bucket.append(item)

    def phase4_scenario_test(
        self,
        host: str,
        port: int,
        deadline_ts: Optional[float] = None,
    ) -> List[Screenshot]:
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
            ("refresh", self._test_refresh_scenario),
            ("detail_entry", self._test_detail_entry_scenario),
            ("return_and_retry", self._test_return_and_retry_scenario),
            ("relaunch_burst", self._test_relaunch_burst_scenario),
        ]

        action_budget = max(4, int(self.policy.scenario_action_budget))
        used_actions = 0

        for scenario_name, scenario_func in scenarios:
            if not self._within_deadline(deadline_ts):
                logger.info("Phase 4 stopped due to time budget")
                break
            if not self._action_budget_remaining():
                logger.info("Phase 4 stopped due to total action budget")
                break
            if used_actions >= action_budget:
                logger.info("Phase 4 stopped due to action budget: %s", action_budget)
                break
            try:
                logger.info(f"Testing scenario: {scenario_name}")
                scenario_screenshots = scenario_func(host, port, deadline_ts=deadline_ts)
                screenshots.extend(scenario_screenshots)
                used_actions += max(1, len(scenario_screenshots))
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
            # Prefer explicit coordinates from Open-AutoGLM action conversion.
            if all(k in params for k in ("start_x", "start_y", "end_x", "end_y")):
                self.android_runner.execute_swipe(
                    host,
                    port,
                    int(params.get("start_x")),
                    int(params.get("start_y")),
                    int(params.get("end_x")),
                    int(params.get("end_y")),
                )
            else:
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
            if "x" in params and "y" in params:
                try:
                    self.android_runner.execute_tap(host, port, int(params["x"]), int(params["y"]))
                    time.sleep(0.2)
                except Exception:
                    pass
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

        # When form interaction is enabled, don't skip login/register pages preemptively.
        if self.policy.enable_form_interaction and self._find_input_candidates(ui_xml):
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

    def _find_input_candidates(self, ui_xml: str) -> List[Dict[str, Any]]:
        """Find input widgets (EditText-like) from UI XML."""
        if not isinstance(ui_xml, str) or "<hierarchy" not in ui_xml:
            return []
        try:
            root = ET.fromstring(ui_xml)
        except ET.ParseError:
            return []

        candidates: List[Dict[str, Any]] = []
        for node in root.iter("node"):
            class_name = (node.attrib.get("class") or "").strip()
            clickable = node.attrib.get("clickable", "false").lower() == "true"
            focusable = node.attrib.get("focusable", "false").lower() == "true"
            editable = (
                "EditText" in class_name
                or node.attrib.get("password", "false").lower() == "true"
                or node.attrib.get("inputType")
            )
            if not editable and not (clickable and focusable):
                continue

            text = (node.attrib.get("text") or "").strip()
            hint = (node.attrib.get("hint") or "").strip()
            desc = (node.attrib.get("content-desc") or "").strip()
            rid = (node.attrib.get("resource-id") or "").strip()
            input_type = (node.attrib.get("inputType") or "").strip()
            max_length_raw = (
                node.attrib.get("maxTextLength")
                or node.attrib.get("maxLength")
                or node.attrib.get("maxlength")
                or ""
            )
            try:
                max_length = int(str(max_length_raw).strip())
            except Exception:
                max_length = 0
            if max_length <= 0:
                max_length = None
            label = " ".join(part for part in [text, hint, desc, rid] if part).strip()

            bounds = node.attrib.get("bounds", "")
            center = self._parse_bounds_center(bounds)
            if not center:
                continue

            signature = f"{rid}|{bounds}|{class_name}"
            candidates.append(
                {
                    "x": center[0],
                    "y": center[1],
                    "label": label,
                    "signature": signature,
                    "password": node.attrib.get("password", "false").lower() == "true",
                    "resource_id": rid,
                    "hint": hint,
                    "input_type": input_type,
                    "max_length": max_length,
                }
            )
        return candidates

    @staticmethod
    def _build_form_input_text(
        label: str,
        is_password: bool = False,
        field: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build deterministic synthetic input text guided by widget constraints."""
        field = field or {}
        lower = (label or "").lower()
        rid = str(field.get("resource_id") or "").lower()
        hint = str(field.get("hint") or "").lower()
        input_type = str(field.get("input_type") or "").lower()
        max_length = field.get("max_length")

        merged = f"{lower} {rid} {hint} {input_type}"

        def _clip(value: str) -> str:
            if isinstance(max_length, int) and max_length > 0:
                if len(value) > max_length:
                    return value[:max_length]
            return value

        def _numeric(value: str) -> str:
            digits = "".join(ch for ch in value if ch.isdigit())
            if isinstance(max_length, int) and max_length > 0:
                digits = digits[:max_length]
            if not digits:
                fallback_len = max(4, min(int(max_length or 6), 18))
                digits = "1" * fallback_len
            return digits

        if is_password or "密码" in merged or "pass" in merged:
            value = "Aa123456"
            return _clip(value)

        if any(token in merged for token in ("验证码", "otp", "sms", "code")):
            return _numeric("123456")

        if any(token in merged for token in ("邮箱", "email")):
            value = "autotest@example.com"
            if isinstance(max_length, int) and max_length > 0 and len(value) > max_length:
                short_email = "a@b.cn"
                return short_email if len(short_email) <= max_length else "ab.cn"[:max_length]
            return value

        if any(token in merged for token in ("身份证", "idcard", "certno")):
            return _clip("110101199001011239")

        if any(token in merged for token in ("银行卡", "cardno", "bankcard")):
            return _numeric("6222021200000007")

        if any(token in merged for token in ("金额", "amount", "money")):
            value = "100.00"
            if isinstance(max_length, int) and max_length > 0 and len(value) > max_length:
                return _numeric("10000")
            return _clip(value)

        if any(token in merged for token in ("姓名", "name", "realname", "username", "账户", "账号")):
            value = "testuser"
            return _clip(value)

        numeric_hint = any(
            token in merged for token in ("手机", "电话", "phone", "mobile", "tel", "number")
        )
        if numeric_hint or input_type.isdigit():
            return _numeric("13800138000")

        return _clip("test123")

    def _find_form_submit_action(self, ui_xml: str) -> Optional[Tuple[int, int, str]]:
        """Find submit-like button for login/register forms."""
        if not isinstance(ui_xml, str) or "<hierarchy" not in ui_xml:
            return None
        try:
            root = ET.fromstring(ui_xml)
        except ET.ParseError:
            return None

        best: Optional[Tuple[int, int, str, int]] = None
        for node in root.iter("node"):
            text = (node.attrib.get("text") or "").strip()
            desc = (node.attrib.get("content-desc") or "").strip()
            rid = (node.attrib.get("resource-id") or "").strip()
            label = f"{text} {desc} {rid}".strip()
            if not label:
                continue
            if not any(token in label for token in self.policy.form_submit_keywords):
                continue
            center = self._parse_bounds_center(node.attrib.get("bounds", ""))
            if not center:
                continue
            score = 100
            if node.attrib.get("clickable", "false").lower() == "true":
                score += 20
            if "Button" in (node.attrib.get("class") or ""):
                score += 10
            if not best or score > best[3]:
                best = (center[0], center[1], label, score)
        if not best:
            return None
        return best[0], best[1], best[2]

    def _perform_form_interaction(
        self,
        host: str,
        port: int,
        ui_xml: str,
        candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[str]:
        """Fill one input field and optionally tap submit action."""
        candidates = candidates if candidates is not None else self._find_input_candidates(ui_xml)
        if not candidates:
            return None

        for item in candidates:
            signature = item["signature"]
            if signature in self.filled_input_signatures:
                continue

            self.android_runner.execute_tap(host, port, item["x"], item["y"])
            time.sleep(0.25)
            text = self._build_form_input_text(
                item["label"],
                is_password=item["password"],
                field=item,
            )
            self.android_runner.execute_input_text(host, port, text)
            self.filled_input_signatures.add(signature)

            submit = self._find_form_submit_action(ui_xml)
            if submit:
                sx, sy, submit_label = submit
                self.android_runner.execute_tap(host, port, sx, sy)
                return f"表单输入并提交: {item['label'] or '输入框'} -> {submit_label}"
            return f"表单输入: {item['label'] or '输入框'}"
        return None

    def _test_search_scenario(
        self,
        host: str,
        port: int,
        deadline_ts: Optional[float] = None,
    ) -> List[Screenshot]:
        """Test search functionality."""
        screenshots = []

        # Try to find and click search button (usually top right or in menu)
        # Common search icon positions
        search_positions = [
            (1000, 150),  # Top right
            (540, 150),   # Top center
        ]

        for x, y in search_positions:
            if not self._within_deadline(deadline_ts):
                break
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

    def _test_scroll_scenario(
        self,
        host: str,
        port: int,
        deadline_ts: Optional[float] = None,
    ) -> List[Screenshot]:
        """Test scrolling."""
        screenshots = []

        # Scroll down multiple times
        for i in range(4):
            if not self._within_deadline(deadline_ts):
                break
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

    def _test_refresh_scenario(
        self,
        host: str,
        port: int,
        deadline_ts: Optional[float] = None,
    ) -> List[Screenshot]:
        """Trigger pull-to-refresh and wait to stimulate network calls."""
        screenshots: List[Screenshot] = []
        if not self._within_deadline(deadline_ts):
            return screenshots
        if not self._ensure_target_app_foreground(host, port):
            return screenshots

        screen_w, screen_h = self._get_display_size(host, port)
        self.android_runner.execute_swipe(
            host,
            port,
            int(screen_w * 0.5),
            int(screen_h * 0.28),
            int(screen_w * 0.5),
            int(screen_h * 0.78),
            duration=450,
        )
        time.sleep(1.8)
        shot = self._capture_app_screenshot(
            host=host,
            port=port,
            stage="scenario_refresh",
            description="下拉刷新触发网络请求",
            require_target=True,
        )
        if shot:
            screenshots.append(shot)
        return screenshots

    def _test_detail_entry_scenario(
        self,
        host: str,
        port: int,
        deadline_ts: Optional[float] = None,
    ) -> List[Screenshot]:
        """Try entering list/detail pages from multiple hotspots then backtrack."""
        screenshots: List[Screenshot] = []
        if not self._ensure_target_app_foreground(host, port):
            return screenshots
        screen_w, screen_h = self._get_display_size(host, port)
        entry_points = [
            (int(screen_w * 0.5), int(screen_h * 0.36)),
            (int(screen_w * 0.5), int(screen_h * 0.50)),
            (int(screen_w * 0.5), int(screen_h * 0.64)),
        ]
        for idx, (x, y) in enumerate(entry_points, start=1):
            if not self._within_deadline(deadline_ts):
                break
            if not self._ensure_target_app_foreground(host, port):
                break
            self.android_runner.execute_tap(host, port, x, y)
            time.sleep(1.3)
            shot = self._capture_app_screenshot(
                host=host,
                port=port,
                stage=f"scenario_detail_{idx}",
                description=f"尝试进入详情页 {idx}",
                require_target=True,
            )
            if shot:
                screenshots.append(shot)
            self.android_runner.press_back(host, port)
            time.sleep(0.9)
        return screenshots

    def _test_return_and_retry_scenario(
        self,
        host: str,
        port: int,
        deadline_ts: Optional[float] = None,
    ) -> List[Screenshot]:
        """Back-navigation and reopen flow to emulate user retry behavior."""
        screenshots: List[Screenshot] = []
        if not self._within_deadline(deadline_ts):
            return screenshots
        if not self._ensure_target_app_foreground(host, port):
            return screenshots

        self.android_runner.press_back(host, port)
        time.sleep(0.9)
        shot = self._capture_app_screenshot(
            host=host,
            port=port,
            stage="scenario_back_once",
            description="返回上级页面后重试",
            require_target=True,
        )
        if shot:
            screenshots.append(shot)

        ui_xml = self._get_ui_dump_xml(host, port)
        op = self._pick_ui_candidate_operation(host, port, ui_xml=ui_xml)
        if op and self._within_deadline(deadline_ts):
            self._execute_operation(host, port, op)
            time.sleep(1.2)
            shot = self._capture_app_screenshot(
                host=host,
                port=port,
                stage="scenario_retry_entry",
                description=f"返回后重试入口: {op.description}",
                require_target=True,
            )
            if shot:
                screenshots.append(shot)
        return screenshots

    def _test_relaunch_burst_scenario(
        self,
        host: str,
        port: int,
        deadline_ts: Optional[float] = None,
    ) -> List[Screenshot]:
        """
        Relaunch app repeatedly to force page bootstrap requests.

        This is intentionally aggressive to increase dynamic traffic evidence
        within a limited time window.
        """
        screenshots: List[Screenshot] = []
        if not self.target_package:
            return screenshots

        cycles = max(1, int(self.policy.relaunch_cycles))
        for idx in range(1, cycles + 1):
            if not self._within_deadline(deadline_ts):
                break
            self.android_runner.execute_adb_remote(
                host,
                port,
                f"shell am force-stop {self.target_package}",
            )
            time.sleep(0.6)
            self.android_runner.launch_app(host, port, self.target_package)
            time.sleep(2.2)
            self._tap_priority_dialog_action(host, port)
            shot = self._capture_app_screenshot(
                host=host,
                port=port,
                stage=f"scenario_relaunch_{idx}",
                description=f"冷启动重放第{idx}次，触发启动链路请求",
                require_target=True,
            )
            if shot:
                screenshots.append(shot)
        return screenshots

    def run_full_exploration(
        self,
        emulator_config: Dict,
        apk_info: Dict,
        persist_screenshots: str = "minio",
        local_screenshot_dir: Optional[str] = None,
    ) -> ExplorationResult:
        """
        Run complete exploration with all phases.

        Args:
            emulator_config: {"host": "10.16.148.66", "port": 5555}
            apk_info: {"apk_path": "/path/to/file.apk", "package_name": "com.example"}
            persist_screenshots: one of "minio", "local", "none"
            local_screenshot_dir: local path when persist_screenshots="local"

        Returns:
            ExplorationResult with all data
        """
        host = emulator_config["host"]
        port = emulator_config["port"]
        apk_path = apk_info["apk_path"]
        package_name = apk_info.get("package_name")  # 使用get方法,允许为None
        activity_name = apk_info.get("activity_name")
        try:
            max_steps = int(os.getenv("APP_EXPLORATION_MAX_STEPS", str(self.policy.max_steps)))
        except ValueError:
            max_steps = self.policy.max_steps
        max_steps = max(5, min(max_steps, 500))
        try:
            time_budget = int(
                os.getenv(
                    "APP_EXPLORATION_TIME_BUDGET_SECONDS",
                    str(self.policy.time_budget_seconds),
                )
            )
        except ValueError:
            time_budget = self.policy.time_budget_seconds
        time_budget = max(60, min(time_budget, 3600))
        deadline_ts = time.time() + time_budget

        self._apk_path = apk_path
        self.target_package = package_name
        self.exploration_history.clear()
        self.activities_visited.clear()
        self.screen_action_counts.clear()
        self.screen_form_action_counts.clear()
        self.clicked_ui_signatures.clear()
        self.filled_input_signatures.clear()
        self._captured_screenshot_count = 0

        all_screenshots = []
        phases_completed = []
        error_message = None

        try:
            # Phase 1: Setup
            screenshots = self.phase1_basic_setup(host, port, apk_path, package_name, activity_name=activity_name)
            all_screenshots.extend(screenshots)
            phases_completed.append("setup")

            # Phase 2: Navigation
            if self._within_deadline(deadline_ts):
                screenshots = self.phase2_navigation_explore(host, port, deadline_ts=deadline_ts)
                all_screenshots.extend(screenshots)
                phases_completed.append("navigation")

            # Phase 3: Autonomous
            if self._within_deadline(deadline_ts):
                screenshots = self.phase3_autonomous_explore(
                    host,
                    port,
                    max_steps=max_steps,
                    deadline_ts=deadline_ts,
                )
                all_screenshots.extend(screenshots)
                phases_completed.append("autonomous")

            # Phase 4: Scenarios
            if self._within_deadline(deadline_ts):
                screenshots = self.phase4_scenario_test(host, port, deadline_ts=deadline_ts)
                all_screenshots.extend(screenshots)
                phases_completed.append("scenarios")

            success = True

        except Exception as e:
            logger.error(f"Exploration failed: {e}")
            success = False
            error_message = str(e)

        if persist_screenshots == "minio":
            for screenshot in all_screenshots:
                self.screenshot_manager.save_to_minio(screenshot)
        elif persist_screenshots == "local" and local_screenshot_dir:
            for idx, screenshot in enumerate(all_screenshots, start=1):
                self.screenshot_manager.save_to_local(
                    screenshot=screenshot,
                    base_dir=local_screenshot_dir,
                    step=idx,
                )

        # Cleanup: Uninstall the app after analysis
        cleanup_package = self.target_package or package_name
        if cleanup_package:
            try:
                logger.info(f"Uninstalling app {cleanup_package}...")
                output = self.android_runner.execute_adb_remote(host, port, f"uninstall {cleanup_package}")
                if "Success" in output:
                    logger.info(f"Successfully uninstalled {cleanup_package}")
                else:
                    logger.warning(f"Failed to uninstall {cleanup_package}: {output}")
            except BaseException as e:
                if isinstance(e, (KeyboardInterrupt, SystemExit)):
                    raise
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
            phases_completed=phases_completed,
            history=self.exploration_history[-1000:],
            permission_summary=dict(self._permission_summary),
        )
