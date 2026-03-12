"""High-level device control helpers for the redroid remote backend."""
from __future__ import annotations

from pathlib import Path

from modules.redroid_remote.adb_client import RedroidADBClient


class RedroidDeviceController:
    def __init__(self, adb_client: RedroidADBClient):
        self.adb = adb_client

    def install_and_launch(self, apk_path: str, package_name: str, activity_name: str) -> dict:
        if not self.adb.connect():
            raise RuntimeError("Failed to connect ADB device")
        install_result = self.adb.install_apk(apk_path, timeout=600)
        launch_result = self.adb.start_activity(package_name, activity_name, wait=True)
        return {
            "install_result": install_result,
            "launch_result": launch_result,
        }

    def capture_screenshot(self, local_dir: str, file_name: str = "screen.png") -> str:
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        remote_path = f"/sdcard/{file_name}"
        local_path = str(Path(local_dir) / file_name)
        self.adb.shell(f"screencap -p {remote_path}", timeout=30)
        return self.adb.pull(remote_path, local_path, timeout=30)

    def dump_ui_xml(self, local_dir: str, file_name: str = "window_dump.xml") -> str:
        Path(local_dir).mkdir(parents=True, exist_ok=True)
        remote_path = f"/sdcard/{file_name}"
        local_path = str(Path(local_dir) / file_name)
        self.adb.shell(f"uiautomator dump {remote_path}", timeout=30)
        return self.adb.pull(remote_path, local_path, timeout=30)
