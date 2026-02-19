"""Android Runner module for Docker-Android container management."""
import logging
from typing import Optional, Dict, Any, List
import docker
from docker.errors import NotFound, APIError

logger = logging.getLogger(__name__)


class AndroidRunner:
    """Docker-Android container manager."""

    def __init__(self):
        """Initialize Android runner with Docker client."""
        self.client = docker.from_env()
        self.container: Optional[Any] = None

    def create_container(self, image: str = "budtmo/docker-android:emulator_11.0",
                        name: Optional[str] = None,
                        ports: Optional[Dict[str, int]] = None) -> str:
        """
        Create and start an Android emulator container.

        Args:
            image: Docker image to use
            name: Container name (optional)
            ports: Port mappings {container_port: host_port}

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
            container = self.client.containers.run(
                image=image,
                name=name,
                ports=ports,
                environment={
                    "EMULATOR_DEVICE": "Nexus 5",
                    "WEB_VNC": "true",
                },
                detach=True,
                privileged=True,
                volumes={"/dev/kvm": {"bind": "/dev/kvm", "mode": "ro"}},
            )
            logger.info(f"Created container {container.id}")
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
