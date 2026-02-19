"""App exploration strategy with mixed approach."""
import logging
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from modules.ai_driver import AIDriver, Operation
from modules.android_runner import AndroidRunner
from modules.screenshot_manager import ScreenshotManager, Screenshot

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

    def __init__(self, ai_driver: AIDriver, android_runner: AndroidRunner,
                 screenshot_manager: ScreenshotManager):
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
        self.exploration_history: List[Dict] = []
        self.activities_visited: List[str] = []

    def phase1_basic_setup(self, host: str, port: int,
                          apk_path: str, package_name: str) -> List[Screenshot]:
        """
        Phase 1: Basic setup - install, grant permissions, launch.

        Args:
            host: Emulator host
            port: Emulator port
            apk_path: Path to APK file
            package_name: Package name

        Returns:
            List of screenshots from this phase
        """
        logger.info(f"Phase 1: Basic setup for {package_name}")
        screenshots = []

        # Connect to emulator
        if not self.android_runner.connect_remote_emulator(host, port):
            raise RuntimeError(f"Failed to connect to emulator {host}:{port}")

        time.sleep(2)  # Wait for connection

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

        # Grant all permissions
        logger.info("Granting permissions...")
        self.android_runner.grant_all_permissions(host, port, package_name)

        # Launch app
        logger.info("Launching app...")
        self.android_runner.launch_app(host, port, package_name)
        time.sleep(3)  # Wait for app to start

        # Screenshot: App launched
        screenshot = self.screenshot_manager.capture(
            stage="launch",
            description="应用启动界面",
            emulator_host=host,
            emulator_port=port
        )
        if screenshot:
            screenshots.append(screenshot)

        # Record activity
        activity = self.android_runner.get_current_activity(host, port)
        if activity:
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
        screenshot = self.screenshot_manager.capture(
            stage="explore_start",
            description="开始探索首页",
            emulator_host=host,
            emulator_port=port
        )
        if screenshot:
            screenshots.append(screenshot)

        # Common navigation positions to try (bottom nav bar typical positions)
        # For 1080x1920 screen, bottom nav is usually around y=1800
        nav_y = 1800
        nav_positions = [270, 540, 810, 1080]  # 4 tabs

        for i, x in enumerate(nav_positions):
            logger.info(f"Tapping navigation position {i+1}")

            # Tap
            self.android_runner.execute_tap(host, port, x, nav_y)
            time.sleep(2)  # Wait for transition

            # Screenshot
            screenshot = self.screenshot_manager.capture(
                stage=f"nav_tab_{i+1}",
                description=f"点击导航栏第{i+1}个Tab",
                emulator_host=host,
                emulator_port=port
            )
            if screenshot:
                screenshots.append(screenshot)

            # Record activity
            activity = self.android_runner.get_current_activity(host, port)
            if activity and activity not in self.activities_visited:
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

        for step in range(max_steps):
            logger.info(f"Exploration step {step + 1}/{max_steps}")

            try:
                # Take screenshot
                screenshot_data = self.android_runner.take_screenshot_remote(host, port)

                if not screenshot_data:
                    logger.warning("Failed to capture screenshot")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        logger.error("Too many consecutive errors, stopping")
                        break
                    continue

                # AI analyzes and decides next action
                operation = self.ai_driver.analyze_and_decide(
                    screenshot_data,
                    self.exploration_history,
                    goal="深度探索应用功能，触发更多网络请求"
                )

                # Check if should skip (login, payment screens)
                if self._should_skip_screen(screenshot_data):
                    logger.info("Skipping screen (login/payment detected)")
                    self.android_runner.press_back(host, port)
                    time.sleep(1)
                    continue

                # Execute operation
                self._execute_operation(host, port, operation)

                # Reset error counter on success
                consecutive_errors = 0

                # Wait for UI to settle
                time.sleep(2)

                # Capture result screenshot
                screenshot = self.screenshot_manager.capture(
                    stage=f"auto_step_{step+1}",
                    description=f"{operation.type.value}: {operation.description}",
                    emulator_host=host,
                    emulator_port=port
                )
                if screenshot:
                    screenshots.append(screenshot)

                # Record in history
                self.exploration_history.append({
                    "phase": "autonomous",
                    "step": step + 1,
                    "operation": operation.type.value,
                    "description": operation.description,
                    "params": operation.params
                })

                # Record activity
                activity = self.android_runner.get_current_activity(host, port)
                if activity and activity not in self.activities_visited:
                    self.activities_visited.append(activity)
                    logger.info(f"Discovered new activity: {activity}")

            except Exception as e:
                logger.error(f"Error in exploration step {step + 1}: {e}")
                consecutive_errors += 1
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many errors, stopping autonomous exploration")
                    break

        return screenshots

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
        params = operation.params

        if op_type == "Tap":
            x = params.get("x", 540)
            y = params.get("y", 960)
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
            time.sleep(duration)

    def _should_skip_screen(self, screenshot_data: bytes) -> bool:
        """Check if current screen should be skipped."""
        # Use AI to detect login/payment screens
        description = self.ai_driver.analyze_screenshot(
            screenshot_data,
            "Is this a login, payment, or authentication screen? Answer yes or no."
        )
        return "yes" in description.lower()

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
            self.android_runner.execute_tap(host, port, x, y)
            time.sleep(1)

            screenshot = self.screenshot_manager.capture(
                stage="search_attempt",
                description="尝试打开搜索",
                emulator_host=host,
                emulator_port=port
            )
            if screenshot:
                screenshots.append(screenshot)

        return screenshots

    def _test_scroll_scenario(self, host: str, port: int) -> List[Screenshot]:
        """Test scrolling."""
        screenshots = []

        # Scroll down multiple times
        for i in range(3):
            self.android_runner.execute_swipe(host, port, 540, 1500, 540, 500)
            time.sleep(1)

            screenshot = self.screenshot_manager.capture(
                stage=f"scroll_{i+1}",
                description=f"向下滚动第{i+1}次",
                emulator_host=host,
                emulator_port=port
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
        package_name = apk_info["package_name"]

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
            screenshots = self.phase3_autonomous_explore(host, port, max_steps=50)
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

        return ExplorationResult(
            total_steps=len(self.exploration_history),
            screenshots=self.screenshot_manager.get_all_for_report(),
            network_requests=[],  # Will be filled by traffic monitor
            activities_visited=self.activities_visited,
            success=success,
            error_message=error_message,
            phases_completed=phases_completed
        )
