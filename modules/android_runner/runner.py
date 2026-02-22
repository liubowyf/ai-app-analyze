"""Android Runner module for remote Android emulator control."""
import logging
import re
import shlex
import subprocess
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class AndroidRunner:
    """Remote Android emulator controller via ADB."""

    def __init__(self, use_docker: bool = False):
        """
        Initialize Android runner.

        Args:
            use_docker: Whether to use Docker for container management (optional)
        """
        self.container: Optional[Any] = None
        self._docker_client = None
        self._use_docker = use_docker

    def create_container(self, image: str = "budtmo/docker-android:emulator_11.0",
                        name: Optional[str] = None,
                        ports: Optional[Dict[str, int]] = None,
                        use_host_network: bool = True) -> str:
        """
        Create and start an Android emulator container.

        Args:
            image: Docker image to use
            name: Container name (optional)
            ports: Port mappings {container_port: host_port}
            use_host_network: Use host network mode for internet access (default: True)

        Returns:
            Container ID
        """
        if ports is None:
            ports = {
                "6080": 6080,  # noVNC
                "5555": 5555,  # ADB
                "8080": 8080,  # mitmproxy
            }

        try:
            # Network configuration
            network_mode = "host" if use_host_network else None

            # When using host network, ports are not needed
            port_config = None if use_host_network else ports

            container = self.client.containers.run(
                image=image,
                name=name,
                ports=port_config,
                environment={
                    "EMULATOR_DEVICE": "Nexus 5",
                    "WEB_VNC": "true",
                },
                detach=True,
                privileged=True,
                volumes={"/dev/kvm": {"bind": "/dev/kvm", "mode": "ro"}},
                network_mode=network_mode,
            )
            logger.info(f"Created container {container.id} with {'host' if use_host_network else 'bridge'} network")
            return container.id
        except APIError as e:
            logger.error(f"Failed to create container: {e}")
            raise

    def get_container(self, container_id: str) -> Any:
        """
        Get container by ID or name.

        Args:
            container_id: Container ID or name

        Returns:
            Container object
        """
        try:
            return self.client.containers.get(container_id)
        except NotFound:
            raise ValueError(f"Container {container_id} not found")

    def start_container(self, container_id: str) -> bool:
        """
        Start a stopped container.

        Args:
            container_id: Container ID

        Returns:
            True if successful
        """
        container = self.get_container(container_id)
        container.start()
        logger.info(f"Started container {container_id}")
        return True

    def stop_container(self, container_id: str, timeout: int = 10) -> bool:
        """
        Stop a running container.

        Args:
            container_id: Container ID
            timeout: Timeout in seconds

        Returns:
            True if successful
        """
        container = self.get_container(container_id)
        container.stop(timeout=timeout)
        logger.info(f"Stopped container {container_id}")
        return True

    def remove_container(self, container_id: str, force: bool = False) -> bool:
        """
        Remove a container.

        Args:
            container_id: Container ID
            force: Force removal of running container

        Returns:
            True if successful
        """
        container = self.get_container(container_id)
        container.remove(force=force)
        logger.info(f"Removed container {container_id}")
        return True

    def get_container_status(self, container_id: str) -> str:
        """
        Get container status.

        Args:
            container_id: Container ID

        Returns:
            Status string (running, exited, etc.)
        """
        container = self.get_container(container_id)
        return container.status

    def get_container_logs(self, container_id: str, tail: int = 100) -> str:
        """
        Get container logs.

        Args:
            container_id: Container ID
            tail: Number of lines to retrieve

        Returns:
            Log output
        """
        container = self.get_container(container_id)
        return container.logs(tail=tail).decode("utf-8")

    def execute_adb_command(self, container_id: str, command: str) -> str:
        """
        Execute ADB command in container.

        Args:
            container_id: Container ID
            command: ADB command to execute

        Returns:
            Command output
        """
        container = self.get_container(container_id)
        # ADB is available via adb command inside the container
        result = container.exec_run(f"adb {command}")
        return result.output.decode("utf-8")

    def install_apk(self, container_id: str, apk_path: str) -> bool:
        """
        Install APK on emulator.

        Args:
            container_id: Container ID
            apk_path: Path to APK file in container

        Returns:
            True if successful
        """
        try:
            result = self.execute_adb_command(container_id, f"install -r {apk_path}")
            logger.info(f"APK install result: {result}")
            return "Success" in result
        except Exception as e:
            logger.error(f"Failed to install APK: {e}")
            return False

    def uninstall_package(self, container_id: str, package_name: str) -> bool:
        """
        Uninstall package from emulator.

        Args:
            container_id: Container ID
            package_name: Package        Returns:
            name to uninstall

 True if successful
        """
        try:
            result = self.execute_adb_command(container_id, f"uninstall {package_name}")
            logger.info(f"Package uninstall result: {result}")
            return "Success" in result
        except Exception as e:
            logger.error(f"Failed to uninstall package: {e}")
            return False

    def take_screenshot(self, container_id: str) -> bytes:
        """
        Take screenshot of emulator screen.

        Args:
            container_id: Container ID

        Returns:
            Screenshot as bytes
        """
        # Use ADB to take screenshot
        result = self.execute_adb_command(
            container_id,
            "shell screencap -p /sdcard/screen.png"
        )
        # Copy to host
        container = self.get_container(container_id)
        _, stat = container.get_archive("/sdcard/screen.png")
        # For simplicity, return the PNG data
        return b""  # Placeholder

    def get_device_info(self, container_id: str) -> Dict[str, str]:
        """
        Get device information.

        Args:
            container_id: Container ID

        Returns:
            Dictionary with device info
        """
        info = {}
        # Get Android version
        result = self.execute_adb_command(container_id, "shell getprop ro.build.version.release")
        info["android_version"] = result.strip()

        # Get device model
        result = self.execute_adb_command(container_id, "shell getprop ro.product.model")
        info["device_model"] = result.strip()

        # Get SDK version
        result = self.execute_adb_command(container_id, "shell getprop ro.build.version.sdk")
        info["sdk_version"] = result.strip()

        return info

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

    def execute_adb_remote(self, host: str, port: int, command: str) -> str:
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
                timeout=30
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
        try:
            output = self.execute_adb_remote(host, port, f"install -r {apk_path}")
            success = "Success" in output
            if success:
                logger.info(f"APK installed successfully on {host}:{port}")
            else:
                logger.error(f"APK installation failed: {output}")
            return success
        except Exception as e:
            logger.error(f"Failed to install APK: {e}")
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
                # Android sometimes returns CRLF, normalize line endings for PNG parser compatibility.
                return image_data.replace(b"\r\n", b"\n")

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

    def launch_app(self, host: str, port: int, package: str) -> None:
        """
        Launch an app by package name.

        Args:
            host: Emulator host IP
            port: ADB port
            package: Package name
        """
        try:
            self.execute_adb_remote(
                host, port,
                f"shell monkey -p {package} -c android.intent.category.LAUNCHER 1"
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
