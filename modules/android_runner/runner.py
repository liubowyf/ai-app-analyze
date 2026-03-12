"""Android Runner module for remote Android emulator control."""
import logging
import os
import re
import shlex
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class AndroidRunner:
    """Remote Android device controller via ADB."""

    def __init__(self):
        """Initialize runner for remote ADB operations."""
        pass

    def list_installed_packages(self, container_id: str) -> List[str]:
        """
        List installed packages.

        Args:
            container_id: Container ID

        Returns:
            List of package names
        """
        result = self.execute_adb_command(
            container_id,
            "shell pm list packages"
        )
        packages = []
        for line in result.strip().split("\n"):
            if "package:" in line:
                packages.append(line.replace("package:", "").strip())
        return packages

    def connect_remote_emulator(self, host: str, port: int) -> bool:
        """
        Connect to remote Android emulator via ADB.

        Args:
            host: Emulator host IP
            port: ADB port

        Returns:
            True if connected successfully
        """
        try:
            import subprocess
            result = subprocess.run(
                ["adb", "connect", f"{host}:{port}"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if "connected" in result.stdout.lower() or "already connected" in result.stdout.lower():
                logger.info(f"Connected to emulator {host}:{port}")
                return True
            else:
                logger.error(f"Failed to connect: {result.stdout}")
                return False
        except Exception as e:
            logger.error(f"Failed to connect to emulator: {e}")
            return False

    def execute_adb_remote(
        self,
        host: str,
        port: int,
        command: str,
        timeout_seconds: Optional[float] = None,
    ) -> str:
        """
        Execute ADB command on remote emulator.

        Args:
            host: Emulator host IP
            port: ADB port
            command: ADB command (without 'adb' prefix)

        Returns:
            Command output
        """
        try:
            device = f"{host}:{port}"
            if timeout_seconds is None:
                timeout_raw = os.getenv("ADB_COMMAND_TIMEOUT_SECONDS", "12")
                try:
                    timeout = float(timeout_raw)
                except ValueError:
                    timeout = 12.0
                timeout = max(2.0, min(timeout, 60.0))
            else:
                timeout = float(timeout_seconds)
                timeout = max(2.0, min(timeout, 600.0))

            adb_cmd = ["adb", "-s", device]
            if command.startswith("shell "):
                # Use sh -c to preserve shell operators like pipes/redirects.
                shell_cmd = command[len("shell "):].strip()
                adb_cmd.extend(["shell", "sh", "-c", shlex.quote(shell_cmd)])
            else:
                adb_cmd.extend(shlex.split(command))

            result = subprocess.run(
                adb_cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.stdout:
                return result.stdout
            if result.stderr:
                return result.stderr
            return ""
        except Exception as e:
            logger.error(f"Failed to execute ADB command: {e}")
            return ""

    def install_apk_remote(self, host: str, port: int, apk_path: str) -> bool:
        """
        Install APK on remote emulator.

        Args:
            host: Emulator host IP
            port: ADB port
            apk_path: Local path to APK file

        Returns:
            True if successful
        """
        install_timeout_raw = os.getenv("ADB_INSTALL_TIMEOUT_SECONDS", "600")
        retry_raw = os.getenv("ADB_INSTALL_RETRIES", "2")
        try:
            install_timeout = float(install_timeout_raw)
        except ValueError:
            install_timeout = 600.0
        install_timeout = max(15.0, min(install_timeout, 600.0))

        try:
            retries = int(retry_raw)
        except ValueError:
            retries = 2
        retries = max(1, min(retries, 5))

        apk_arg = shlex.quote(apk_path)
        last_output = ""
        for attempt in range(1, retries + 1):
            output = self.execute_adb_remote(
                host,
                port,
                f"install -r -g {apk_arg}",
                timeout_seconds=install_timeout,
            )
            last_output = output or ""
            if "Success" in last_output:
                logger.info(
                    "APK installed successfully on %s:%s (attempt=%s)",
                    host,
                    port,
                    attempt,
                )
                return True

            logger.warning(
                "APK install attempt %s/%s failed on %s:%s: %s",
                attempt,
                retries,
                host,
                port,
                (last_output or "").strip()[:400],
            )
            # Reconnect between retries to recover from transient ADB transport issues.
            self.connect_remote_emulator(host, port)

        logger.error("APK installation failed after %s attempts: %s", retries, last_output)
        return False

    def take_screenshot_remote(self, host: str, port: int) -> bytes:
        """
        Take screenshot from remote emulator.

        Args:
            host: Emulator host IP
            port: ADB port

        Returns:
            Screenshot as PNG bytes
        """
        try:
            import subprocess
            import tempfile
            import os
            import math

            device = f"{host}:{port}"
            timeout_raw = os.getenv("ADB_SCREENSHOT_TIMEOUT_SECONDS", "8")
            try:
                timeout = float(timeout_raw)
            except ValueError:
                timeout = 8.0
            timeout = max(2.0, min(timeout, 30.0))

            # Prefer exec-out to avoid slow temporary-file pull path.
            result = subprocess.run(
                ["adb", "-s", device, "exec-out", "screencap", "-p"],
                capture_output=True,
                timeout=timeout,
            )
            image_data = result.stdout or b""
            if image_data.startswith(b"\x89PNG"):
                # exec-out already returns raw PNG bytes; do not normalize CRLF, which can corrupt payload.
                return image_data

            # Take screenshot on device
            subprocess.run(
                ["adb", "-s", device, "shell", "screencap", "-p", "/sdcard/screen.png"],
                check=True,
                capture_output=True,
                timeout=math.ceil(timeout)
            )

            # Pull to temp file
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name

            subprocess.run(
                ["adb", "-s", device, "pull", "/sdcard/screen.png", tmp_path],
                check=True,
                capture_output=True,
                timeout=math.ceil(timeout)
            )

            # Read and return
            with open(tmp_path, "rb") as f:
                data = f.read()

            os.unlink(tmp_path)
            return data

        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return b""

    def grant_all_permissions(self, host: str, port: int, package: str) -> None:
        """
        Grant all runtime permissions to an app.

        Args:
            host: Emulator host IP
            port: ADB port
            package: Package name
        """
        try:
            # Get all permissions
            output = self.execute_adb_remote(
                host, port,
                f"shell pm dump {package} | grep 'requested permissions:' -A 100"
            )

            # Grant each permission
            for line in output.split('\n'):
                if 'android.permission' in line:
                    perm = line.strip().split(':')[-1].strip()
                    self.execute_adb_remote(
                        host, port,
                        f"shell pm grant {package} {perm}"
                    )

            logger.info(f"Granted all permissions to {package}")
        except Exception as e:
            logger.warning(f"Failed to grant permissions: {e}")

    def launch_app(
        self,
        host: str,
        port: int,
        package: str,
        activity_name: str | None = None,
    ) -> None:
        """
        Launch an app by package name.

        Args:
            host: Emulator host IP
            port: ADB port
            package: Package name
        """
        try:
            launch_timeout_raw = os.getenv("ADB_LAUNCH_TIMEOUT_SECONDS", "15")
            try:
                launch_timeout = float(launch_timeout_raw)
            except ValueError:
                launch_timeout = 15.0
            launch_timeout = max(3.0, min(launch_timeout, 120.0))

            if activity_name:
                component = f"{package}/{activity_name}"
                self.execute_adb_remote(
                    host,
                    port,
                    f"shell am start -W -n {component}",
                    timeout_seconds=launch_timeout,
                )
            else:
                self.execute_adb_remote(
                    host, port,
                    f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1",
                    timeout_seconds=launch_timeout,
                )
            logger.info(f"Launched app {package}")
        except Exception as e:
            logger.error(f"Failed to launch app: {e}")

    def execute_tap(self, host: str, port: int, x: int, y: int) -> None:
        """
        Execute tap on screen.

        Args:
            host: Emulator host IP
            port: ADB port
            x: X coordinate
            y: Y coordinate
        """
        try:
            self.execute_adb_remote(host, port, f"shell input tap {x} {y}")
            logger.debug(f"Tapped at ({x}, {y})")
        except Exception as e:
            logger.error(f"Failed to tap: {e}")

    def execute_swipe(self, host: str, port: int,
                     start_x: int, start_y: int,
                     end_x: int, end_y: int, duration: int = 300) -> None:
        """
        Execute swipe on screen.

        Args:
            host: Emulator host IP
            port: ADB port
            start_x: Start X coordinate
            start_y: Start Y coordinate
            end_x: End X coordinate
            end_y: End Y coordinate
            duration: Swipe duration in ms
        """
        try:
            self.execute_adb_remote(
                host, port,
                f"shell input swipe {start_x} {start_y} {end_x} {end_y} {duration}"
            )
            logger.debug(f"Swiped from ({start_x}, {start_y}) to ({end_x}, {end_y})")
        except Exception as e:
            logger.error(f"Failed to swipe: {e}")

    def execute_input_text(self, host: str, port: int, text: str) -> None:
        """
        Input text on device.

        Args:
            host: Emulator host IP
            port: ADB port
            text: Text to input
        """
        try:
            # Escape special characters for shell
            escaped_text = text.replace(' ', '%s').replace('&', '\\&')
            self.execute_adb_remote(host, port, f"shell input text {escaped_text}")
            logger.debug(f"Input text: {text}")
        except Exception as e:
            logger.error(f"Failed to input text: {e}")

    def get_current_activity(self, host: str, port: int) -> str:
        """
        Get current foreground activity.

        Args:
            host: Emulator host IP
            port: ADB port

        Returns:
            Activity name
        """
        try:
            commands = [
                "shell dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'",
                "shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'",
                "shell dumpsys activity top",
            ]
            for cmd in commands:
                output = self.execute_adb_remote(host, port, cmd)
                activity = self._extract_activity_token(output)
                if activity:
                    return activity
            return ""
        except Exception as e:
            logger.error(f"Failed to get current activity: {e}")
            return ""

    @staticmethod
    def _extract_activity_token(output: str) -> str:
        """Extract package/activity token from dumpsys output."""
        if not output:
            return ""

        prioritized_patterns = [
            r"mResumedActivity:\s+.*?([A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+)",
            r"topResumedActivity(?:=|:\s+).*?([A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+)",
            r"mCurrentFocus(?:=|:\s+).*?([A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+)",
            r"mFocusedApp(?:=|:\s+).*?([A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+)",
        ]
        for pattern in prioritized_patterns:
            match = re.search(pattern, output, re.MULTILINE)
            if match:
                return match.group(1)

        # Fallback for compact outputs that only contain activity tokens.
        match = re.search(r"([A-Za-z0-9_.$]+/[A-Za-z0-9_.$]+)", output)
        return match.group(1) if match else ""

    def get_current_package(self, host: str, port: int) -> str:
        """
        Get current foreground package name.

        Args:
            host: Emulator host IP
            port: ADB port

        Returns:
            Package name or empty string when unavailable
        """
        activity = self.get_current_activity(host, port)
        if not activity or "/" not in activity:
            return ""
        return activity.split("/", 1)[0].strip()

    def get_current_window(self, host: str, port: int) -> str:
        """
        Get current foreground window token.

        Args:
            host: Emulator host IP
            port: ADB port

        Returns:
            Window token string
        """
        try:
            output = self.execute_adb_remote(
                host,
                port,
                "shell dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'",
            )
            activity = self._extract_activity_token(output)
            if activity:
                return activity
            return (output or "").strip()
        except Exception as e:
            logger.error(f"Failed to get current window: {e}")
            return ""

    def dump_ui_hierarchy(self, host: str, port: int) -> str:
        """
        Dump current UI hierarchy xml.

        Args:
            host: Emulator host IP
            port: ADB port

        Returns:
            XML text
        """
        self.execute_adb_remote(host, port, "shell uiautomator dump /sdcard/window_dump.xml")
        return self.execute_adb_remote(host, port, "shell cat /sdcard/window_dump.xml")

    def force_stop_app(self, host: str, port: int, package: str) -> None:
        """
        Force stop an app process.

        Args:
            host: Emulator host IP
            port: ADB port
            package: Package name
        """
        try:
            self.execute_adb_remote(host, port, f"shell am force-stop {package}")
            logger.info("Force-stopped app %s", package)
        except Exception as e:
            logger.error(f"Failed to force stop app: {e}")

    def clear_app_data(self, host: str, port: int, package: str) -> bool:
        """
        Clear app data.

        Args:
            host: Emulator host IP
            port: ADB port
            package: Package name

        Returns:
            True if successful
        """
        try:
            output = self.execute_adb_remote(host, port, f"shell pm clear {package}")
            success = "success" in (output or "").lower()
            if success:
                logger.info("Cleared app data for %s", package)
            else:
                logger.warning("Failed to clear app data for %s: %s", package, output)
            return success
        except Exception as e:
            logger.error(f"Failed to clear app data: {e}")
            return False

    def press_back(self, host: str, port: int) -> None:
        """
        Press back button.

        Args:
            host: Emulator host IP
            port: ADB port
        """
        try:
            self.execute_adb_remote(host, port, "shell input keyevent KEYCODE_BACK")
            logger.debug("Pressed back")
        except Exception as e:
            logger.error(f"Failed to press back: {e}")

    def press_home(self, host: str, port: int) -> None:
        """
        Press home button.

        Args:
            host: Emulator host IP
            port: ADB port
        """
        try:
            self.execute_adb_remote(host, port, "shell input keyevent KEYCODE_HOME")
            logger.debug("Pressed home")
        except Exception as e:
            logger.error(f"Failed to press home: {e}")
